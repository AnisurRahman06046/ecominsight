"""RAG (Retrieval-Augmented Generation) service for analytical questions."""

import hashlib
from typing import List, Dict, Any, Optional
from datetime import datetime
import logging

# Make heavy dependencies optional
try:
    import numpy as np
    from sentence_transformers import SentenceTransformer
    import chromadb
    from chromadb.config import Settings
    RAG_AVAILABLE = True
except ImportError:
    RAG_AVAILABLE = False
    logger = logging.getLogger(__name__)
    logger.warning("RAG dependencies not installed. RAG features disabled.")

from app.core.config import settings
from app.core.database import mongodb

logger = logging.getLogger(__name__)


class RAGService:
    """Service for RAG-based analytical insights."""

    def __init__(self):
        self.initialized = False
        self.collection = None

        if not RAG_AVAILABLE:
            logger.warning("RAG Service disabled - dependencies not installed")
            self.embedding_model = None
            self.chroma_client = None
            return

        # Initialize embedding model
        self.embedding_model = SentenceTransformer(settings.embedding_model)

        # Initialize ChromaDB
        self.chroma_client = chromadb.Client(
            Settings(
                persist_directory=settings.vector_db_path,
                anonymized_telemetry=False,
            )
        )

    async def initialize(self):
        """Initialize RAG service and create/load collection."""
        try:
            # Create or get collection
            self.collection = self.chroma_client.get_or_create_collection(
                name="ecommerce_insights",
                metadata={"description": "E-commerce analytics and insights"},
            )

            # Check if we need to populate initial documents
            if self.collection.count() == 0:
                await self._populate_initial_documents()

            self.initialized = True
            logger.info(f"RAG service initialized with {self.collection.count()} documents")

        except Exception as e:
            logger.error(f"Failed to initialize RAG service: {e}")
            self.initialized = False

    async def _populate_initial_documents(self):
        """Populate vector store with initial analytical documents."""
        try:
            # Generate summary documents from MongoDB
            documents = await self._generate_summary_documents()

            if documents:
                # Add documents to vector store
                self.add_documents(documents)
                logger.info(f"Added {len(documents)} initial documents to vector store")

        except Exception as e:
            logger.error(f"Failed to populate initial documents: {e}")

    async def _generate_summary_documents(self) -> List[Dict[str, Any]]:
        """Generate summary documents from database for RAG."""
        documents = []

        try:
            # Get list of shops
            shops = await mongodb.database["orders"].distinct("shop_id")

            for shop_id in shops[:10]:  # Limit to first 10 shops for demo
                # Generate various summaries
                summaries = await self._generate_shop_summaries(shop_id)
                documents.extend(summaries)

        except Exception as e:
            logger.error(f"Failed to generate summary documents: {e}")

        return documents

    async def _generate_shop_summaries(self, shop_id: str) -> List[Dict[str, Any]]:
        """Generate analytical summaries for a shop."""
        summaries = []
        timestamp = datetime.utcnow()

        try:
            # Sales trend summary
            sales_data = await mongodb.execute_aggregation(
                "orders",
                [
                    {"$match": {"shop_id": shop_id, "status": "completed"}},
                    {
                        "$group": {
                            "_id": {
                                "year": {"$year": "$created_at"},
                                "month": {"$month": "$created_at"},
                            },
                            "total_sales": {"$sum": "$total_amount"},
                            "order_count": {"$sum": 1},
                            "avg_order": {"$avg": "$total_amount"},
                        }
                    },
                    {"$sort": {"_id.year": -1, "_id.month": -1}},
                    {"$limit": 6},
                ],
            )

            if sales_data:
                # Analyze trends
                sales_values = [d["total_sales"] for d in sales_data]
                if len(sales_values) > 1:
                    trend = "increasing" if sales_values[0] > sales_values[-1] else "decreasing"
                    growth = ((sales_values[0] - sales_values[-1]) / sales_values[-1]) * 100 if sales_values[-1] > 0 else 0

                    summary = f"""Shop {shop_id} Sales Analysis:
- Sales trend: {trend} ({growth:.1f}% over last 6 months)
- Average monthly sales: ${np.mean(sales_values):,.2f}
- Peak month: ${max(sales_values):,.2f}
- Current month: ${sales_values[0]:,.2f}
- Average order value: ${np.mean([d['avg_order'] for d in sales_data]):,.2f}"""

                    summaries.append(
                        {
                            "id": hashlib.md5(f"{shop_id}_sales_trend_{timestamp}".encode()).hexdigest(),
                            "content": summary,
                            "metadata": {
                                "shop_id": shop_id,
                                "type": "sales_trend",
                                "created_at": timestamp.isoformat(),
                            },
                        }
                    )

            # Category performance summary
            category_data = await mongodb.execute_aggregation(
                "order_items",
                [
                    {"$match": {"shop_id": shop_id}},
                    {
                        "$lookup": {
                            "from": "products",
                            "localField": "product_id",
                            "foreignField": "_id",
                            "as": "product",
                        }
                    },
                    {"$unwind": "$product"},
                    {
                        "$group": {
                            "_id": "$product.category",
                            "revenue": {"$sum": {"$multiply": ["$quantity", "$price"]}},
                            "units_sold": {"$sum": "$quantity"},
                        }
                    },
                    {"$sort": {"revenue": -1}},
                    {"$limit": 5},
                ],
            )

            if category_data:
                top_categories = ", ".join([f"{c['_id']} (${c['revenue']:,.0f})" for c in category_data[:3]])
                summary = f"""Shop {shop_id} Category Performance:
- Top categories: {top_categories}
- Best performing: {category_data[0]['_id']} with ${category_data[0]['revenue']:,.2f} in revenue
- Total categories: {len(category_data)}"""

                summaries.append(
                    {
                        "id": hashlib.md5(f"{shop_id}_categories_{timestamp}".encode()).hexdigest(),
                        "content": summary,
                        "metadata": {
                            "shop_id": shop_id,
                            "type": "category_analysis",
                            "created_at": timestamp.isoformat(),
                        },
                    }
                )

            # Customer behavior summary
            customer_data = await mongodb.execute_aggregation(
                "customers",
                [
                    {"$match": {"shop_id": shop_id}},
                    {
                        "$group": {
                            "_id": None,
                            "total_customers": {"$sum": 1},
                            "avg_lifetime_value": {"$avg": "$total_spent"},
                            "avg_order_count": {"$avg": "$order_count"},
                        }
                    },
                ],
            )

            if customer_data and customer_data[0]:
                data = customer_data[0]
                summary = f"""Shop {shop_id} Customer Insights:
- Total customers: {data['total_customers']}
- Average lifetime value: ${data['avg_lifetime_value']:,.2f}
- Average orders per customer: {data['avg_order_count']:.1f}
- Customer retention indicator: {"High" if data['avg_order_count'] > 3 else "Needs improvement"}"""

                summaries.append(
                    {
                        "id": hashlib.md5(f"{shop_id}_customers_{timestamp}".encode()).hexdigest(),
                        "content": summary,
                        "metadata": {
                            "shop_id": shop_id,
                            "type": "customer_analysis",
                            "created_at": timestamp.isoformat(),
                        },
                    }
                )

        except Exception as e:
            logger.error(f"Failed to generate summaries for shop {shop_id}: {e}")

        return summaries

    def add_documents(self, documents: List[Dict[str, Any]]):
        """Add documents to vector store."""
        if not self.collection:
            logger.error("Collection not initialized")
            return

        try:
            # Prepare data for ChromaDB
            ids = [doc["id"] for doc in documents]
            contents = [doc["content"] for doc in documents]
            metadatas = [doc.get("metadata", {}) for doc in documents]

            # Generate embeddings
            embeddings = self.embedding_model.encode(contents).tolist()

            # Add to collection
            self.collection.add(
                ids=ids,
                embeddings=embeddings,
                documents=contents,
                metadatas=metadatas,
            )

            logger.info(f"Added {len(documents)} documents to vector store")

        except Exception as e:
            logger.error(f"Failed to add documents: {e}")

    def search(
        self,
        query: str,
        shop_id: Optional[str] = None,
        n_results: int = 5,
    ) -> List[Dict[str, Any]]:
        """
        Search for relevant documents using vector similarity.

        Args:
            query: Search query
            shop_id: Optional shop filter
            n_results: Number of results to return

        Returns:
            List of relevant documents
        """
        if not self.collection:
            logger.error("Collection not initialized")
            return []

        try:
            # Generate query embedding
            query_embedding = self.embedding_model.encode(query).tolist()

            # Prepare filters
            where = {"shop_id": shop_id} if shop_id else None

            # Search
            results = self.collection.query(
                query_embeddings=[query_embedding],
                n_results=n_results,
                where=where,
            )

            # Format results
            documents = []
            if results["documents"] and results["documents"][0]:
                for i, doc in enumerate(results["documents"][0]):
                    documents.append(
                        {
                            "content": doc,
                            "metadata": results["metadatas"][0][i] if results["metadatas"] else {},
                            "distance": results["distances"][0][i] if results["distances"] else 0,
                        }
                    )

            return documents

        except Exception as e:
            logger.error(f"Search failed: {e}")
            return []

    async def update_insights(self, shop_id: str):
        """Update insights for a specific shop."""
        try:
            # Generate new summaries
            new_summaries = await self._generate_shop_summaries(shop_id)

            if new_summaries:
                # Remove old summaries for this shop
                self.collection.delete(where={"shop_id": shop_id})

                # Add new summaries
                self.add_documents(new_summaries)

                logger.info(f"Updated {len(new_summaries)} insights for shop {shop_id}")

        except Exception as e:
            logger.error(f"Failed to update insights for shop {shop_id}: {e}")


# Global instance
rag_service = RAGService()
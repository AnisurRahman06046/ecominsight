"""
Semantic Router Service
Uses sentence embeddings to match user queries to appropriate tools based on semantic similarity.
This is more robust than keyword matching and works locally without cloud APIs.
"""

import logging
import json
import numpy as np
from typing import Dict, Any, Optional, List, Tuple
from pathlib import Path

logger = logging.getLogger(__name__)


class SemanticRouter:
    """
    Routes queries to appropriate tools using semantic similarity.
    Uses sentence-transformers for local, fast embedding generation.
    """

    def __init__(self):
        self.model = None
        self.tool_examples = self._load_tool_examples()
        self.tool_embeddings = {}
        self.initialized = False
        self._initialize_model()

    def _load_tool_examples(self) -> Dict[str, List[str]]:
        """
        Load example queries for each tool.
        These examples help the router understand what each tool is for.
        """
        return {
            "count_documents": [
                "how many products",
                "how many orders",
                "how many customers",
                "total number of products",
                "total number of orders",
                "total number of customers",
                "count all products",
                "count all orders",
                "count customers",
                "what is the total products",
                "what is the total orders",
                "total products",
                "total orders",
                "total customers",
                "number of products",
                "number of orders",
                "number of customers",
                "product count",
                "order count",
                "customer count",
                "how many items",
                "count of products",
                "count of orders",
                "how many orders did i get this month",
                "orders this month",
                "how many new customers this month",
                "customer growth this month",
                "how many orders last week",
                "total last week orders",
            ],
            "calculate_sum": [
                "total revenue",
                "total sales",
                "sum of sales",
                "how much revenue",
                "how much money",
                "total amount",
                "revenue generated",
                "sales generated",
                "total earnings",
                "sum of revenue",
                "what is the total revenue",
                "what is the total sales",
                "how much did we make",
                "total income",
                "gross revenue",
                "total grand total",
                "sales this week",
                "sales this month",
                "revenue this week",
                "revenue this month",
                "this week sales",
                "this month sales",
                "how much yesterday",
                "how much today",
                "how much did i sell yesterday",
                "how much did i sell today",
                "yesterday sales",
                "today sales",
                "sales from yesterday",
                "sales from today",
                "show sales",
                "revenue per day this week",
                "give me total sales this month",
                "total sales this month",
            ],
            "calculate_average": [
                "average order value",
                "average price",
                "mean order value",
                "avg order",
                "average sale",
                "what is the average order",
                "mean revenue per order",
                "average revenue",
                "typical order value",
                "average amount",
                "what's my average order value",
                "average revenue per customer",
                "avg order value",
                "mean order amount",
            ],
            "get_top_customers_by_spending": [
                "top customers",
                "best customers",
                "highest spending customers",
                "who spent the most",
                "biggest spenders",
                "most valuable customers",
                "top spenders",
                "customers by spending",
                "who are my best customers",
                "customers who spent most",
                "loyal customers",
                "top buyers",
                "customer with highest spending",
                "who are my top customers",
                "show me top spenders",
                "top 5 customers",
                "top 10 customers",
                "best buyers",
                "top spending customers",
                "who spends the most",
                "show top customers",
                "how many buyers",
            ],
            "get_best_selling_products": [
                "best selling products",
                "top products",
                "most popular products",
                "best sellers",
                "top selling items",
                "which products sell most",
                "most sold products",
                "popular products",
                "highest selling products",
                "top performing products",
                "products by sales",
                "what are my top products",
                "show me top sellers",
                "top 5 products",
                "top 10 products",
                "best products",
                "most popular products",
                "what are my best sellers",
                "show best selling products",
                "most ordered product",
                "least ordered product",
                "which products are not selling",
            ],
            "group_and_count": [
                "orders by status",
                "breakdown by status",
                "group by payment status",
                "distribution by category",
                "orders by payment method",
                "count by status",
                "group orders by status",
                "breakdown of orders",
                "payment status breakdown",
                "order distribution",
                "categorize orders",
                # Time-based grouping queries
                "which month has the highest order",
                "which month has the most orders",
                "which month has the lowest order",
                "which month has the fewest orders",
                "worst performing month",
                "best performing month",
                "orders by month",
                "monthly order breakdown",
                "sales by month",
                "revenue by month",
                "which day has most orders",
                "orders by day",
                "daily order count",
                "which year has highest sales",
                "yearly sales breakdown",
                "monthly sales distribution",
                "order count by month",
                "which month has the highest sales",
                "breakdown by month",
                "group by month",
            ],
            "find_documents": [
                "list orders",
                "list all orders",
                "list all products",
                "list products",
                "show products",
                "display customers",
                "get orders",
                "view products",
                "see all orders",
                "recent orders",
                "latest orders",
                "find orders",
                "search products",
                "show me orders",
                "give me products",
                "pending orders",
                "paid orders",
                "unpaid orders",
            ],
        }

    def _initialize_model(self):
        """Initialize sentence transformer model for embeddings."""
        try:
            from sentence_transformers import SentenceTransformer

            # Try multiple models in order of preference
            models_to_try = [
                "all-MiniLM-L6-v2",      # Best balance (80MB, fast, good quality)
                "paraphrase-MiniLM-L3-v2",  # Smaller, faster (60MB)
                "all-MiniLM-L12-v2",     # Better quality, slower (120MB)
            ]

            for model_name in models_to_try:
                try:
                    logger.info(f"Loading semantic model: {model_name}...")
                    self.model = SentenceTransformer(model_name)
                    self.model_name = model_name
                    logger.info(f"Semantic router initialized with {model_name}")

                    # Pre-compute embeddings for all examples
                    self._compute_tool_embeddings()
                    self.initialized = True
                    return

                except Exception as e:
                    logger.warning(f"Failed to load {model_name}: {e}")
                    continue

            logger.error("All semantic models failed to load")
            self.initialized = False

        except ImportError:
            logger.error("sentence-transformers not installed. Run: pip install sentence-transformers")
            self.initialized = False
        except Exception as e:
            logger.error(f"Semantic router initialization failed: {e}")
            self.initialized = False

    def _compute_tool_embeddings(self):
        """Pre-compute embeddings for all tool examples."""
        if not self.model:
            return

        logger.info("Pre-computing tool embeddings...")
        for tool_name, examples in self.tool_examples.items():
            # Compute embeddings for all examples
            embeddings = self.model.encode(examples, convert_to_numpy=True)
            self.tool_embeddings[tool_name] = embeddings
            logger.debug(f"Computed {len(examples)} embeddings for {tool_name}")

        logger.info(f"Pre-computed embeddings for {len(self.tool_embeddings)} tools")

    def route_query(
        self,
        query: str,
        min_confidence: float = 0.65
    ) -> Optional[Dict[str, Any]]:
        """
        Route a query to the most appropriate tool using semantic similarity.

        Args:
            query: User's natural language query
            min_confidence: Minimum similarity score (0-1) to consider a match

        Returns:
            Dict with tool name, confidence, and metadata, or None if no good match
        """
        if not self.initialized or not self.model:
            logger.warning("Semantic router not initialized, falling back")
            return None

        try:
            # Encode the query
            query_embedding = self.model.encode(query, convert_to_numpy=True)

            # Find best matching tool
            best_tool = None
            best_confidence = 0.0
            best_example = None
            all_scores = {}

            for tool_name, tool_embeddings in self.tool_embeddings.items():
                # Calculate cosine similarity with all examples for this tool
                similarities = self._cosine_similarity(query_embedding, tool_embeddings)

                # Take the maximum similarity across all examples
                max_similarity = float(np.max(similarities))
                best_example_idx = int(np.argmax(similarities))

                all_scores[tool_name] = max_similarity

                if max_similarity > best_confidence:
                    best_confidence = max_similarity
                    best_tool = tool_name
                    best_example = self.tool_examples[tool_name][best_example_idx]

            # Log all scores for debugging
            logger.info(f"Query: '{query}' | Scores: {json.dumps({k: round(v, 3) for k, v in all_scores.items()})}")

            # Check if confidence meets threshold
            if best_confidence >= min_confidence:
                logger.info(f"Semantic match: {best_tool} (confidence: {best_confidence:.3f}, matched: '{best_example}')")

                # Extract parameters from query (basic extraction)
                parameters = self._extract_parameters(query, best_tool)

                return {
                    "tool": best_tool,
                    "confidence": best_confidence,
                    "parameters": parameters,
                    "method": "semantic_router",
                    "matched_example": best_example,
                    "all_scores": all_scores
                }
            else:
                logger.info(f"No confident semantic match (best: {best_tool} at {best_confidence:.3f}, threshold: {min_confidence})")
                return None

        except Exception as e:
            logger.error(f"Semantic routing failed: {e}")
            return None

    def _cosine_similarity(self, query_embedding: np.ndarray, tool_embeddings: np.ndarray) -> np.ndarray:
        """Calculate cosine similarity between query and tool embeddings."""
        # Normalize embeddings
        query_norm = query_embedding / np.linalg.norm(query_embedding)
        tool_norms = tool_embeddings / np.linalg.norm(tool_embeddings, axis=1, keepdims=True)

        # Compute dot product (cosine similarity for normalized vectors)
        similarities = np.dot(tool_norms, query_norm)
        return similarities

    def _extract_parameters(self, query: str, tool_name: str) -> Dict[str, Any]:
        """
        Extract basic parameters from query based on tool type.
        This is a simple heuristic-based extraction.
        """
        import re
        query_lower = query.lower()
        params = {}

        # Determine collection from query
        if "product" in query_lower:
            params["collection"] = "product"
        elif "customer" in query_lower:
            params["collection"] = "customer"
        elif "order" in query_lower:
            params["collection"] = "order"
        elif "category" in query_lower or "categories" in query_lower:
            params["collection"] = "category"
        else:
            # Default based on tool
            if tool_name in ["get_best_selling_products"]:
                params["collection"] = "product"
            elif tool_name in ["get_top_customers_by_spending"]:
                params["collection"] = "customer"
            else:
                params["collection"] = "order"

        # Extract limit/top N
        numbers = re.findall(r'\b(\d+)\b', query_lower)
        if numbers:
            limit = int(numbers[0])
            if limit > 0 and limit <= 100:
                params["limit"] = limit

        # Set default limit for certain tools
        if "limit" not in params:
            if tool_name in ["get_top_customers_by_spending", "get_best_selling_products"]:
                params["limit"] = 10
            elif tool_name == "find_documents":
                params["limit"] = 10

        # Extract field for sum/average
        if tool_name == "calculate_sum":
            params["sum_field"] = "grand_total"
        elif tool_name == "calculate_average":
            params["avg_field"] = "grand_total"

        # Extract group_by field
        if tool_name == "group_and_count":
            # Time-based grouping
            if "month" in query_lower or "monthly" in query_lower:
                params["group_by"] = "month"
            elif "day" in query_lower or "daily" in query_lower:
                params["group_by"] = "day"
            elif "year" in query_lower or "yearly" in query_lower:
                params["group_by"] = "year"
            elif "week" in query_lower or "weekly" in query_lower:
                params["group_by"] = "week"
            # Field-based grouping
            elif "status" in query_lower and "payment" not in query_lower:
                params["group_by"] = "status"
            elif "payment" in query_lower:
                params["group_by"] = "payment_status"
            elif "category" in query_lower or "categories" in query_lower:
                params["group_by"] = "category_id"
            else:
                params["group_by"] = "status"

        # Extract filters (basic)
        filter_dict = {}

        if "pending" in query_lower:
            filter_dict["status"] = "pending"
        elif "confirmed" in query_lower:
            filter_dict["status"] = "confirmed"
        elif "delivered" in query_lower:
            filter_dict["status"] = "delivered"

        if "paid" in query_lower and "unpaid" not in query_lower:
            filter_dict["payment_status"] = "paid"
        elif "unpaid" in query_lower:
            filter_dict["payment_status"] = "unpaid"

        if filter_dict:
            params["filter"] = filter_dict

        return params

    def add_example(self, tool_name: str, example_query: str):
        """
        Add a new example query for a tool (for continuous improvement).
        Call this when you identify a query that should match a specific tool.
        """
        if tool_name not in self.tool_examples:
            logger.warning(f"Unknown tool: {tool_name}")
            return

        # Add to examples
        self.tool_examples[tool_name].append(example_query)

        # Recompute embeddings for this tool
        if self.initialized and self.model:
            embeddings = self.model.encode(self.tool_examples[tool_name], convert_to_numpy=True)
            self.tool_embeddings[tool_name] = embeddings
            logger.info(f"Added example '{example_query}' to {tool_name}")

    def save_examples(self, filepath: str = "config/semantic_examples.json"):
        """Save current examples to file for persistence."""
        try:
            Path(filepath).parent.mkdir(parents=True, exist_ok=True)
            with open(filepath, 'w') as f:
                json.dump(self.tool_examples, f, indent=2)
            logger.info(f"Saved {sum(len(ex) for ex in self.tool_examples.values())} examples to {filepath}")
        except Exception as e:
            logger.error(f"Failed to save examples: {e}")

    def load_examples(self, filepath: str = "config/semantic_examples.json"):
        """Load examples from file and recompute embeddings."""
        try:
            with open(filepath, 'r') as f:
                self.tool_examples = json.load(f)
            logger.info(f"Loaded {sum(len(ex) for ex in self.tool_examples.values())} examples from {filepath}")

            # Recompute embeddings
            if self.initialized:
                self._compute_tool_embeddings()
        except FileNotFoundError:
            logger.info(f"No saved examples found at {filepath}, using defaults")
        except Exception as e:
            logger.error(f"Failed to load examples: {e}")


# Global instance
semantic_router = SemanticRouter()

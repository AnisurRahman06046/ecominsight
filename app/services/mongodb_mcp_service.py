"""
MongoDB MCP (Model Context Protocol) Service
Provides tool-based interface for MongoDB operations that LLMs can use reliably
"""

import json
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta

from app.core.database import mongodb
from app.core.config import settings

logger = logging.getLogger(__name__)


class MongoDBMCPService:
    """
    MCP-style tool interface for MongoDB operations.
    Each method represents a tool that can be called by the LLM.
    """

    async def count_documents(
        self,
        collection: str,
        shop_id: int,
        filter: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Count documents in a collection with optional filter.

        Args:
            collection: Name of the collection
            shop_id: Shop ID to filter by
            filter: Optional additional filter conditions

        Returns:
            Dict with count result
        """
        try:
            pipeline = [{"$match": {"shop_id": shop_id}}]

            if filter:
                pipeline[0]["$match"].update(filter)

            pipeline.append({"$count": "total"})

            result = await mongodb.execute_aggregation(collection, pipeline)
            count = result[0]["total"] if result else 0

            return {
                "success": True,
                "count": count,
                "message": f"Found {count} {collection}(s)"
            }
        except Exception as e:
            logger.error(f"Count documents failed: {e}")
            return {
                "success": False,
                "error": str(e)
            }

    async def find_documents(
        self,
        collection: str,
        shop_id: int,
        filter: Optional[Dict[str, Any]] = None,
        sort_by: Optional[str] = None,
        sort_order: int = -1,
        limit: int = 10
    ) -> Dict[str, Any]:
        """
        Find documents with filtering, sorting, and limiting.

        Args:
            collection: Name of the collection
            shop_id: Shop ID to filter by
            filter: Optional filter conditions
            sort_by: Field to sort by
            sort_order: 1 for ascending, -1 for descending
            limit: Maximum number of documents to return

        Returns:
            Dict with documents
        """
        try:
            pipeline = [{"$match": {"shop_id": shop_id}}]

            if filter:
                pipeline[0]["$match"].update(filter)

            if sort_by:
                pipeline.append({"$sort": {sort_by: sort_order}})

            pipeline.append({"$limit": limit})

            result = await mongodb.execute_aggregation(collection, pipeline)

            return {
                "success": True,
                "documents": result,
                "count": len(result),
                "message": f"Found {len(result)} {collection}(s)"
            }
        except Exception as e:
            logger.error(f"Find documents failed: {e}")
            return {
                "success": False,
                "error": str(e)
            }

    async def group_and_count(
        self,
        collection: str,
        shop_id: int,
        group_by: str,
        filter: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Group documents by a field and count them.

        Args:
            collection: Name of the collection
            shop_id: Shop ID to filter by
            group_by: Field to group by
            filter: Optional filter conditions

        Returns:
            Dict with grouped counts
        """
        try:
            # Validate group_by field - handle both string and list
            if isinstance(group_by, list):
                # If list, use first field or default
                group_by = group_by[0] if group_by else "status"
                logger.info(f"group_by was a list, using first field: {group_by}")
            elif isinstance(group_by, str):
                if not group_by or group_by.strip() == "":
                    # Default to status for orders, name for others
                    default_fields = {
                        "order": "status",
                        "product": "category_id",
                        "customer": "status",
                        "category": "parent_id"
                    }
                    group_by = default_fields.get(collection, "status")
                    logger.warning(f"Empty group_by field, using default: {group_by}")
            else:
                # Unexpected type, use default
                group_by = "status"
                logger.warning(f"Unexpected group_by type: {type(group_by)}, using default")

            pipeline = [{"$match": {"shop_id": shop_id}}]

            if filter:
                pipeline[0]["$match"].update(filter)

            pipeline.extend([
                {
                    "$group": {
                        "_id": f"${group_by}",
                        "count": {"$sum": 1}
                    }
                },
                {"$sort": {"count": -1}}
            ])

            result = await mongodb.execute_aggregation(collection, pipeline)

            return {
                "success": True,
                "groups": result,
                "total_groups": len(result),
                "message": f"Grouped {collection} by {group_by}"
            }
        except Exception as e:
            logger.error(f"Group and count failed: {e}")
            return {
                "success": False,
                "error": str(e)
            }

    async def calculate_sum(
        self,
        collection: str,
        shop_id: int,
        sum_field: str,
        group_by: Optional[str] = None,
        filter: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Calculate sum of a field, optionally grouped.

        Args:
            collection: Name of the collection
            shop_id: Shop ID to filter by
            sum_field: Field to sum
            group_by: Optional field to group by
            filter: Optional filter conditions

        Returns:
            Dict with sum result
        """
        try:
            pipeline = [{"$match": {"shop_id": shop_id}}]

            if filter:
                pipeline[0]["$match"].update(filter)

            if group_by:
                pipeline.append({
                    "$group": {
                        "_id": f"${group_by}",
                        "total": {"$sum": f"${sum_field}"},
                        "count": {"$sum": 1}
                    }
                })
                pipeline.append({"$sort": {"total": -1}})
            else:
                pipeline.append({
                    "$group": {
                        "_id": None,
                        "total": {"$sum": f"${sum_field}"},
                        "count": {"$sum": 1}
                    }
                })

            result = await mongodb.execute_aggregation(collection, pipeline)

            return {
                "success": True,
                "result": result,
                "message": f"Calculated sum of {sum_field}"
            }
        except Exception as e:
            logger.error(f"Calculate sum failed: {e}")
            return {
                "success": False,
                "error": str(e)
            }

    async def calculate_average(
        self,
        collection: str,
        shop_id: int,
        avg_field: str,
        group_by: Optional[str] = None,
        filter: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Calculate average of a field, optionally grouped.

        Args:
            collection: Name of the collection
            shop_id: Shop ID to filter by
            avg_field: Field to average
            group_by: Optional field to group by
            filter: Optional filter conditions

        Returns:
            Dict with average result
        """
        try:
            pipeline = [{"$match": {"shop_id": shop_id}}]

            if filter:
                pipeline[0]["$match"].update(filter)

            if group_by:
                pipeline.append({
                    "$group": {
                        "_id": f"${group_by}",
                        "average": {"$avg": f"${avg_field}"},
                        "count": {"$sum": 1}
                    }
                })
                pipeline.append({"$sort": {"average": -1}})
            else:
                pipeline.append({
                    "$group": {
                        "_id": None,
                        "average": {"$avg": f"${avg_field}"},
                        "count": {"$sum": 1}
                    }
                })

            result = await mongodb.execute_aggregation(collection, pipeline)

            return {
                "success": True,
                "result": result,
                "message": f"Calculated average of {avg_field}"
            }
        except Exception as e:
            logger.error(f"Calculate average failed: {e}")
            return {
                "success": False,
                "error": str(e)
            }

    async def get_top_n(
        self,
        collection: str,
        shop_id: int,
        sort_by: str,
        n: int = 5,
        ascending: bool = False,
        filter: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Get top N documents sorted by a field.

        Args:
            collection: Name of the collection
            shop_id: Shop ID to filter by
            sort_by: Field to sort by
            n: Number of documents to return
            ascending: If True, get bottom N instead
            filter: Optional filter conditions

        Returns:
            Dict with top N documents
        """
        try:
            pipeline = [{"$match": {"shop_id": shop_id}}]

            if filter:
                pipeline[0]["$match"].update(filter)

            sort_order = 1 if ascending else -1
            pipeline.extend([
                {"$sort": {sort_by: sort_order}},
                {"$limit": n}
            ])

            result = await mongodb.execute_aggregation(collection, pipeline)

            return {
                "success": True,
                "documents": result,
                "count": len(result),
                "message": f"Top {n} {collection}s by {sort_by}"
            }
        except Exception as e:
            logger.error(f"Get top N failed: {e}")
            return {
                "success": False,
                "error": str(e)
            }

    async def get_date_range(
        self,
        collection: str,
        shop_id: int,
        date_field: str,
        days_back: int = 7,
        filter: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Get documents within a date range.

        Args:
            collection: Name of the collection
            shop_id: Shop ID to filter by
            date_field: Field containing date
            days_back: Number of days to look back
            filter: Optional additional filters

        Returns:
            Dict with documents in date range
        """
        try:
            # Calculate date range
            end_date = datetime.now()
            start_date = end_date - timedelta(days=days_back)

            pipeline = [
                {
                    "$match": {
                        "shop_id": shop_id,
                        date_field: {
                            "$gte": start_date.isoformat(),
                            "$lte": end_date.isoformat()
                        }
                    }
                }
            ]

            if filter:
                pipeline[0]["$match"].update(filter)

            pipeline.append({"$sort": {date_field: -1}})

            result = await mongodb.execute_aggregation(collection, pipeline)

            return {
                "success": True,
                "documents": result,
                "count": len(result),
                "message": f"Found {len(result)} {collection}s from last {days_back} days"
            }
        except Exception as e:
            logger.error(f"Get date range failed: {e}")
            return {
                "success": False,
                "error": str(e)
            }

    async def get_collections(self) -> Dict[str, Any]:
        """
        Get list of all available collections.

        Returns:
            Dict with list of collections
        """
        try:
            collections = await mongodb.list_collections()
            return {
                "success": True,
                "collections": collections,
                "count": len(collections),
                "message": f"Found {len(collections)} collections"
            }
        except Exception as e:
            logger.error(f"Get collections failed: {e}")
            return {
                "success": False,
                "error": str(e)
            }

    async def get_best_selling_products(
        self,
        shop_id: int,
        limit: int = 10,
        filter: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Get best selling products by analyzing order_product collection.
        Joins with order collection to filter by shop_id.

        Args:
            shop_id: Shop ID to filter by
            limit: Number of products to return
            filter: Optional filter for orders

        Returns:
            Dict with top selling products
        """
        try:
            # First approach: Try direct aggregation on order_product if it has shop_id
            pipeline = []

            # Try to filter by shop_id if field exists
            match_stage = {"shop_id": shop_id} if shop_id else {}
            if filter:
                match_stage.update(filter)

            if match_stage:
                pipeline.append({"$match": match_stage})

            # Group by product_id and count/sum
            pipeline.extend([
                {
                    "$group": {
                        "_id": "$product_id",
                        "total_quantity": {"$sum": "$quantity"},
                        "total_revenue": {"$sum": {"$multiply": ["$price", "$quantity"]}},
                        "order_count": {"$sum": 1}
                    }
                },
                {"$sort": {"total_quantity": -1}},
                {"$limit": limit}
            ])

            # Try to get product details
            pipeline.append({
                "$lookup": {
                    "from": "product",
                    "localField": "_id",
                    "foreignField": "id",
                    "as": "product_info"
                }
            })

            result = await mongodb.execute_aggregation("order_product", pipeline)

            # If no results, try alternative approach with join
            if not result:
                # Alternative: Join order_product with order first
                pipeline = [
                    # First get orders for this shop
                    {"$match": {"shop_id": shop_id}},

                    # Lookup order products
                    {
                        "$lookup": {
                            "from": "order_product",
                            "localField": "id",
                            "foreignField": "order_id",
                            "as": "products"
                        }
                    },

                    # Unwind products
                    {"$unwind": "$products"},

                    # Group by product_id
                    {
                        "$group": {
                            "_id": "$products.product_id",
                            "total_quantity": {"$sum": "$products.quantity"},
                            "total_revenue": {"$sum": {"$multiply": ["$products.price", "$products.quantity"]}},
                            "order_count": {"$sum": 1}
                        }
                    },

                    {"$sort": {"total_quantity": -1}},
                    {"$limit": limit},

                    # Get product details
                    {
                        "$lookup": {
                            "from": "product",
                            "localField": "_id",
                            "foreignField": "id",
                            "as": "product_info"
                        }
                    }
                ]

                result = await mongodb.execute_aggregation("order", pipeline)

            # Format results
            formatted_result = []
            for r in result:
                product_data = {
                    "product_id": r["_id"],
                    "total_quantity": r.get("total_quantity", 0),
                    "total_revenue": r.get("total_revenue", 0),
                    "order_count": r.get("order_count", 0)
                }

                if r.get("product_info"):
                    product = r["product_info"][0]
                    product_data["name"] = product.get("name", "")
                    product_data["sku"] = product.get("sku", "")
                    product_data["price"] = product.get("price", 0)

                formatted_result.append(product_data)

            return {
                "success": True,
                "products": formatted_result,
                "count": len(formatted_result),
                "message": f"Top {len(formatted_result)} best selling products"
            }

        except Exception as e:
            logger.error(f"Get best selling products failed: {e}")
            return {
                "success": False,
                "error": str(e)
            }

    async def get_top_customers_by_spending(
        self,
        shop_id: int,
        limit: int = 10,
        filter: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Special tool for getting top customers by total spending.

        Args:
            shop_id: Shop ID to filter by
            limit: Number of customers to return
            filter: Optional filter for orders

        Returns:
            Dict with top customers
        """
        try:
            pipeline = [{"$match": {"shop_id": shop_id}}]

            if filter:
                pipeline[0]["$match"].update(filter)

            pipeline.extend([
                {
                    "$group": {
                        "_id": "$user_id",
                        "total_spent": {"$sum": "$grand_total"},
                        "order_count": {"$sum": 1}
                    }
                },
                {"$sort": {"total_spent": -1}},
                {"$limit": limit},
                {
                    "$lookup": {
                        "from": "customer",
                        "localField": "_id",
                        "foreignField": "id",
                        "as": "customer_info"
                    }
                }
            ])

            result = await mongodb.execute_aggregation("order", pipeline)

            # Format result
            formatted_result = []
            for r in result:
                customer_data = {
                    "user_id": r["_id"],
                    "total_spent": r["total_spent"],
                    "order_count": r["order_count"]
                }
                if r.get("customer_info"):
                    customer = r["customer_info"][0]
                    customer_data["name"] = f"{customer.get('first_name', '')} {customer.get('last_name', '')}"
                    customer_data["email"] = customer.get("email", "")
                formatted_result.append(customer_data)

            return {
                "success": True,
                "customers": formatted_result,
                "count": len(formatted_result),
                "message": f"Top {len(formatted_result)} customers by spending"
            }
        except Exception as e:
            logger.error(f"Get top customers failed: {e}")
            return {
                "success": False,
                "error": str(e)
            }


# Global instance
mongodb_mcp = MongoDBMCPService()
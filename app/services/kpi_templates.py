"""MongoDB query templates for predefined KPIs."""

from typing import Dict, Any, List
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)


class KPITemplates:
    """Predefined MongoDB aggregation templates for common KPIs."""

    def __init__(self):
        self.templates = self._load_templates()

    def _get_shop_id_filter(self, shop_id: str) -> int:
        """Convert shop_id to integer if possible, as MongoDB stores them as integers."""
        try:
            return int(shop_id)
        except (ValueError, TypeError):
            return shop_id

    def _load_templates(self) -> Dict[str, Dict[str, Any]]:
        """Load all KPI templates."""
        return {
            "total_sales": {
                "collection": "order",  # Changed from orders
                "pipeline": self._total_sales_pipeline,
                "answer_template": "Your total sales {time_desc} {is_were} ${total:,.2f}",
            },
            "order_count": {
                "collection": "order",  # Changed from orders
                "pipeline": self._order_count_pipeline,
                "answer_template": "You had {count} orders {time_desc}",
            },
            "product_count": {
                "collection": "product",  # Changed from products
                "pipeline": self._product_count_pipeline,
                "answer_template": "You have {count} {filter_desc} products",
            },
            "customer_count": {
                "collection": "customer",  # Changed from customers
                "pipeline": self._customer_count_pipeline,
                "answer_template": "You have {count} {filter_desc} customers",
            },
            "average_order_value": {
                "collection": "order",  # Changed from orders
                "pipeline": self._avg_order_pipeline,
                "answer_template": "Your average order value {time_desc} {is_was} ${avg:,.2f}",
            },
            "top_products": {
                "collection": "order_items",
                "pipeline": self._top_products_pipeline,
                "answer_template": self._format_top_products,
            },
            "top_customers": {
                "collection": "order",  # Changed from orders
                "pipeline": self._top_customers_pipeline,
                "answer_template": self._format_top_customers,
            },
            "low_stock": {
                "collection": "inventory",
                "pipeline": self._low_stock_pipeline,
                "answer_template": self._format_low_stock,
            },
            "returns": {
                "collection": "returns",
                "pipeline": self._returns_pipeline,
                "answer_template": "You had {count} returns {time_desc} totaling ${total:,.2f}",
            },
            "sales_by_category": {
                "collection": "order_items",
                "pipeline": self._sales_by_category_pipeline,
                "answer_template": self._format_category_sales,
            },
        }

    def get_template(self, kpi_name: str) -> Dict[str, Any]:
        """Get template for a specific KPI."""
        return self.templates.get(kpi_name)

    def _get_time_range(self, time_period: str) -> tuple:
        """Convert time period to date range."""
        now = datetime.utcnow()
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

        ranges = {
            "today": (today_start, now),
            "yesterday": (
                today_start - timedelta(days=1),
                today_start - timedelta(seconds=1),
            ),
            "this week": (
                now - timedelta(days=now.weekday()),
                now,
            ),
            "last week": (
                now - timedelta(days=now.weekday() + 7),
                now - timedelta(days=now.weekday()),
            ),
            "this month": (
                now.replace(day=1, hour=0, minute=0, second=0, microsecond=0),
                now,
            ),
            "last month": (
                (now.replace(day=1) - timedelta(days=1)).replace(day=1),
                now.replace(day=1) - timedelta(seconds=1),
            ),
        }

        return ranges.get(time_period, (now - timedelta(days=30), now))

    def _total_sales_pipeline(self, shop_id: str, params: Dict[str, Any]) -> List[Dict]:
        """Pipeline for total sales."""
        shop_id = self._get_shop_id_filter(shop_id)
        pipeline = [{"$match": {"shop_id": shop_id, "status": {"$in": ["completed", "processing"]}}}]

        if "time_period" in params:
            start, end = self._get_time_range(params["time_period"])
            pipeline[0]["$match"]["created_at"] = {"$gte": start, "$lte": end}

        pipeline.extend(
            [
                {"$group": {"_id": None, "total": {"$sum": "$total_amount"}}},
                {"$project": {"_id": 0, "total": 1}},
            ]
        )

        return pipeline

    def _order_count_pipeline(self, shop_id: str, params: Dict[str, Any]) -> List[Dict]:
        """Pipeline for order count."""
        shop_id = self._get_shop_id_filter(shop_id)
        pipeline = [{"$match": {"shop_id": shop_id}}]

        if "time_period" in params:
            start, end = self._get_time_range(params["time_period"])
            pipeline[0]["$match"]["created_at"] = {"$gte": start, "$lte": end}

        pipeline.append({"$count": "count"})

        return pipeline

    def _product_count_pipeline(self, shop_id: str, params: Dict[str, Any]) -> List[Dict]:
        """Pipeline for product count."""
        shop_id = self._get_shop_id_filter(shop_id)
        match_filter = {"shop_id": shop_id}

        if params.get("filter") == "active":
            match_filter["status"] = "active"
        elif params.get("filter") == "inactive":
            match_filter["status"] = "inactive"
        elif params.get("filter") == "in stock":
            match_filter["stock_quantity"] = {"$gt": 0}
        elif params.get("filter") == "out of stock":
            match_filter["stock_quantity"] = 0
        elif params.get("filter") == "low stock":
            match_filter["stock_quantity"] = {"$lte": 10, "$gt": 0}

        return [{"$match": match_filter}, {"$count": "count"}]

    def _customer_count_pipeline(self, shop_id: str, params: Dict[str, Any]) -> List[Dict]:
        """Pipeline for customer count."""
        shop_id = self._get_shop_id_filter(shop_id)
        match_filter = {"shop_id": shop_id}

        if params.get("filter") == "new":
            # Customers created in last 30 days
            match_filter["created_at"] = {"$gte": datetime.utcnow() - timedelta(days=30)}
        elif params.get("filter") == "active":
            # Customers with recent orders
            return [
                {"$match": {"shop_id": shop_id}},
                {
                    "$lookup": {
                        "from": "orders",
                        "let": {"customer_id": "$_id"},
                        "pipeline": [
                            {
                                "$match": {
                                    "$expr": {"$eq": ["$customer_id", "$$customer_id"]},
                                    "created_at": {"$gte": datetime.utcnow() - timedelta(days=90)},
                                }
                            }
                        ],
                        "as": "recent_orders",
                    }
                },
                {"$match": {"recent_orders": {"$ne": []}}},
                {"$count": "count"},
            ]

        return [{"$match": match_filter}, {"$count": "count"}]

    def _avg_order_pipeline(self, shop_id: str, params: Dict[str, Any]) -> List[Dict]:
        """Pipeline for average order value."""
        shop_id = self._get_shop_id_filter(shop_id)
        pipeline = [{"$match": {"shop_id": shop_id, "status": {"$in": ["completed", "processing"]}}}]

        if "time_period" in params:
            start, end = self._get_time_range(params["time_period"])
            pipeline[0]["$match"]["created_at"] = {"$gte": start, "$lte": end}

        pipeline.extend(
            [
                {"$group": {"_id": None, "avg": {"$avg": "$total_amount"}}},
                {"$project": {"_id": 0, "avg": 1}},
            ]
        )

        return pipeline

    def _top_products_pipeline(self, shop_id: str, params: Dict[str, Any]) -> List[Dict]:
        """Pipeline for top products."""
        shop_id = self._get_shop_id_filter(shop_id)
        limit = params.get("limit", 10)

        pipeline = [
            {"$match": {"shop_id": shop_id}},
            {
                "$group": {
                    "_id": "$product_id",
                    "product_name": {"$first": "$product_name"},
                    "quantity_sold": {"$sum": "$quantity"},
                    "revenue": {"$sum": {"$multiply": ["$quantity", "$price"]}},
                }
            },
            {"$sort": {"revenue": -1}},
            {"$limit": limit},
        ]

        return pipeline

    def _top_customers_pipeline(self, shop_id: str, params: Dict[str, Any]) -> List[Dict]:
        """Pipeline for top customers."""
        shop_id = self._get_shop_id_filter(shop_id)
        limit = params.get("limit", 10)

        pipeline = [
            {"$match": {"shop_id": shop_id, "status": {"$in": ["completed", "processing"]}}},
            {
                "$group": {
                    "_id": "$customer_id",
                    "customer_name": {"$first": "$customer_name"},
                    "order_count": {"$sum": 1},
                    "total_spent": {"$sum": "$total_amount"},
                }
            },
            {"$sort": {"total_spent": -1}},
            {"$limit": limit},
        ]

        return pipeline

    def _low_stock_pipeline(self, shop_id: str, params: Dict[str, Any]) -> List[Dict]:
        """Pipeline for low stock products."""
        shop_id = self._get_shop_id_filter(shop_id)
        return [
            {"$match": {"shop_id": shop_id, "stock_quantity": {"$lte": 10, "$gte": 0}}},
            {"$sort": {"stock_quantity": 1}},
            {"$limit": 20},
            {
                "$project": {
                    "product_name": 1,
                    "sku": 1,
                    "stock_quantity": 1,
                    "reorder_point": 1,
                }
            },
        ]

    def _returns_pipeline(self, shop_id: str, params: Dict[str, Any]) -> List[Dict]:
        """Pipeline for returns."""
        shop_id = self._get_shop_id_filter(shop_id)
        pipeline = [{"$match": {"shop_id": shop_id}}]

        if "time_period" in params:
            start, end = self._get_time_range(params["time_period"])
            pipeline[0]["$match"]["created_at"] = {"$gte": start, "$lte": end}

        pipeline.extend(
            [
                {
                    "$group": {
                        "_id": None,
                        "count": {"$sum": 1},
                        "total": {"$sum": "$refund_amount"},
                    }
                },
                {"$project": {"_id": 0, "count": 1, "total": 1}},
            ]
        )

        return pipeline

    def _sales_by_category_pipeline(self, shop_id: str, params: Dict[str, Any]) -> List[Dict]:
        """Pipeline for sales by category."""
        shop_id = self._get_shop_id_filter(shop_id)
        pipeline = [
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
                    "total_sales": {"$sum": {"$multiply": ["$quantity", "$price"]}},
                    "units_sold": {"$sum": "$quantity"},
                }
            },
            {"$sort": {"total_sales": -1}},
        ]

        return pipeline

    def _format_top_products(self, data: List[Dict]) -> str:
        """Format top products response."""
        if not data:
            return "No product sales data available."

        lines = ["Your top selling products are:\n"]
        for i, product in enumerate(data, 1):
            lines.append(
                f"{i}. {product['product_name']}: {product['quantity_sold']} units sold, "
                f"${product['revenue']:,.2f} in revenue"
            )

        return "\n".join(lines)

    def _format_top_customers(self, data: List[Dict]) -> str:
        """Format top customers response."""
        if not data:
            return "No customer data available."

        lines = ["Your top customers are:\n"]
        for i, customer in enumerate(data, 1):
            lines.append(
                f"{i}. {customer['customer_name']}: {customer['order_count']} orders, "
                f"${customer['total_spent']:,.2f} total spent"
            )

        return "\n".join(lines)

    def _format_low_stock(self, data: List[Dict]) -> str:
        """Format low stock response."""
        if not data:
            return "All products are well stocked."

        lines = ["The following products are low in stock:\n"]
        for product in data:
            status = "OUT OF STOCK" if product["stock_quantity"] == 0 else f"{product['stock_quantity']} units"
            lines.append(f"• {product['product_name']} (SKU: {product['sku']}): {status}")

        return "\n".join(lines)

    def _format_category_sales(self, data: List[Dict]) -> str:
        """Format category sales response."""
        if not data:
            return "No sales data by category available."

        lines = ["Sales breakdown by category:\n"]
        total = sum(cat["total_sales"] for cat in data)

        for cat in data:
            percentage = (cat["total_sales"] / total) * 100 if total > 0 else 0
            lines.append(
                f"• {cat['_id']}: ${cat['total_sales']:,.2f} ({percentage:.1f}%) - "
                f"{cat['units_sold']} units sold"
            )

        return "\n".join(lines)


# Global instance
kpi_templates = KPITemplates()
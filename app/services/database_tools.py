from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
import logging
from app.core.database import mongodb

logger = logging.getLogger(__name__)


class DatabaseTools:

    @staticmethod
    async def count_products(shop_id: int, status: Optional[str] = None) -> Dict[str, Any]:
        pipeline = [{"$match": {"shop_id": shop_id}}]

        if status:
            pipeline[0]["$match"]["status"] = status

        pipeline.append({"$count": "total"})

        result = await mongodb.execute_aggregation("product", pipeline)
        count = result[0]["total"] if result else 0

        return {
            "count": count,
            "shop_id": shop_id,
            "status": status,
            "collection": "product"
        }

    @staticmethod
    async def count_orders(
        shop_id: int,
        time_period: Optional[str] = None,
        status: Optional[str] = None
    ) -> Dict[str, Any]:
        match_filter = {"shop_id": shop_id}

        if time_period:
            date_filter = DatabaseTools._get_date_filter(time_period)
            if date_filter:
                match_filter["created_at"] = date_filter

        if status:
            match_filter["status"] = status

        pipeline = [
            {"$match": match_filter},
            {"$count": "total"}
        ]

        result = await mongodb.execute_aggregation("order", pipeline)
        count = result[0]["total"] if result else 0

        return {
            "count": count,
            "shop_id": shop_id,
            "time_period": time_period,
            "status": status,
            "collection": "order"
        }

    @staticmethod
    async def count_customers(shop_id: int, customer_type: Optional[str] = None) -> Dict[str, Any]:
        pipeline = [{"$match": {"shop_id": shop_id}}]

        if customer_type:
            pipeline[0]["$match"]["type"] = customer_type

        pipeline.append({"$count": "total"})

        result = await mongodb.execute_aggregation("customer", pipeline)
        count = result[0]["total"] if result else 0

        return {
            "count": count,
            "shop_id": shop_id,
            "customer_type": customer_type,
            "collection": "customer"
        }

    @staticmethod
    async def count_categories(shop_id: int) -> Dict[str, Any]:
        pipeline = [
            {"$match": {"shop_id": shop_id}},
            {"$count": "total"}
        ]

        result = await mongodb.execute_aggregation("category", pipeline)
        count = result[0]["total"] if result else 0

        return {
            "count": count,
            "shop_id": shop_id,
            "collection": "category"
        }

    @staticmethod
    async def total_revenue(
        shop_id: int,
        time_period: Optional[str] = None
    ) -> Dict[str, Any]:
        match_filter = {"shop_id": shop_id}

        if time_period:
            date_filter = DatabaseTools._get_date_filter(time_period)
            if date_filter:
                match_filter["created_at"] = date_filter

        pipeline = [
            {"$match": match_filter},
            {"$group": {
                "_id": None,
                "total": {"$sum": "$grand_total"},
                "count": {"$sum": 1},
                "average": {"$avg": "$grand_total"}
            }}
        ]

        result = await mongodb.execute_aggregation("order", pipeline)

        if result:
            return {
                "total_revenue": result[0]["total"],
                "order_count": result[0]["count"],
                "average_order_value": result[0]["average"],
                "shop_id": shop_id,
                "time_period": time_period,
                "collection": "order"
            }

        return {
            "total_revenue": 0,
            "order_count": 0,
            "average_order_value": 0,
            "shop_id": shop_id,
            "time_period": time_period,
            "collection": "order"
        }

    @staticmethod
    async def average_order_value(
        shop_id: int,
        time_period: Optional[str] = None
    ) -> Dict[str, Any]:
        revenue_data = await DatabaseTools.total_revenue(shop_id, time_period)

        return {
            "average_order_value": revenue_data["average_order_value"],
            "order_count": revenue_data["order_count"],
            "total_revenue": revenue_data["total_revenue"],
            "shop_id": shop_id,
            "time_period": time_period,
            "collection": "order"
        }

    @staticmethod
    async def top_products(
        shop_id: int,
        limit: int = 5,
        time_period: Optional[str] = None
    ) -> Dict[str, Any]:
        match_filter = {"shop_id": shop_id}

        if time_period:
            date_filter = DatabaseTools._get_date_filter(time_period)
            if date_filter:
                match_filter["created_at"] = date_filter

        pipeline = [
            {"$match": match_filter},
            {"$unwind": "$items"},
            {"$group": {
                "_id": "$items.product_id",
                "product_name": {"$first": "$items.product_name"},
                "quantity_sold": {"$sum": "$items.quantity"},
                "revenue": {"$sum": {"$multiply": ["$items.quantity", "$items.price"]}}
            }},
            {"$sort": {"quantity_sold": -1}},
            {"$limit": limit}
        ]

        result = await mongodb.execute_aggregation("order", pipeline)

        return {
            "top_products": result,
            "shop_id": shop_id,
            "limit": limit,
            "time_period": time_period,
            "collection": "order"
        }

    @staticmethod
    async def top_customers(
        shop_id: int,
        limit: int = 5,
        time_period: Optional[str] = None
    ) -> Dict[str, Any]:
        match_filter = {"shop_id": shop_id}

        if time_period:
            date_filter = DatabaseTools._get_date_filter(time_period)
            if date_filter:
                match_filter["created_at"] = date_filter

        pipeline = [
            {"$match": match_filter},
            {"$group": {
                "_id": "$user_id",
                "customer_name": {"$first": "$shipping_name"},
                "total_orders": {"$sum": 1},
                "total_spent": {"$sum": "$grand_total"}
            }},
            {"$sort": {"total_spent": -1}},
            {"$limit": limit}
        ]

        result = await mongodb.execute_aggregation("order", pipeline)

        return {
            "top_customers": result,
            "shop_id": shop_id,
            "limit": limit,
            "time_period": time_period,
            "collection": "order"
        }

    @staticmethod
    async def recent_orders(
        shop_id: int,
        limit: int = 10
    ) -> Dict[str, Any]:
        pipeline = [
            {"$match": {"shop_id": shop_id}},
            {"$sort": {"created_at": -1}},
            {"$limit": limit}
        ]

        result = await mongodb.execute_aggregation("order", pipeline)

        return {
            "orders": result,
            "count": len(result),
            "shop_id": shop_id,
            "limit": limit,
            "collection": "order"
        }

    @staticmethod
    async def sales_by_status(shop_id: int) -> Dict[str, Any]:
        pipeline = [
            {"$match": {"shop_id": shop_id}},
            {"$group": {
                "_id": "$status",
                "count": {"$sum": 1},
                "total_value": {"$sum": "$grand_total"}
            }},
            {"$sort": {"count": -1}}
        ]

        result = await mongodb.execute_aggregation("order", pipeline)

        return {
            "status_breakdown": result,
            "shop_id": shop_id,
            "collection": "order"
        }

    @staticmethod
    def _get_date_filter(time_period: str) -> Optional[Dict[str, Any]]:
        now = datetime.now()

        if time_period == "today":
            start = datetime(now.year, now.month, now.day)
            return {"$gte": start.isoformat()}

        elif time_period == "yesterday":
            start = datetime(now.year, now.month, now.day) - timedelta(days=1)
            end = datetime(now.year, now.month, now.day)
            return {"$gte": start.isoformat(), "$lt": end.isoformat()}

        elif time_period == "this week":
            start = now - timedelta(days=now.weekday())
            start = datetime(start.year, start.month, start.day)
            return {"$gte": start.isoformat()}

        elif time_period == "last week":
            end = now - timedelta(days=now.weekday())
            end = datetime(end.year, end.month, end.day)
            start = end - timedelta(days=7)
            return {"$gte": start.isoformat(), "$lt": end.isoformat()}

        elif time_period == "this month":
            start = datetime(now.year, now.month, 1)
            return {"$gte": start.isoformat()}

        elif time_period == "last month":
            if now.month == 1:
                start = datetime(now.year - 1, 12, 1)
                end = datetime(now.year, 1, 1)
            else:
                start = datetime(now.year, now.month - 1, 1)
                end = datetime(now.year, now.month, 1)
            return {"$gte": start.isoformat(), "$lt": end.isoformat()}

        elif time_period == "this year":
            start = datetime(now.year, 1, 1)
            return {"$gte": start.isoformat()}

        return None


database_tools = DatabaseTools()
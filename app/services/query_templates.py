"""
MongoDB Query Templates for Common Patterns
This provides reliable query generation without LLM hallucination
"""

from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta

class QueryTemplates:
    """Predefined MongoDB query templates for common patterns"""

    @staticmethod
    def count_with_filter(collection: str, shop_id: int, filters: Dict = None) -> Dict:
        """Count documents with optional filters"""
        match_stage = {"shop_id": shop_id}
        if filters:
            match_stage.update(filters)

        return {
            "collection": collection,
            "pipeline": [
                {"$match": match_stage},
                {"$count": "total"}
            ],
            "answer_template": f"Found {{total}} {collection}s"
        }

    @staticmethod
    def filter_with_comparison(collection: str, shop_id: int, field: str, operator: str, value: Any) -> Dict:
        """Filter with comparison operators (gt, lt, gte, lte, eq, ne)"""
        operators = {
            "greater": "$gt",
            "less": "$lt",
            "greater_equal": "$gte",
            "less_equal": "$lte",
            "equal": "$eq",
            "not_equal": "$ne"
        }

        mongo_op = operators.get(operator, "$eq")

        return {
            "collection": collection,
            "pipeline": [
                {"$match": {
                    "shop_id": shop_id,
                    field: {mongo_op: value}
                }},
                {"$limit": 100}
            ],
            "answer_template": f"Found {{count}} {collection}s where {field} {operator} {value}"
        }

    @staticmethod
    def group_and_count(collection: str, shop_id: int, group_field: str) -> Dict:
        """Group by field and count"""
        return {
            "collection": collection,
            "pipeline": [
                {"$match": {"shop_id": shop_id}},
                {"$group": {
                    "_id": f"${group_field}",
                    "count": {"$sum": 1}
                }},
                {"$sort": {"count": -1}}
            ],
            "answer_template": f"{collection}s grouped by {group_field}"
        }

    @staticmethod
    def top_n_by_field(collection: str, shop_id: int, sort_field: str, limit: int = 5, ascending: bool = False) -> Dict:
        """Get top N documents sorted by field"""
        sort_order = 1 if ascending else -1

        return {
            "collection": collection,
            "pipeline": [
                {"$match": {"shop_id": shop_id}},
                {"$sort": {sort_field: sort_order}},
                {"$limit": limit}
            ],
            "answer_template": f"Top {limit} {collection}s by {sort_field}"
        }

    @staticmethod
    def sum_field(collection: str, shop_id: int, sum_field: str, group_by: Optional[str] = None) -> Dict:
        """Sum a field with optional grouping"""
        pipeline = [{"$match": {"shop_id": shop_id}}]

        if group_by:
            pipeline.append({
                "$group": {
                    "_id": f"${group_by}",
                    "total": {"$sum": f"${sum_field}"},
                    "count": {"$sum": 1}
                }
            })
            answer = f"Total {sum_field} grouped by {group_by}"
        else:
            pipeline.append({
                "$group": {
                    "_id": None,
                    "total": {"$sum": f"${sum_field}"},
                    "count": {"$sum": 1}
                }
            })
            answer = f"Total {sum_field}: {{total}}"

        return {
            "collection": collection,
            "pipeline": pipeline,
            "answer_template": answer
        }

    @staticmethod
    def average_field(collection: str, shop_id: int, avg_field: str, group_by: Optional[str] = None) -> Dict:
        """Calculate average of a field"""
        pipeline = [{"$match": {"shop_id": shop_id}}]

        if group_by:
            pipeline.append({
                "$group": {
                    "_id": f"${group_by}",
                    "average": {"$avg": f"${avg_field}"},
                    "count": {"$sum": 1}
                }
            })
            answer = f"Average {avg_field} grouped by {group_by}"
        else:
            pipeline.append({
                "$group": {
                    "_id": None,
                    "average": {"$avg": f"${avg_field}"},
                    "count": {"$sum": 1}
                }
            })
            answer = f"Average {avg_field}: {{average}}"

        return {
            "collection": collection,
            "pipeline": pipeline,
            "answer_template": answer
        }

    @staticmethod
    def date_range_filter(collection: str, shop_id: int, date_field: str, days_back: int = 30) -> Dict:
        """Filter by date range"""
        date_threshold = datetime.utcnow() - timedelta(days=days_back)

        return {
            "collection": collection,
            "pipeline": [
                {"$match": {
                    "shop_id": shop_id,
                    date_field: {"$gte": date_threshold.isoformat()}
                }},
                {"$sort": {date_field: -1}},
                {"$limit": 100}
            ],
            "answer_template": f"{collection}s from last {days_back} days"
        }

    @staticmethod
    def multiple_conditions(collection: str, shop_id: int, conditions: List[Dict]) -> Dict:
        """Multiple filter conditions"""
        match_stage = {"shop_id": shop_id}

        for condition in conditions:
            field = condition.get("field")
            operator = condition.get("operator", "$eq")
            value = condition.get("value")

            if operator in ["$gt", "$lt", "$gte", "$lte", "$ne"]:
                match_stage[field] = {operator: value}
            else:
                match_stage[field] = value

        return {
            "collection": collection,
            "pipeline": [
                {"$match": match_stage},
                {"$limit": 100}
            ],
            "answer_template": f"Filtered {collection}s"
        }

    @staticmethod
    def customer_spending(shop_id: int, limit: int = 10) -> Dict:
        """Top customers by total spending"""
        return {
            "collection": "order",
            "pipeline": [
                {"$match": {"shop_id": shop_id}},
                {"$group": {
                    "_id": "$user_id",
                    "total_spent": {"$sum": "$grand_total"},
                    "order_count": {"$sum": 1},
                    "avg_order": {"$avg": "$grand_total"}
                }},
                {"$sort": {"total_spent": -1}},
                {"$limit": limit},
                {"$lookup": {
                    "from": "customer",
                    "localField": "_id",
                    "foreignField": "id",
                    "as": "customer_info"
                }}
            ],
            "answer_template": f"Top {limit} customers by spending"
        }

    @staticmethod
    def sales_by_period(shop_id: int, group_by: str = "month") -> Dict:
        """Sales grouped by time period"""
        date_format = {
            "day": "%Y-%m-%d",
            "week": "%Y-W%U",
            "month": "%Y-%m",
            "year": "%Y"
        }

        format_str = date_format.get(group_by, "%Y-%m")

        return {
            "collection": "order",
            "pipeline": [
                {"$match": {"shop_id": shop_id}},
                {"$group": {
                    "_id": {
                        "$dateToString": {
                            "format": format_str,
                            "date": {"$dateFromString": {"dateString": "$created_at"}}
                        }
                    },
                    "total_revenue": {"$sum": "$grand_total"},
                    "order_count": {"$sum": 1},
                    "avg_order": {"$avg": "$grand_total"}
                }},
                {"$sort": {"_id": -1}},
                {"$limit": 12}
            ],
            "answer_template": f"Sales by {group_by}"
        }


class SmartQueryBuilder:
    """
    Intelligent query builder that uses LLM for intent classification
    and templates for query generation
    """

    def __init__(self):
        self.templates = QueryTemplates()

    def parse_query_intent(self, question: str) -> Dict[str, Any]:
        """
        Parse the question to understand intent and extract parameters
        This can use a simple LLM or rule-based approach
        """
        question_lower = question.lower()

        # Detect intent patterns
        if "count" in question_lower:
            return {"intent": "count", "params": {}}

        elif any(word in question_lower for word in ["group", "by status", "by category"]):
            # Extract grouping field
            if "status" in question_lower:
                group_field = "status"
            elif "category" in question_lower:
                group_field = "category"
            elif "customer" in question_lower:
                group_field = "user_id"
            else:
                group_field = "status"  # default

            return {"intent": "group", "params": {"group_field": group_field}}

        elif any(word in question_lower for word in ["top", "best", "highest"]):
            # Extract number and field
            import re
            numbers = re.findall(r'\d+', question)
            limit = int(numbers[0]) if numbers else 5

            if "customer" in question_lower and "spending" in question_lower:
                return {"intent": "top_customers", "params": {"limit": limit}}
            else:
                return {"intent": "top_n", "params": {"limit": limit}}

        elif any(word in question_lower for word in ["greater than", "more than", "over", "above"]):
            # Extract field and value
            import re
            numbers = re.findall(r'\d+', question)
            value = int(numbers[0]) if numbers else 100

            if "grand_total" in question_lower or "total" in question_lower:
                field = "grand_total"
            elif "amount" in question_lower:
                field = "grand_total"
            else:
                field = "grand_total"

            return {"intent": "filter_comparison", "params": {
                "field": field,
                "operator": "greater",
                "value": value
            }}

        elif any(word in question_lower for word in ["sum", "total", "revenue"]):
            return {"intent": "sum", "params": {"field": "grand_total"}}

        elif any(word in question_lower for word in ["average", "avg", "mean"]):
            return {"intent": "average", "params": {"field": "grand_total"}}

        elif any(word in question_lower for word in ["last", "recent", "past"]):
            import re
            numbers = re.findall(r'\d+', question)
            days = int(numbers[0]) if numbers else 30
            return {"intent": "date_range", "params": {"days": days}}

        else:
            return {"intent": "unknown", "params": {}}

    def build_query(self, question: str, shop_id: int, collection: str = "order") -> Dict:
        """
        Build MongoDB query using intent and templates
        """
        intent_data = self.parse_query_intent(question)
        intent = intent_data["intent"]
        params = intent_data["params"]

        # Map intent to template
        if intent == "count":
            return self.templates.count_with_filter(collection, shop_id)

        elif intent == "group":
            return self.templates.group_and_count(
                collection, shop_id, params["group_field"]
            )

        elif intent == "top_customers":
            return self.templates.customer_spending(shop_id, params["limit"])

        elif intent == "top_n":
            return self.templates.top_n_by_field(
                collection, shop_id, "grand_total", params["limit"]
            )

        elif intent == "filter_comparison":
            return self.templates.filter_with_comparison(
                collection, shop_id,
                params["field"], params["operator"], params["value"]
            )

        elif intent == "sum":
            return self.templates.sum_field(
                collection, shop_id, params["field"]
            )

        elif intent == "average":
            return self.templates.average_field(
                collection, shop_id, params["field"]
            )

        elif intent == "date_range":
            return self.templates.date_range_filter(
                collection, shop_id, "created_at", params["days"]
            )

        else:
            # Default fallback
            return {
                "collection": collection,
                "pipeline": [
                    {"$match": {"shop_id": shop_id}},
                    {"$limit": 10}
                ],
                "answer_template": "Recent data"
            }


# Global instance
smart_query_builder = SmartQueryBuilder()
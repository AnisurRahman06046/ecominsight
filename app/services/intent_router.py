import re
from typing import Dict, Any, Optional, Callable, Tuple
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class Intent(Enum):
    PRODUCT_COUNT = "product_count"
    ORDER_COUNT = "order_count"
    CUSTOMER_COUNT = "customer_count"
    CATEGORY_COUNT = "category_count"
    TOTAL_REVENUE = "total_revenue"
    AVERAGE_ORDER_VALUE = "average_order_value"
    TOP_PRODUCTS = "top_products"
    TOP_CUSTOMERS = "top_customers"
    RECENT_ORDERS = "recent_orders"
    SALES_BY_STATUS = "sales_by_status"
    GREETING = "greeting"
    UNKNOWN = "unknown"


class IntentRouter:

    def __init__(self):
        self.intent_patterns = {
            Intent.PRODUCT_COUNT: [
                r"how many products",
                r"number of products",
                r"product count",
                r"total products",
                r"count.*products"
            ],
            Intent.ORDER_COUNT: [
                r"how many orders",
                r"number of orders",
                r"order count",
                r"total orders",
                r"count.*orders"
            ],
            Intent.CUSTOMER_COUNT: [
                r"how many customers",
                r"number of customers",
                r"customer count",
                r"total customers",
                r"count.*customers",
                r"count.*users"
            ],
            Intent.CATEGORY_COUNT: [
                r"how many categor",
                r"number of categor",
                r"category count",
                r"total categor",
                r"count.*categor"
            ],
            Intent.TOTAL_REVENUE: [
                r"total sales",
                r"total revenue",
                r"how much.*sold",
                r"sales total",
                r"revenue total"
            ],
            Intent.AVERAGE_ORDER_VALUE: [
                r"average order",
                r"avg order",
                r"mean order value",
                r"aov"
            ],
            Intent.TOP_PRODUCTS: [
                r"top.*products",
                r"best selling",
                r"most sold",
                r"popular products",
                r"top sellers"
            ],
            Intent.TOP_CUSTOMERS: [
                r"top.*customers",
                r"best customers",
                r"vip customers",
                r"highest spending",
                r"valuable customers"
            ],
            Intent.RECENT_ORDERS: [
                r"recent orders",
                r"latest orders",
                r"last.*orders",
                r"show.*orders"
            ],
            Intent.SALES_BY_STATUS: [
                r"sales by status",
                r"orders by status",
                r"status.*breakdown",
                r"order status"
            ],
            Intent.GREETING: [
                r"^(hi|hello|hey|greetings)",
                r"how are you",
                r"what's up"
            ]
        }

        self.time_period_pattern = r"(today|yesterday|this week|last week|this month|last month|this year)"
        self.limit_pattern = r"top (\d+)"
        self.status_pattern = r"(pending|completed|cancelled|shipped|delivered)"

    def classify(self, question: str) -> Tuple[Intent, Dict[str, Any]]:
        question_lower = question.lower().strip()

        for intent, patterns in self.intent_patterns.items():
            for pattern in patterns:
                if re.search(pattern, question_lower):
                    params = self._extract_params(question_lower, intent)
                    logger.info(f"Matched intent: {intent.value} with params: {params}")
                    return intent, params

        return Intent.UNKNOWN, {}

    def _extract_params(self, question: str, intent: Intent) -> Dict[str, Any]:
        params = {}

        time_match = re.search(self.time_period_pattern, question)
        if time_match:
            params["time_period"] = time_match.group(1)

        limit_match = re.search(self.limit_pattern, question)
        if limit_match:
            params["limit"] = int(limit_match.group(1))
        elif intent in [Intent.TOP_PRODUCTS, Intent.TOP_CUSTOMERS]:
            params["limit"] = 5

        status_match = re.search(self.status_pattern, question)
        if status_match:
            params["status"] = status_match.group(1)

        if "recent" in question or "latest" in question:
            if "limit" not in params:
                params["limit"] = 10

        return params


intent_router = IntentRouter()
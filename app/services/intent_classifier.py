"""Intent classification for determining query type."""

import re
from typing import Dict, Any, Optional, List, Tuple
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class IntentType(Enum):
    """Types of query intents."""

    KPI = "kpi"  # Known KPI query
    ANALYTICAL = "analytical"  # Why/how questions
    UNKNOWN = "unknown"  # Needs LLM


class IntentClassifier:
    """Classify user queries into intents."""

    def __init__(self):
        self.kpi_patterns = self._load_kpi_patterns()
        self.analytical_keywords = [
            "why",
            "how",
            "explain",
            "reason",
            "cause",
            "trend",
            "pattern",
            "analyze",
            "compare",
            "insight",
            "correlation",
            "forecast",
            "predict",
        ]

    def _load_kpi_patterns(self) -> Dict[str, Dict[str, Any]]:
        """Load predefined KPI patterns."""
        return {
            "total_sales": {
                "patterns": [
                    r"total sales",
                    r"revenue",
                    r"how much.*sold",
                    r"sales total",
                    r"total revenue",
                ],
                "time_patterns": [
                    r"(today|yesterday|this week|last week|this month|last month|this year)",
                ],
            },
            "order_count": {
                "patterns": [
                    r"how many orders",
                    r"number of orders",
                    r"order count",
                    r"total orders",
                    r"count.*orders",
                ],
                "time_patterns": [
                    r"(today|yesterday|this week|last week|this month|last month)",
                ],
            },
            "product_count": {
                "patterns": [
                    r"how many products",
                    r"number of products",
                    r"product count",
                    r"total products",
                    r"count.*products",
                ],
                "filters": [r"(active|inactive|in stock|out of stock|low stock)"],
            },
            "customer_count": {
                "patterns": [
                    r"how many customers",
                    r"number of customers",
                    r"customer count",
                    r"total customers",
                    r"count.*customers",
                ],
                "filters": [r"(new|returning|active|inactive)"],
            },
            "average_order_value": {
                "patterns": [
                    r"average order",
                    r"avg order",
                    r"mean order value",
                    r"aov",
                ],
                "time_patterns": [
                    r"(today|yesterday|this week|last week|this month|last month)",
                ],
            },
            "top_products": {
                "patterns": [
                    r"top \d+ products",
                    r"best selling",
                    r"most sold",
                    r"popular products",
                    r"top sellers",
                ],
                "limit_pattern": r"top (\d+)",
            },
            "top_customers": {
                "patterns": [
                    r"top \d+ customers",
                    r"best customers",
                    r"vip customers",
                    r"highest spending",
                    r"valuable customers",
                ],
                "limit_pattern": r"top (\d+)",
            },
            "low_stock": {
                "patterns": [
                    r"low.*stock",
                    r"out of stock",
                    r"inventory.*low",
                    r"need.*restock",
                    r"running out",
                ],
            },
            "returns": {
                "patterns": [
                    r"returns",
                    r"refund",
                    r"returned products",
                    r"return rate",
                ],
                "time_patterns": [
                    r"(today|yesterday|this week|last week|this month|last month)",
                ],
            },
            "sales_by_category": {
                "patterns": [
                    r"sales by category",
                    r"category.*revenue",
                    r"revenue.*category",
                    r"breakdown.*category",
                ],
            },
        }

    def classify(self, question: str) -> Tuple[IntentType, Optional[str], Dict[str, Any]]:
        """
        Classify the intent of a question.

        Returns:
            Tuple of (IntentType, kpi_name, extracted_params)
        """
        question_lower = question.lower()

        # Check if it's an analytical question
        if self._is_analytical(question_lower):
            return IntentType.ANALYTICAL, None, {}

        # Check for KPI matches
        kpi_match = self._match_kpi(question_lower)
        if kpi_match:
            kpi_name, params = kpi_match
            return IntentType.KPI, kpi_name, params

        # Default to unknown (needs LLM)
        return IntentType.UNKNOWN, None, {}

    def _is_analytical(self, question: str) -> bool:
        """Check if question is analytical."""
        # Don't classify as analytical if it matches KPI patterns
        if any(pattern in question for patterns in self.kpi_patterns.values() for pattern in patterns.get("patterns", [])):
            return False

        for keyword in self.analytical_keywords:
            # More strict matching - check for word boundaries
            if f" {keyword} " in f" {question} " or question.startswith(f"{keyword} "):
                return True
        return False

    def _match_kpi(self, question: str) -> Optional[Tuple[str, Dict[str, Any]]]:
        """Match question against KPI patterns."""
        for kpi_name, kpi_config in self.kpi_patterns.items():
            # Check main patterns
            for pattern in kpi_config["patterns"]:
                if re.search(pattern, question):
                    params = {}

                    # Extract time period
                    if "time_patterns" in kpi_config:
                        for time_pattern in kpi_config["time_patterns"]:
                            match = re.search(time_pattern, question)
                            if match:
                                params["time_period"] = match.group(1)
                                break

                    # Extract filters
                    if "filters" in kpi_config:
                        for filter_pattern in kpi_config["filters"]:
                            match = re.search(filter_pattern, question)
                            if match:
                                params["filter"] = match.group(1)
                                break

                    # Extract limit (for top N queries)
                    if "limit_pattern" in kpi_config:
                        match = re.search(kpi_config["limit_pattern"], question)
                        if match:
                            params["limit"] = int(match.group(1))
                        else:
                            params["limit"] = 10  # default

                    logger.info(f"Matched KPI: {kpi_name} with params: {params}")
                    return kpi_name, params

        return None

    def get_kpi_info(self, kpi_name: str) -> Optional[Dict[str, Any]]:
        """Get information about a specific KPI."""
        return self.kpi_patterns.get(kpi_name)


# Global instance
intent_classifier = IntentClassifier()
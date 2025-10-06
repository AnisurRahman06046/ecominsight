"""
HuggingFace Parameter Extractor Service
Uses local HuggingFace models to extract MongoDB query parameters from natural language.
Lightweight and doesn't require Ollama.
"""

import logging
import json
import re
from typing import Dict, Any, Optional
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class HFParameterExtractor:
    """
    Extracts structured query parameters using rule-based + NLP approach.
    Since full LLM parameter extraction is heavy, we use:
    1. Fast rule-based extraction for dates and common patterns
    2. NER models for entity extraction (optional, future enhancement)
    """

    def __init__(self):
        self.initialized = True
        logger.info("HF Parameter Extractor initialized")

    def extract_parameters(
        self,
        query: str,
        tool_name: str,
        basic_params: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Extract parameters from query using rule-based NLP.

        Args:
            query: User's natural language query
            tool_name: Tool selected by semantic router
            basic_params: Basic parameters already extracted by semantic router

        Returns:
            Enhanced parameters with filters and additional fields
        """
        # Start with basic params if provided
        params = basic_params.copy() if basic_params else {}

        try:
            query_lower = query.lower()

            # Extract date/time filters
            date_filter = self._extract_date_filter(query_lower)
            if date_filter:
                if "filters" not in params:
                    params["filters"] = {}
                params["filters"]["created_at"] = date_filter
                logger.info(f"Extracted date filter: {date_filter}")

            # Extract status filters
            status_filter = self._extract_status_filter(query_lower)
            if status_filter:
                if "filters" not in params:
                    params["filters"] = {}
                params["filters"].update(status_filter)
                logger.info(f"Extracted status filter: {status_filter}")

            # Extract numeric filters (amounts, thresholds)
            numeric_filter = self._extract_numeric_filter(query_lower)
            if numeric_filter:
                if "filters" not in params:
                    params["filters"] = {}
                params["filters"].update(numeric_filter)
                logger.info(f"Extracted numeric filter: {numeric_filter}")

            # Validate and set defaults
            params = self._validate_parameters(params, tool_name)

            logger.info(f"Final extracted parameters: {json.dumps(params, default=str)}")
            return params

        except Exception as e:
            logger.error(f"Parameter extraction failed: {e}")
            return params

    def _extract_date_filter(self, query: str) -> Optional[Dict[str, Any]]:
        """Extract date/time filters from query."""
        now = datetime.utcnow()

        # This month
        if any(phrase in query for phrase in ["this month", "current month"]):
            start_of_month = datetime(now.year, now.month, 1)
            return {"$gte": start_of_month}

        # Last month
        if "last month" in query or "previous month" in query:
            if now.month == 1:
                start_of_last_month = datetime(now.year - 1, 12, 1)
                start_of_this_month = datetime(now.year, 1, 1)
            else:
                start_of_last_month = datetime(now.year, now.month - 1, 1)
                start_of_this_month = datetime(now.year, now.month, 1)
            return {"$gte": start_of_last_month, "$lt": start_of_this_month}

        # This year
        if any(phrase in query for phrase in ["this year", "current year"]):
            start_of_year = datetime(now.year, 1, 1)
            return {"$gte": start_of_year}

        # Last year
        if "last year" in query or "previous year" in query:
            start_of_last_year = datetime(now.year - 1, 1, 1)
            start_of_this_year = datetime(now.year, 1, 1)
            return {"$gte": start_of_last_year, "$lt": start_of_this_year}

        # Today
        if "today" in query:
            start_of_today = datetime(now.year, now.month, now.day)
            return {"$gte": start_of_today}

        # Yesterday
        if "yesterday" in query:
            yesterday = now - timedelta(days=1)
            start_of_yesterday = datetime(yesterday.year, yesterday.month, yesterday.day)
            start_of_today = datetime(now.year, now.month, now.day)
            return {"$gte": start_of_yesterday, "$lt": start_of_today}

        # Last N days
        days_match = re.search(r'last (\d+) days?', query)
        if days_match:
            days = int(days_match.group(1))
            start_date = now - timedelta(days=days)
            return {"$gte": start_date}

        # Last week
        if "last week" in query or "past week" in query:
            start_date = now - timedelta(days=7)
            return {"$gte": start_date}

        # This week
        if "this week" in query:
            days_since_monday = now.weekday()
            start_of_week = now - timedelta(days=days_since_monday)
            start_of_week = datetime(start_of_week.year, start_of_week.month, start_of_week.day)
            return {"$gte": start_of_week}

        # Specific month (e.g., "October 2025", "in September")
        month_year_match = re.search(r'(january|february|march|april|may|june|july|august|september|october|november|december)\s+(\d{4})', query)
        if month_year_match:
            month_names = {
                'january': 1, 'february': 2, 'march': 3, 'april': 4,
                'may': 5, 'june': 6, 'july': 7, 'august': 8,
                'september': 9, 'october': 10, 'november': 11, 'december': 12
            }
            month = month_names[month_year_match.group(1)]
            year = int(month_year_match.group(2))
            start_of_month = datetime(year, month, 1)

            # Calculate next month
            if month == 12:
                end_of_month = datetime(year + 1, 1, 1)
            else:
                end_of_month = datetime(year, month + 1, 1)

            return {"$gte": start_of_month, "$lt": end_of_month}

        # Specific month (e.g., "in October", "during September")
        month_match = re.search(r'\b(in|during)\s+(january|february|march|april|may|june|july|august|september|october|november|december)', query)
        if month_match:
            month_names = {
                'january': 1, 'february': 2, 'march': 3, 'april': 4,
                'may': 5, 'june': 6, 'july': 7, 'august': 8,
                'september': 9, 'october': 10, 'november': 11, 'december': 12
            }
            month = month_names[month_match.group(2)]
            # Assume current year
            year = now.year
            start_of_month = datetime(year, month, 1)

            if month == 12:
                end_of_month = datetime(year + 1, 1, 1)
            else:
                end_of_month = datetime(year, month + 1, 1)

            return {"$gte": start_of_month, "$lt": end_of_month}

        # Specific year (e.g., "in 2024", "during 2023")
        year_match = re.search(r'\b(in|during|for)\s+(20\d{2})\b', query)
        if year_match:
            year = int(year_match.group(2))
            start_of_year = datetime(year, 1, 1)
            end_of_year = datetime(year + 1, 1, 1)
            return {"$gte": start_of_year, "$lt": end_of_year}

        return None

    def _extract_status_filter(self, query: str) -> Optional[Dict[str, Any]]:
        """Extract status filters from query."""
        filters = {}

        # Order status
        if "pending" in query and "payment" not in query:
            filters["status"] = "pending"
        elif "confirmed" in query:
            filters["status"] = "confirmed"
        elif "delivered" in query:
            filters["status"] = "delivered"
        elif "cancelled" in query or "canceled" in query:
            filters["status"] = "canceled"

        # Payment status
        if "paid" in query and "unpaid" not in query:
            filters["payment_status"] = "paid"
        elif "unpaid" in query:
            filters["payment_status"] = "unpaid"
        elif "pending payment" in query:
            filters["payment_status"] = "pending"

        return filters if filters else None

    def _extract_numeric_filter(self, query: str) -> Optional[Dict[str, Any]]:
        """Extract numeric filters (amounts, thresholds)."""
        filters = {}

        # Greater than patterns
        gt_patterns = [
            r'more than \$?(\d+)',
            r'greater than \$?(\d+)',
            r'over \$?(\d+)',
            r'above \$?(\d+)',
            r'>\s*\$?(\d+)'
        ]

        for pattern in gt_patterns:
            match = re.search(pattern, query)
            if match:
                value = float(match.group(1))
                # Determine field based on context
                if any(word in query for word in ["delivery", "charge", "shipping"]):
                    filters["delivery_charge"] = {"$gt": value}
                elif any(word in query for word in ["spent", "spending", "revenue", "total", "amount"]):
                    # This is likely for aggregation, not filtering
                    # Skip for now
                    pass
                else:
                    filters["grand_total"] = {"$gt": value}
                break

        # Less than patterns
        lt_patterns = [
            r'less than \$?(\d+)',
            r'under \$?(\d+)',
            r'below \$?(\d+)',
            r'<\s*\$?(\d+)'
        ]

        for pattern in lt_patterns:
            match = re.search(pattern, query)
            if match:
                value = float(match.group(1))
                if any(word in query for word in ["delivery", "charge", "shipping"]):
                    filters["delivery_charge"] = {"$lt": value}
                else:
                    filters["grand_total"] = {"$lt": value}
                break

        # Between pattern
        between_match = re.search(r'between \$?(\d+) and \$?(\d+)', query)
        if between_match:
            min_val = float(between_match.group(1))
            max_val = float(between_match.group(2))
            filters["grand_total"] = {"$gte": min_val, "$lte": max_val}

        return filters if filters else None

    def _validate_parameters(self, params: Dict[str, Any], tool_name: str) -> Dict[str, Any]:
        """Validate and set defaults for parameters."""

        # Ensure collection is set
        if "collection" not in params:
            if tool_name in ["get_best_selling_products"]:
                params["collection"] = "product"
            elif tool_name in ["get_top_customers_by_spending"]:
                params["collection"] = "customer"
            else:
                params["collection"] = "order"

        # Ensure filters is a dict
        if "filters" not in params:
            params["filters"] = {}
        elif not isinstance(params["filters"], dict):
            params["filters"] = {}

        # Set default limits
        if "limit" not in params:
            if tool_name in ["get_top_customers_by_spending", "get_best_selling_products"]:
                params["limit"] = 10
            elif tool_name == "find_documents":
                params["limit"] = 10

        # Set default fields for sum/avg
        if tool_name == "calculate_sum" and "sum_field" not in params:
            params["sum_field"] = "grand_total"

        if tool_name == "calculate_average" and "avg_field" not in params:
            params["avg_field"] = "grand_total"

        # Set default group_by
        if tool_name == "group_and_count" and "group_by" not in params:
            params["group_by"] = "status"

        return params


# Global instance
hf_parameter_extractor = HFParameterExtractor()

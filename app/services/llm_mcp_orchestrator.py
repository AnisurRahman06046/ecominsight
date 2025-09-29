"""
LLM MCP Orchestrator
Uses LLM to decide which MCP tools to call based on natural language queries
"""

import json
import logging
from typing import Dict, Any, Optional
import httpx

from app.core.config import settings
from app.services.mongodb_mcp_service import mongodb_mcp

logger = logging.getLogger(__name__)


class LLMMCPOrchestrator:
    """
    Orchestrates MCP tool calls using LLM for decision making.
    Instead of generating MongoDB queries, the LLM chooses tools to call.
    """

    def __init__(self):
        self.base_url = settings.ollama_host
        self.model = settings.ollama_model
        self.client = httpx.AsyncClient(timeout=30)

    async def process_query(self, question: str, shop_id: int) -> Dict[str, Any]:
        """
        Process a natural language query using MCP tools.

        Args:
            question: User's natural language question
            shop_id: Shop ID for filtering

        Returns:
            Dict with answer and data
        """
        try:
            # FIRST: Try keyword-based tool selection (more reliable)
            tool_decision = self._keyword_tool_selection(question)

            # ONLY if keyword matching fails completely, try LLM
            if not tool_decision or tool_decision.get("confidence", 0) < 0.3:
                logger.info("Keyword matching uncertain, trying LLM")
                tool_decision = await self._get_tool_decision(question, shop_id)

            if not tool_decision or not tool_decision.get("tool"):
                return {
                    "success": False,
                    "error": "Could not determine appropriate tool"
                }

            # Execute the chosen tool
            result = await self._execute_tool(tool_decision, shop_id)

            # Format the answer
            if result.get("success"):
                answer = self._format_answer(result, tool_decision, question)
                return {
                    "success": True,
                    "answer": answer,
                    "data": result.get("documents") or result.get("result") or result.get("groups") or result.get("customers"),
                    "metadata": {
                        "tool_used": tool_decision["tool"],
                        "parameters": tool_decision.get("parameters", {})
                    }
                }
            else:
                return {
                    "success": False,
                    "error": result.get("error", "Tool execution failed")
                }

        except Exception as e:
            logger.error(f"MCP query processing failed: {e}")
            return {
                "success": False,
                "error": str(e)
            }

    async def _get_tool_decision(self, question: str, shop_id: int) -> Dict[str, Any]:
        """
        Use LLM to decide which tool to use and with what parameters.
        """
        # Simplified prompt that's easier for LLMs to handle
        prompt = f"""Choose a MongoDB tool for this question: "{question}"

Tools:
- count_documents: count items
- find_documents: search and list items
- group_and_count: group by field and count
- calculate_sum: sum a numeric field
- calculate_average: average a numeric field
- get_top_customers_by_spending: top customers by spending

Return JSON:
{{
  "tool": "tool_name",
  "parameters": {{
    "collection": "order",
    "filter": {{}},
    "sort_by": "field_name",
    "group_by": "field_name",
    "sum_field": "field_name",
    "limit": 10
  }}
}}

Example for "how many orders": {{"tool": "count_documents", "parameters": {{"collection": "order"}}}}
Example for "total revenue": {{"tool": "calculate_sum", "parameters": {{"collection": "order", "sum_field": "grand_total"}}}}
"""

        try:
            response = await self.client.post(
                f"{self.base_url}/api/generate",
                json={
                    "model": self.model,
                    "prompt": prompt,
                    "stream": False,
                    "format": "json",
                    "temperature": 0.1
                }
            )
            response.raise_for_status()
            result = response.json()

            # Parse the response
            generated_text = result.get("response", "{}").strip()

            # Clean up response
            if "```json" in generated_text:
                start = generated_text.find("```json") + 7
                end = generated_text.find("```", start)
                generated_text = generated_text[start:end].strip()
            elif "```" in generated_text:
                start = generated_text.find("```") + 3
                end = generated_text.find("```", start)
                generated_text = generated_text[start:end].strip()

            tool_decision = json.loads(generated_text)
            logger.info(f"LLM tool decision: {tool_decision}")
            return tool_decision

        except Exception as e:
            logger.error(f"Failed to get tool decision: {e}")
            # Fallback to keyword-based tool selection
            return self._keyword_tool_selection(question)

    def _extract_filters(self, question: str) -> Dict[str, Any]:
        """
        Extract filter conditions from natural language.
        """
        import re
        filters = {}
        question_lower = question.lower()

        # Extract comparison operators
        # Greater than patterns
        gt_patterns = [
            r'more than (\d+)',
            r'greater than (\d+)',
            r'over (\d+)',
            r'above (\d+)',
            r'>\s*(\d+)'
        ]

        # Less than patterns
        lt_patterns = [
            r'less than (\d+)',
            r'under (\d+)',
            r'below (\d+)',
            r'<\s*(\d+)'
        ]

        # Between patterns
        between_pattern = r'between (\d+) and (\d+)'

        # Check for amount/price fields - but exclude aggregation queries
        if any(word in question_lower for word in ['price', 'amount', 'total', 'value', 'delivery charge', 'charge']) and \
           not any(word in question_lower for word in ['total revenue', 'total sales', 'sum']):
            field = 'grand_total'  # default
            if 'delivery' in question_lower:
                field = 'delivery_charge'
            elif 'subtotal' in question_lower:
                field = 'subtotal'

            for pattern in gt_patterns:
                match = re.search(pattern, question_lower)
                if match:
                    filters[field] = {"$gt": float(match.group(1))}
                    break

            for pattern in lt_patterns:
                match = re.search(pattern, question_lower)
                if match:
                    filters[field] = {"$lt": float(match.group(1))}
                    break

            match = re.search(between_pattern, question_lower)
            if match:
                filters[field] = {
                    "$gte": float(match.group(1)),
                    "$lte": float(match.group(2))
                }

        # Extract status filters
        if 'pending' in question_lower:
            filters['status'] = 'Pending'
        elif 'confirmed' in question_lower:
            filters['status'] = 'Confirmed'
        elif 'delivered' in question_lower:
            filters['status'] = 'Delivered'
        elif 'canceled' in question_lower or 'cancelled' in question_lower:
            filters['status'] = 'Canceled'

        # Extract payment status
        if 'paid' in question_lower and 'unpaid' not in question_lower:
            filters['payment_status'] = 'paid'
        elif 'unpaid' in question_lower:
            filters['payment_status'] = 'unpaid'

        return filters

    def _keyword_tool_selection(self, question: str) -> Dict[str, Any]:
        """
        Enhanced keyword-based tool selection with confidence scoring.
        Returns tool decision with confidence level.
        """
        question_lower = question.lower()

        # Extract filters that might be needed
        extracted_filters = self._extract_filters(question)

        # HIGH CONFIDENCE (0.9) - Very specific patterns

        # Count queries - be very specific
        if any(phrase in question_lower for phrase in ["how many", "number of", "count of"]):
            confidence = 0.9
            if "product" in question_lower:
                return {"tool": "count_documents", "parameters": {"collection": "product"}, "confidence": confidence}
            elif "customer" in question_lower:
                return {"tool": "count_documents", "parameters": {"collection": "customer"}, "confidence": confidence}
            elif "order" in question_lower:
                return {"tool": "count_documents", "parameters": {"collection": "order"}, "confidence": confidence}
            elif "categor" in question_lower:  # catches category/categories
                return {"tool": "count_documents", "parameters": {"collection": "category"}, "confidence": confidence}
            else:
                # Default to orders with lower confidence
                return {"tool": "count_documents", "parameters": {"collection": "order"}, "confidence": 0.6}

        # Revenue/Sum queries - very specific
        if any(phrase in question_lower for phrase in ["total revenue", "total sales", "sum of", "total amount", "revenue"]):
            return {
                "tool": "calculate_sum",
                "parameters": {
                    "collection": "order",
                    "sum_field": "grand_total"
                },
                "confidence": 0.95
            }

        # Average queries
        if any(word in question_lower for word in ["average", "avg", "mean"]):
            field = "grand_total"
            if "order" in question_lower or "value" in question_lower:
                field = "grand_total"
            return {
                "tool": "calculate_average",
                "parameters": {
                    "collection": "order",
                    "avg_field": field
                },
                "confidence": 0.9
            }

        # Top customers by spending - very specific
        if ("top" in question_lower or "best" in question_lower) and "customer" in question_lower and any(word in question_lower for word in ["spending", "spent", "revenue", "purchase"]):
            limit = 5
            # Extract number if present
            import re
            numbers = re.findall(r'\d+', question_lower)
            if numbers:
                limit = int(numbers[0])
            return {
                "tool": "get_top_customers_by_spending",
                "parameters": {"limit": limit},
                "confidence": 0.95
            }

        # Product sales analysis - best selling products
        if ("best" in question_lower or "top" in question_lower or "most" in question_lower) and any(word in question_lower for word in ["selling", "sold", "popular"]) and "product" in question_lower:
            limit = 10
            # Extract number if present
            import re
            numbers = re.findall(r'\d+', question_lower)
            if numbers:
                limit = int(numbers[0])
            return {
                "tool": "get_best_selling_products",
                "parameters": {"limit": limit},
                "confidence": 0.95
            }

        # Group by queries - check for specific group keywords
        if any(phrase in question_lower for phrase in ["group", "breakdown", "distribution", "by status", "by category"]):
            group_field = "status"  # default
            collection = "order"  # default

            if "status" in question_lower:
                group_field = "status"
                collection = "order"
            elif "category" in question_lower:
                group_field = "category_id"
                collection = "product" if "product" in question_lower else "order"
            elif "customer" in question_lower:
                group_field = "user_id"
                collection = "order"
            elif "date" in question_lower or "month" in question_lower:
                group_field = "created_at"
                collection = "order"

            return {
                "tool": "group_and_count",
                "parameters": {
                    "collection": collection,
                    "group_by": group_field
                },
                "confidence": 0.85
            }

        # MEDIUM CONFIDENCE (0.6) - Less specific patterns

        # List/Find queries WITH FILTERS - also check for filter keywords
        if any(word in question_lower for word in ["list", "show", "find", "get", "display", "orders with", "products with"]) or \
           (extracted_filters and any(word in question_lower for word in ["order", "product", "customer"])):
            collection = "order"
            confidence = 0.6

            if "product" in question_lower:
                collection = "product"
                confidence = 0.7
            elif "customer" in question_lower:
                collection = "customer"
                confidence = 0.7
            elif "order" in question_lower:
                collection = "order"
                confidence = 0.7
            elif "categor" in question_lower:
                collection = "category"
                confidence = 0.7

            # Recent/Latest modifiers
            sort_by = None
            if "recent" in question_lower or "latest" in question_lower:
                sort_by = "created_at"
                confidence += 0.1

            # If we have filters, increase confidence
            if extracted_filters:
                confidence = 0.85

            params = {
                "collection": collection,
                "limit": 10
            }

            if sort_by:
                params["sort_by"] = sort_by
                params["sort_order"] = -1

            if extracted_filters:
                params["filter"] = extracted_filters

            return {
                "tool": "find_documents",
                "parameters": params,
                "confidence": confidence
            }

        # Date range queries
        if any(word in question_lower for word in ["last", "past", "recent", "today", "yesterday", "this week", "this month"]):
            days = 7  # default
            confidence = 0.7

            if "today" in question_lower:
                days = 1
                confidence = 0.9
            elif "yesterday" in question_lower:
                days = 2
                confidence = 0.9
            elif "week" in question_lower:
                days = 7
                confidence = 0.85
            elif "month" in question_lower:
                days = 30
                confidence = 0.85
            elif "year" in question_lower:
                days = 365
                confidence = 0.85

            return {
                "tool": "get_date_range",
                "parameters": {
                    "collection": "order",
                    "date_field": "created_at",
                    "days_back": days
                },
                "confidence": confidence
            }

        # LOW CONFIDENCE (0.3) - Default fallback

        # Try to guess collection from context
        collection = "order"  # default
        if "product" in question_lower:
            collection = "product"
        elif "customer" in question_lower:
            collection = "customer"
        elif "categor" in question_lower:
            collection = "category"

        return {
            "tool": "find_documents",
            "parameters": {
                "collection": collection,
                "limit": 10
            },
            "confidence": 0.3
        }

    async def _execute_tool(self, tool_decision: Dict[str, Any], shop_id: int) -> Dict[str, Any]:
        """
        Execute the chosen MCP tool with parameters.
        """
        tool_name = tool_decision.get("tool")
        params = tool_decision.get("parameters", {})

        # Tool name mapping to handle LLM variations
        tool_map = {
            "get_top_customer_by_spending": "get_top_customers_by_spending",
            "get_top_customer": "get_top_customers_by_spending",
            "top_customers": "get_top_customers_by_spending",
            "sum_field": "calculate_sum",
            "average_field": "calculate_average",
            "count": "count_documents",
            "find": "find_documents",
            "group": "group_and_count"
        }
        tool_name = tool_map.get(tool_name, tool_name)

        # Validate and fix common parameter issues
        # Fix limit parameter
        if "limit" in params:
            limit = params["limit"]
            if isinstance(limit, str):
                limit = limit.strip()
                params["limit"] = int(limit) if limit.isdigit() else 10
            elif not isinstance(limit, int):
                params["limit"] = 10
            elif limit <= 0:
                params["limit"] = 10

        # Fix sort_order parameter
        if "sort_order" in params:
            sort_order = params["sort_order"]
            if isinstance(sort_order, str):
                if "desc" in sort_order.lower() or "-" in sort_order:
                    params["sort_order"] = -1
                else:
                    params["sort_order"] = 1
            elif not isinstance(sort_order, int):
                params["sort_order"] = -1

        try:
            if tool_name == "count_documents":
                return await mongodb_mcp.count_documents(
                    collection=params.get("collection", "order"),
                    shop_id=shop_id,
                    filter=params.get("filter", {})
                )

            elif tool_name == "find_documents":
                return await mongodb_mcp.find_documents(
                    collection=params.get("collection", "order"),
                    shop_id=shop_id,
                    filter=params.get("filter", {}),
                    sort_by=params.get("sort_by"),
                    sort_order=params.get("sort_order", -1),
                    limit=params.get("limit", 10)
                )

            elif tool_name == "group_and_count":
                # Validate and provide defaults for group_by
                group_by = params.get("group_by", "")

                # Handle both string and list types
                if isinstance(group_by, list):
                    # If it's a list, take the first field or use default
                    group_by = group_by[0] if group_by else "status"
                    logger.info(f"group_by was a list, using first field: {group_by}")
                elif isinstance(group_by, str):
                    # If string, check if empty
                    if not group_by or group_by.strip() == "":
                        # Provide sensible defaults based on collection
                        collection = params.get("collection", "order")
                        if collection == "order":
                            group_by = "status"
                        elif collection == "product":
                            group_by = "category_id"
                        elif collection == "customer":
                            group_by = "status"
                        else:
                            group_by = "status"
                        logger.info(f"Using default group_by: {group_by} for collection: {collection}")
                else:
                    # Neither string nor list, use default
                    group_by = "status"
                    logger.warning(f"Unexpected group_by type: {type(group_by)}, using default")

                return await mongodb_mcp.group_and_count(
                    collection=params.get("collection", "order"),
                    shop_id=shop_id,
                    group_by=group_by,
                    filter=params.get("filter", {})
                )

            elif tool_name == "calculate_sum":
                return await mongodb_mcp.calculate_sum(
                    collection=params.get("collection", "order"),
                    shop_id=shop_id,
                    sum_field=params.get("sum_field", "grand_total"),
                    group_by=params.get("group_by"),
                    filter=params.get("filter", {})
                )

            elif tool_name == "calculate_average":
                return await mongodb_mcp.calculate_average(
                    collection=params.get("collection", "order"),
                    shop_id=shop_id,
                    avg_field=params.get("avg_field", "grand_total"),
                    group_by=params.get("group_by"),
                    filter=params.get("filter", {})
                )

            elif tool_name == "get_top_n":
                return await mongodb_mcp.get_top_n(
                    collection=params.get("collection", "order"),
                    shop_id=shop_id,
                    sort_by=params.get("sort_by", "grand_total"),
                    n=params.get("limit", 5),
                    ascending=params.get("ascending", False),
                    filter=params.get("filter", {})
                )

            elif tool_name == "get_date_range":
                return await mongodb_mcp.get_date_range(
                    collection=params.get("collection", "order"),
                    shop_id=shop_id,
                    date_field=params.get("date_field", "created_at"),
                    days_back=params.get("days_back", 7),
                    filter=params.get("filter", {})
                )

            elif tool_name == "get_best_selling_products":
                return await mongodb_mcp.get_best_selling_products(
                    shop_id=shop_id,
                    limit=params.get("limit", 10),
                    filter=params.get("filter", {})
                )

            elif tool_name == "get_top_customers_by_spending":
                return await mongodb_mcp.get_top_customers_by_spending(
                    shop_id=shop_id,
                    limit=params.get("limit", 10),
                    filter=params.get("filter", {})
                )

            else:
                logger.warning(f"Unknown tool: {tool_name}")
                return {
                    "success": False,
                    "error": f"Unknown tool: {tool_name}"
                }

        except Exception as e:
            logger.error(f"Tool execution failed: {e}")
            return {
                "success": False,
                "error": str(e)
            }

    def _format_answer(self, result: Dict[str, Any], tool_decision: Dict[str, Any], question: str) -> str:
        """
        Format the result into a natural language answer.
        """
        tool_name = tool_decision.get("tool")

        if tool_name == "count_documents":
            count = result.get("count", 0)
            collection = tool_decision.get("parameters", {}).get("collection", "items")
            return f"You have {count} {collection}s."

        elif tool_name == "find_documents":
            count = result.get("count", 0)
            collection = tool_decision.get("parameters", {}).get("collection", "items")
            return f"Found {count} {collection}s matching your criteria."

        elif tool_name == "group_and_count":
            groups = result.get("groups", [])
            if groups:
                summary = ", ".join([f"{g['_id']}: {g['count']}" for g in groups[:5]])
                return f"Grouped results: {summary}"
            return "No groups found."

        elif tool_name == "calculate_sum":
            results = result.get("result", [])
            if results and len(results) > 0:
                total = results[0].get("total", 0)
                return f"Total: ${total:,.2f}"
            return "Could not calculate sum."

        elif tool_name == "calculate_average":
            results = result.get("result", [])
            if results and len(results) > 0:
                avg = results[0].get("average", 0)
                return f"Average: ${avg:,.2f}"
            return "Could not calculate average."

        elif tool_name == "get_best_selling_products":
            products = result.get("products", [])
            if products:
                top_list = []
                for i, p in enumerate(products[:10], 1):
                    name = p.get("name", f"Product {p.get('product_id', 'Unknown')}")
                    quantity = p.get("total_quantity", 0)
                    revenue = p.get("total_revenue", 0)
                    top_list.append(f"{i}. {name}: {quantity} sold (${revenue:,.2f})")
                return "Best selling products:\n" + "\n".join(top_list)
            return "No product sales data found."

        elif tool_name == "get_top_customers_by_spending":
            customers = result.get("customers", [])
            if customers:
                top_list = []
                for i, c in enumerate(customers[:5], 1):
                    name = c.get("name", f"Customer {c.get('user_id', 'Unknown')}")
                    spent = c.get("total_spent", 0)
                    top_list.append(f"{i}. {name}: ${spent:,.2f}")
                return "Top customers by spending:\n" + "\n".join(top_list)
            return "No customer data found."

        else:
            return result.get("message", "Query completed successfully.")


# Global instance
llm_mcp_orchestrator = LLMMCPOrchestrator()
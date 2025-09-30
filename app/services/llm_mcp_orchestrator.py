"""
LLM MCP Orchestrator
Uses LLM to decide which MCP tools to call based on natural language queries
"""

import json
import logging
from typing import Dict, Any, Optional
import httpx
import time

from app.core.config import settings
from app.core.database import mongodb
from app.services.mongodb_mcp_service import mongodb_mcp
from app.services.hf_response_generator import hf_response_generator
from app.services.query_logger import query_logger

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
        start_time = time.time()

        try:
            # FIRST: Check if this is a complex multi-part query
            complex_result = await self._try_complex_query_pattern(question, shop_id, start_time)
            if complex_result:
                return complex_result

            # Standard processing: Try keyword-based tool selection (more reliable)
            tool_decision = self._keyword_tool_selection(question)

            # ONLY if keyword matching fails completely, try Ollama then LLM
            if not tool_decision or tool_decision.get("confidence", 0) < 0.3:
                logger.info("Keyword matching uncertain, trying Ollama quick generation")

                # Try Ollama with short timeout (10s)
                ollama_result = await self._try_ollama_generation(question, shop_id, start_time)
                if ollama_result and ollama_result.get("success"):
                    return ollama_result

                # If Ollama fails/times out, use fallback LLM decision
                logger.info("Ollama failed, trying LLM tool decision")
                tool_decision = await self._get_tool_decision(question, shop_id)

            if not tool_decision or not tool_decision.get("tool"):
                response_time = time.time() - start_time

                # Log failed query
                query_logger.log_query(
                    question=question,
                    shop_id=shop_id,
                    answer="",
                    tool_used="none",
                    intent="unknown",
                    confidence=0.0,
                    success=False,
                    response_time=response_time,
                    error="Could not determine appropriate tool"
                )

                return {
                    "success": False,
                    "error": "Could not determine appropriate tool"
                }

            # Execute the chosen tool
            result = await self._execute_tool(tool_decision, shop_id)

            # Format the answer
            if result.get("success"):
                # Use HF response generator for natural language
                answer = hf_response_generator.generate_response(
                    data=result,
                    question=question,
                    tool_name=tool_decision.get("tool")
                )

                response_time = time.time() - start_time

                # Log successful query
                query_logger.log_query(
                    question=question,
                    shop_id=shop_id,
                    answer=answer,
                    tool_used=tool_decision["tool"],
                    intent="analytical",  # Could be enhanced with intent classification
                    confidence=tool_decision.get("confidence", 0.5),
                    success=True,
                    response_time=response_time,
                    data=result
                )

                return {
                    "success": True,
                    "answer": answer,
                    "data": result.get("documents") or result.get("result") or result.get("groups") or result.get("customers"),
                    "metadata": {
                        "tool_used": tool_decision["tool"],
                        "parameters": tool_decision.get("parameters", {}),
                        "confidence": tool_decision.get("confidence", 0.5)
                    }
                }
            else:
                response_time = time.time() - start_time

                # Log failed query
                query_logger.log_query(
                    question=question,
                    shop_id=shop_id,
                    answer="",
                    tool_used=tool_decision.get("tool", "unknown"),
                    intent="analytical",
                    confidence=tool_decision.get("confidence", 0.5),
                    success=False,
                    response_time=response_time,
                    error=result.get("error", "Tool execution failed")
                )

                return {
                    "success": False,
                    "error": result.get("error", "Tool execution failed")
                }

        except Exception as e:
            response_time = time.time() - start_time
            logger.error(f"MCP query processing failed: {e}")

            # Log exception
            query_logger.log_query(
                question=question,
                shop_id=shop_id,
                answer="",
                tool_used="unknown",
                intent="unknown",
                confidence=0.0,
                success=False,
                response_time=response_time,
                error=str(e)
            )

            return {
                "success": False,
                "error": str(e)
            }

    async def _try_complex_query_pattern(
        self,
        question: str,
        shop_id: int,
        start_time: float
    ) -> Optional[Dict[str, Any]]:
        """
        Detect and handle complex multi-part queries with custom pipelines.
        """
        question_lower = question.lower()

        # Pattern: Products by revenue + customer frequency + payment distribution + delivery filter
        if all([
            any(w in question_lower for w in ["product", "products"]),
            any(w in question_lower for w in ["revenue", "generated"]),
            any(w in question_lower for w in ["customer", "customers"]),
            any(w in question_lower for w in ["placed", "orders", "order"]),
            any(w in question_lower for w in ["percentage", "percent", "paid", "unpaid"])
        ]):
            logger.info("Detected complex products-revenue-customers-payment pattern")

            # Extract parameters
            import re

            # Get min orders
            min_orders = 3
            order_match = re.search(r'(\d+)\s+orders?', question_lower)
            if order_match:
                min_orders = int(order_match.group(1))

            # Get delivery charge filter
            dc_filter = {}
            dc_match = re.search(r'delivery\s+charge[s]?\s+(above|over|greater than|>)\s+(\d+)', question_lower)
            if dc_match:
                dc_filter = {"$gt": float(dc_match.group(2))}

            # Build complex aggregation pipeline
            pipeline = [
                # Step 1: Start with orders
                {"$match": {"shop_id": shop_id}},

                # Step 2: Group by customer to find those with min_orders+
                {
                    "$group": {
                        "_id": "$user_id",
                        "order_count": {"$sum": 1},
                        "orders": {"$push": "$$ROOT"}
                    }
                },
                {"$match": {"order_count": {"$gte": min_orders}}},

                # Step 3: Unwind orders back
                {"$unwind": "$orders"},
                {"$replaceRoot": {"newRoot": "$orders"}},

                # Step 4: Apply delivery charge filter if specified
                *([{"$match": {"delivery_charge": dc_filter}}] if dc_filter else []),

                # Step 5: Lookup order products
                {
                    "$lookup": {
                        "from": "order_product",
                        "localField": "id",
                        "foreignField": "order_id",
                        "as": "products"
                    }
                },

                # Step 6: Unwind products
                {"$unwind": "$products"},

                # Step 7: Group by product for revenue
                {
                    "$group": {
                        "_id": "$products.product_id",
                        "total_revenue": {
                            "$sum": {"$multiply": ["$products.price", "$products.quantity"]}
                        },
                        "total_quantity": {"$sum": "$products.quantity"},
                        "order_count": {"$sum": 1}
                    }
                },

                # Step 8: Sort by revenue
                {"$sort": {"total_revenue": -1}},
                {"$limit": 10},

                # Step 9: Lookup product details
                {
                    "$lookup": {
                        "from": "product",
                        "localField": "_id",
                        "foreignField": "id",
                        "as": "product_info"
                    }
                },
                {"$unwind": {"path": "$product_info", "preserveNullAndEmptyArrays": True}}
            ]

            try:
                # Execute product revenue query
                result = await mongodb.execute_aggregation("order", pipeline)

                # Also get payment distribution
                payment_pipeline = [
                    {"$match": {"shop_id": shop_id}},
                    {
                        "$group": {
                            "_id": "$user_id",
                            "order_count": {"$sum": 1},
                            "orders": {"$push": "$$ROOT"}
                        }
                    },
                    {"$match": {"order_count": {"$gte": min_orders}}},
                    {"$unwind": "$orders"},
                    {"$replaceRoot": {"newRoot": "$orders"}},
                    *([{"$match": {"delivery_charge": dc_filter}}] if dc_filter else []),
                    {
                        "$group": {
                            "_id": "$payment_status",
                            "count": {"$sum": 1}
                        }
                    },
                    {
                        "$group": {
                            "_id": None,
                            "statuses": {"$push": {"status": "$_id", "count": "$count"}},
                            "total": {"$sum": "$count"}
                        }
                    },
                    {"$unwind": "$statuses"},
                    {
                        "$project": {
                            "_id": 0,
                            "status": "$statuses.status",
                            "count": "$statuses.count",
                            "percentage": {
                                "$multiply": [
                                    {"$divide": ["$statuses.count", "$total"]},
                                    100
                                ]
                            }
                        }
                    }
                ]

                payment_result = await mongodb.execute_aggregation("order", payment_pipeline)

                # Format answer
                answer_parts = []

                # Products
                if result:
                    answer_parts.append("Top products by revenue:")
                    for i, item in enumerate(result[:5], 1):
                        name = item.get("product_info", {}).get("name", f"Product {item['_id']}")
                        revenue = item.get("total_revenue", 0)
                        qty = item.get("total_quantity", 0)
                        answer_parts.append(f"  {i}. {name}: ${revenue:,.2f} ({qty} units)")

                # Payment distribution
                if payment_result:
                    answer_parts.append("\nPayment distribution:")
                    for item in payment_result:
                        status = item.get("status", "unknown")
                        count = item.get("count", 0)
                        pct = item.get("percentage", 0)
                        answer_parts.append(f"  {status}: {count} orders ({pct:.1f}%)")

                answer = "\n".join(answer_parts) if answer_parts else "No results found"

                response_time = time.time() - start_time

                query_logger.log_query(
                    question=question,
                    shop_id=shop_id,
                    answer=answer,
                    tool_used="complex_pipeline",
                    intent="complex_analytical",
                    confidence=0.9,
                    success=True,
                    response_time=response_time,
                    data={"products": result, "payment_dist": payment_result}
                )

                return {
                    "success": True,
                    "answer": answer,
                    "data": result,
                    "metadata": {
                        "tool_used": "complex_pipeline",
                        "min_orders_filter": min_orders,
                        "delivery_charge_filter": dc_filter,
                        "payment_distribution": payment_result,
                        "confidence": 0.9
                    }
                }

            except Exception as e:
                logger.error(f"Complex query execution failed: {e}")
                return None

        # Pattern 2: Top customers with additional filters
        elif all([
            any(w in question_lower for w in ["customer", "customers", "top customer"]),
            any(w in question_lower for w in ["spending", "spent", "revenue", "purchase"])
        ]) and any(w in question_lower for w in ["product", "category", "region", "year", "month"]):
            logger.info("Detected complex customers-spending-filter pattern")

            # This is a complex customer query that needs custom handling
            # For now, use best effort with existing tools
            pass

        # Pattern 3: Product analysis with trends
        elif all([
            any(w in question_lower for w in ["product", "products"]),
            any(w in question_lower for w in ["trend", "growth", "decline", "increase", "decrease", "comparison", "compare"])
        ]):
            logger.info("Detected product trend analysis pattern")
            # Needs time-series aggregation - complex pattern
            pass

        # Pattern 4: Time-based queries (month/year comparisons)
        elif any(phrase in question_lower for phrase in [
            "last month", "this month", "last year", "this year",
            "monthly", "yearly", "year over year", "yoy",
            "quarter", "seasonal"
        ]):
            logger.info("Detected temporal analysis pattern")
            # Needs date grouping and comparisons
            pass

        return None

    async def _try_ollama_generation(
        self,
        question: str,
        shop_id: int,
        start_time: float
    ) -> Optional[Dict[str, Any]]:
        """
        Try to use Ollama to generate MongoDB pipeline for unseen queries.
        Uses a simple, fast approach with minimal prompting.
        """
        try:
            schema_context = """
Collections: order (shop_id, user_id, grand_total, delivery_charge, status, payment_status, created_at)
            product (id, shop_id, name, price, category_id)
            order_product (order_id, product_id, quantity, price)
            customer (id, shop_id, first_name, last_name, email)
"""

            prompt = f"""{schema_context}

Question: {question}
Shop ID: {shop_id}

Generate MongoDB aggregation pipeline as JSON array. Start with [{{"$match": {{"shop_id": {shop_id}}}}}]
Pipeline:"""

            response = await self.client.post(
                f"{self.base_url}/api/generate",
                json={
                    "model": "tinyllama:1.1b",
                    "prompt": prompt,
                    "stream": False,
                    "temperature": 0.1
                },
                timeout=10.0  # 10 second timeout
            )

            if response.status_code == 200:
                result = response.json()
                generated = result.get("response", "")

                # Try to extract JSON array
                import re
                import json as json_lib

                if "[" in generated:
                    start = generated.find("[")
                    end = generated.rfind("]") + 1
                    pipeline_str = generated[start:end]

                    try:
                        pipeline = json_lib.loads(pipeline_str)
                        if isinstance(pipeline, list) and len(pipeline) > 0:
                            logger.info(f"Ollama generated pipeline: {pipeline}")

                            # Execute pipeline
                            exec_result = await mongodb.execute_aggregation("order", pipeline)

                            response_time = time.time() - start_time

                            return {
                                "success": True,
                                "answer": f"Found {len(exec_result)} results",
                                "data": exec_result,
                                "metadata": {
                                    "tool_used": "ollama_pipeline",
                                    "pipeline": pipeline,
                                    "confidence": 0.6
                                }
                            }
                    except:
                        pass

        except Exception as e:
            logger.warning(f"Ollama generation failed: {e}")

        return None

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

        # Count queries - improved to catch "count all" patterns
        if any(phrase in question_lower for phrase in ["how many", "number of", "count of", "count all", "total number"]):
            confidence = 0.9
            if "product" in question_lower:
                return {"tool": "count_documents", "parameters": {"collection": "product", "filter": extracted_filters}, "confidence": confidence}
            elif "customer" in question_lower:
                return {"tool": "count_documents", "parameters": {"collection": "customer", "filter": extracted_filters}, "confidence": confidence}
            elif "order" in question_lower:
                return {"tool": "count_documents", "parameters": {"collection": "order", "filter": extracted_filters}, "confidence": confidence}
            elif "categor" in question_lower:  # catches category/categories
                return {"tool": "count_documents", "parameters": {"collection": "category"}, "confidence": confidence}
            else:
                # Default to orders with lower confidence
                return {"tool": "count_documents", "parameters": {"collection": "order", "filter": extracted_filters}, "confidence": 0.6}

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

        # Top customers - improved to catch more patterns
        if ("top" in question_lower or "best" in question_lower or "highest" in question_lower) and "customer" in question_lower:
            limit = 5
            # Extract number if present
            import re
            numbers = re.findall(r'\d+', question_lower)
            if numbers:
                limit = int(numbers[0])
            # High confidence even without "spending" keyword
            confidence = 0.95 if any(word in question_lower for word in ["spending", "spent", "revenue", "purchase"]) else 0.90
            return {
                "tool": "get_top_customers_by_spending",
                "parameters": {"limit": limit},
                "confidence": confidence
            }

        # Product sales analysis - improved to catch "top products"
        if ("best" in question_lower or "top" in question_lower or "most" in question_lower or "highest" in question_lower) and "product" in question_lower:
            limit = 10
            # Extract number if present
            import re
            numbers = re.findall(r'\d+', question_lower)
            if numbers:
                limit = int(numbers[0])
            # High confidence even without "selling" keyword
            confidence = 0.95 if any(word in question_lower for word in ["selling", "sold", "popular"]) else 0.90
            return {
                "tool": "get_best_selling_products",
                "parameters": {"limit": limit},
                "confidence": confidence
            }

        # Group by queries - improved to catch more patterns
        if any(phrase in question_lower for phrase in ["group", "breakdown", "distribution", "by status", "by category", "by payment", "count by", "orders by"]):
            group_field = "status"  # default
            collection = "order"  # default
            confidence = 0.85

            if "status" in question_lower:
                group_field = "status"
                collection = "order"
                confidence = 0.90
            elif "payment" in question_lower:
                group_field = "payment_status"
                collection = "order"
                confidence = 0.90
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
                "confidence": confidence
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

        # Year-based queries - NEW: catch "2024", "this year", etc.
        import re
        year_match = re.search(r'\b(20\d{2})\b', question_lower)
        if year_match or "this year" in question_lower or "from year" in question_lower:
            # For specific years like "2024" or "this year"
            confidence = 0.85
            # Use find_documents with date filter (more flexible)
            return {
                "tool": "find_documents",
                "parameters": {
                    "collection": "order",
                    "filter": extracted_filters,
                    "sort_by": "created_at",
                    "sort_order": -1,
                    "limit": 10
                },
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
            elif "year" in question_lower and "this" not in question_lower:
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
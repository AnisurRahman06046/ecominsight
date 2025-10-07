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
from app.services.few_shot_response_generator import few_shot_response_generator
from app.services.query_logger import query_logger
from app.services.semantic_router import semantic_router
from app.services.hf_parameter_extractor import hf_parameter_extractor

logger = logging.getLogger(__name__)


class LLMMCPOrchestrator:
    """
    Orchestrates MCP tool calls using LLM for decision making.
    Instead of generating MongoDB queries, the LLM chooses tools to call.
    """

    def __init__(self):
        self.client = httpx.AsyncClient(timeout=30)

    def _get_generic_error_message(self, error_type: str = "general") -> str:
        """
        Get user-friendly error messages instead of exposing technical errors.

        Args:
            error_type: Type of error (general, timeout, not_found, invalid_query)

        Returns:
            User-friendly error message
        """
        error_messages = {
            "general": "I apologize, but I'm having trouble processing your request at the moment. Could you please try rephrasing your question or contact support if the issue persists?",
            "timeout": "Your query is taking longer than expected to process. Please try again or simplify your question.",
            "not_found": "I couldn't find any data matching your query. Please check your shop ID or try a different question.",
            "invalid_query": "I'm not sure I understood your question correctly. Could you please rephrase it more clearly? For example: 'How many orders are there?' or 'What is the total revenue?'",
            "tool_selection": "I'm having difficulty determining how to answer your question. Please try asking in a different way or use one of the example queries.",
            "execution_failed": "I encountered an issue while retrieving the data. Please try again in a moment."
        }
        return error_messages.get(error_type, error_messages["general"])

    def _handle_conversational_query(self, question: str, start_time: float) -> Optional[Dict[str, Any]]:
        """
        Handle conversational queries like greetings, thanks, help requests.
        Returns response if conversational, None if analytical query.
        """
        question_lower = question.strip().lower()

        # Define conversational patterns
        conversational_responses = {
            # Greetings
            ("hi", "hello", "hey", "hii", "helo"): [
                "Hello! I'm your e-commerce analytics assistant. I can help you analyze your sales data, track orders, understand customer behavior, and much more. What would you like to know?",
                "Hi there! I can help you with sales reports, order analysis, customer insights, and revenue tracking. How can I assist you today?",
                "Hello! Ask me about your orders, revenue, top products, customer analytics, or any other sales data you need."
            ],
            # Gratitude
            ("thanks", "thank you", "thankyou", "thx", "ty"): [
                "You're welcome! Let me know if you need anything else.",
                "Happy to help! Feel free to ask more questions anytime.",
                "Glad I could help! Is there anything else you'd like to know?"
            ],
            # Goodbyes
            ("bye", "goodbye", "see you", "later"): [
                "Goodbye! Feel free to come back anytime you need analytics insights.",
                "See you later! Happy selling!",
                "Bye! Come back if you need more sales insights."
            ],
            # Help/Capability
            ("what can you do", "help", "help me", "what do you do", "capabilities"): [
                "I can help you with:\n• Sales analytics (total revenue, average orders)\n• Product insights (best sellers, inventory counts)\n• Customer analysis (top customers, spending patterns)\n• Order tracking (by status, date, payment)\n• Complex queries (multi-condition filters, trends)\n\nTry asking: 'What is my total revenue?' or 'Who are my top customers?'",
            ],
            # Status check
            ("how are you", "how r u", "how are you doing"): [
                "I'm functioning perfectly and ready to help with your sales analytics! What would you like to analyze?",
                "All systems running smoothly! What sales data can I help you with today?"
            ]
        }

        # Check if query matches any conversational pattern
        # Use exact match or word boundary matching to avoid false positives
        import random
        for patterns, responses in conversational_responses.items():
            # Check for exact match first
            if question_lower in patterns:
                response = random.choice(responses)
                response_time = time.time() - start_time

                logger.info(f"Conversational query detected: {question} → {response[:50]}...")

                # Log as successful conversational interaction
                query_logger.log_query(
                    question=question,
                    shop_id=0,  # No shop context needed
                    answer=response,
                    tool_used="conversational",
                    intent="conversational",
                    confidence=1.0,
                    success=True,
                    response_time=response_time
                )

                return {
                    "success": True,
                    "answer": response,
                    "data": [],
                    "metadata": {
                        "tool_used": "conversational",
                        "intent": "conversational",
                        "confidence": 1.0,
                        "routing_method": "conversational_detection"
                    }
                }

        return None  # Not a conversational query, continue with analytics

    def _get_clarification_response(self, question: str) -> str:
        """Get clarification response for ambiguous queries."""
        question_lower = question.lower().strip()

        # Specific clarifications for common ambiguous words
        clarifications = {
            "sales": "I can help with sales data! Did you mean:\n• Total sales revenue?\n• Number of orders/sales?\n• Sales by product or category?\n• Sales for a specific time period?",
            "revenue": "I can show you revenue data! Did you mean:\n• Total revenue?\n• Revenue by product?\n• Revenue by time period?\n• Revenue by payment status?",
            "orders": "I can help with order data! Did you mean:\n• Total number of orders?\n• Recent orders?\n• Orders by status (pending/completed)?\n• Orders for a specific period?",
            "products": "I can show product information! Did you mean:\n• Total number of products?\n• Best selling products?\n• Products by category?\n• Product revenue?",
            "customers": "I can help with customer data! Did you mean:\n• Total number of customers?\n• Top customers by spending?\n• Customer order frequency?\n• Customer segmentation?"
        }

        if question_lower in clarifications:
            return clarifications[question_lower]

        # Generic clarification
        return f"I'm not sure what you meant by '{question}'. Could you be more specific? For example:\n• 'What is my total revenue?'\n• 'How many orders do I have?'\n• 'Who are my top customers?'\n• 'What are my best selling products?'"

    async def process_query(self, question: str, shop_id: str) -> Dict[str, Any]:
        """
        Process a natural language query using MCP tools.

        Args:
            question: User's natural language question
            shop_id: Shop ID for filtering (as string to match database)

        Returns:
            Dict with answer and data
        """
        start_time = time.time()

        try:
            # FIRST: Check if this is a conversational query (greetings, thanks, etc.)
            conversational_result = self._handle_conversational_query(question, start_time)
            if conversational_result:
                return conversational_result

            # SECOND: Check if this is a complex multi-part query
            complex_result = await self._try_complex_query_pattern(question, shop_id, start_time)
            if complex_result:
                return complex_result

            # Standard processing: Try semantic router first (most reliable)
            logger.info(f"Trying semantic router for: {question}")
            tool_decision = semantic_router.route_query(question, min_confidence=0.75)

            # Track confidence for logging
            semantic_confidence = tool_decision.get("confidence", 0.0) if tool_decision else 0.0
            routing_method = "semantic" if tool_decision and semantic_confidence >= 0.75 else "fallback"

            # If semantic router succeeded, enhance parameters using LLM
            if tool_decision and semantic_confidence >= 0.75:
                logger.info(f"Semantic router matched: {tool_decision.get('tool')} (confidence: {semantic_confidence:.3f})")
                logger.info("Enhancing parameters with LLM extraction...")

                try:
                    # Use HuggingFace extractor to extract detailed parameters (dates, filters, etc.)
                    enhanced_params = hf_parameter_extractor.extract_parameters(
                        query=question,
                        tool_name=tool_decision.get("tool"),
                        basic_params=tool_decision.get("parameters", {})
                    )

                    # Update tool decision with enhanced parameters
                    tool_decision["parameters"] = enhanced_params
                    logger.info(f"Enhanced parameters: {json.dumps(enhanced_params, default=str)}")
                except Exception as e:
                    logger.warning(f"Parameter extraction failed, using basic params: {e}")
                    # Continue with basic params from semantic router

            # If semantic router fails or low confidence, try keyword matching
            if not tool_decision or semantic_confidence < 0.75:
                logger.info(f"Semantic router failed/uncertain (confidence: {semantic_confidence:.3f}), trying keyword matching")
                tool_decision = self._keyword_tool_selection(question)

                # Improve: Reject very low confidence results and ask for clarification
                if not tool_decision or tool_decision.get("confidence", 0) < 0.4:
                    logger.warning(f"Very low confidence ({tool_decision.get('confidence', 0) if tool_decision else 0}), asking for clarification")

                    # Check if query is too ambiguous (single word or very short)
                    if len(question.split()) <= 2 and tool_decision.get("confidence", 0) < 0.5:
                        clarification_response = self._get_clarification_response(question)
                        response_time = time.time() - start_time

                        query_logger.log_query(
                            question=question,
                            shop_id=shop_id,
                            answer=clarification_response,
                            tool_used="clarification",
                            intent="ambiguous",
                            confidence=0.0,
                            success=True,
                            response_time=response_time
                        )

                        return {
                            "success": True,
                            "answer": clarification_response,
                            "data": [],
                            "metadata": {
                                "tool_used": "clarification",
                                "confidence": 0.0,
                                "routing_method": "clarification_needed"
                            }
                        }

                    # Low confidence - use LLM tool decision
                    logger.info("Keyword matching uncertain, trying LLM tool decision")
                    tool_decision = await self._get_tool_decision(question, shop_id)
                    routing_method = "llm_fallback"

                # Log low-confidence queries if needed (removed low_confidence_logger)

            if not tool_decision or not tool_decision.get("tool"):
                response_time = time.time() - start_time

                # Get user-friendly error message
                user_message = self._get_generic_error_message("tool_selection")

                # Log failed query with technical error
                query_logger.log_query(
                    question=question,
                    shop_id=shop_id,
                    answer=user_message,
                    tool_used="none",
                    intent="unknown",
                    confidence=0.0,
                    success=False,
                    response_time=response_time,
                    error="Could not determine appropriate tool"  # Technical error for logs
                )

                return {
                    "success": False,
                    "answer": user_message,  # User-friendly message
                    "error": user_message
                }

            # Execute the chosen tool
            result = await self._execute_tool(tool_decision, shop_id)

            # Format the answer
            if result.get("success"):
                answer = None

                # Try few-shot prompting first (pre-trained model with examples)
                if few_shot_response_generator.initialized:
                    logger.info("Attempting few-shot response generation")
                    answer = few_shot_response_generator.generate_response(
                        question=question,
                        data=result,
                        tool_name=tool_decision.get("tool")
                    )

                # Fallback to randomized templates if model fails or returns None
                if not answer:
                    logger.info("Using template-based response generator (fallback)")
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
                        "confidence": tool_decision.get("confidence", 0.5),
                        "routing_method": tool_decision.get("method", routing_method),
                        "semantic_confidence": semantic_confidence
                    }
                }
            else:
                response_time = time.time() - start_time

                # Get user-friendly error message
                user_message = self._get_generic_error_message("execution_failed")

                # Log failed query with technical error
                query_logger.log_query(
                    question=question,
                    shop_id=shop_id,
                    answer=user_message,
                    tool_used=tool_decision.get("tool", "unknown"),
                    intent="analytical",
                    confidence=tool_decision.get("confidence", 0.5),
                    success=False,
                    response_time=response_time,
                    error=result.get("error", "Tool execution failed")  # Technical error for logs
                )

                return {
                    "success": False,
                    "answer": user_message,  # User-friendly message
                    "error": user_message
                }

        except Exception as e:
            response_time = time.time() - start_time
            logger.error(f"MCP query processing failed: {e}")

            # Get user-friendly error message
            user_message = self._get_generic_error_message("general")

            # Log exception with technical error
            query_logger.log_query(
                question=question,
                shop_id=shop_id,
                answer=user_message,
                tool_used="unknown",
                intent="unknown",
                confidence=0.0,
                success=False,
                response_time=response_time,
                error=str(e)  # Technical error for logs
            )

            return {
                "success": False,
                "answer": user_message,  # User-friendly message
                "error": user_message
            }

    async def _try_complex_query_pattern(
        self,
        question: str,
        shop_id: int,
        start_time: float
    ) -> Optional[Dict[str, Any]]:
        """
        Detect and handle complex multi-part queries with custom pipelines.
        Now supports 20+ complex patterns for common business queries.
        """
        question_lower = question.lower()
        import re

        # PATTERN 1: Products by revenue + customer frequency + payment distribution + delivery filter
        if all([
            any(w in question_lower for w in ["product", "products"]),
            any(w in question_lower for w in ["revenue", "generated"]),
            any(w in question_lower for w in ["customer", "customers"]),
            any(w in question_lower for w in ["placed", "orders", "order"]),
            any(w in question_lower for w in ["percentage", "percent", "paid", "unpaid"])
        ]):
            logger.info("Detected complex products-revenue-customers-payment pattern")

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

        # PATTERN 2: High-value customers (spending threshold)
        elif all([
            any(w in question_lower for w in ["customer", "customers"]),
            any(w in question_lower for w in ["spending", "spent", "spend", "revenue", "purchase"]),
            any(phrase in question_lower for phrase in ["more than", "greater than", "above", "over", ">"])
        ]):
            logger.info("Detected high-value customers pattern")
            try:
                # Extract spending threshold
                threshold = 5000
                threshold_match = re.search(r'(more than|greater than|above|over|>)\s*\$?(\d+)', question_lower)
                if threshold_match:
                    threshold = float(threshold_match.group(2))

                pipeline = [
                    {"$match": {"shop_id": shop_id}},
                    {"$group": {
                        "_id": "$user_id",
                        "total_spent": {"$sum": "$grand_total"},
                        "order_count": {"$sum": 1}
                    }},
                    {"$match": {"total_spent": {"$gt": threshold}}},
                    {"$sort": {"total_spent": -1}},
                    {"$limit": 50}
                ]

                result = await mongodb.execute_aggregation("order", pipeline)
                answer = f"Found {len(result)} customers who spent more than ${threshold:,.2f}:\n"
                for i, customer in enumerate(result[:10], 1):
                    answer += f"  {i}. Customer {customer['_id']}: ${customer['total_spent']:,.2f} ({customer['order_count']} orders)\n"

                return {
                    "success": True,
                    "answer": answer.strip(),
                    "data": result,
                    "metadata": {"tool_used": "complex_pipeline", "confidence": 0.85}
                }
            except Exception as e:
                logger.error(f"Pattern 2 failed: {e}")
                return None

        # PATTERN 3: Product revenue with category filter
        elif all([
            any(w in question_lower for w in ["product", "products"]),
            any(w in question_lower for w in ["revenue", "sales", "earning"]),
            any(w in question_lower for w in ["category", "categories"])
        ]):
            logger.info("Detected products by revenue with category pattern")
            try:
                pipeline = [
                    {"$match": {"shop_id": shop_id}},
                    {"$lookup": {
                        "from": "order_product",
                        "localField": "id",
                        "foreignField": "order_id",
                        "as": "products"
                    }},
                    {"$unwind": "$products"},
                    {"$lookup": {
                        "from": "product",
                        "localField": "products.product_id",
                        "foreignField": "id",
                        "as": "product_info"
                    }},
                    {"$unwind": "$product_info"},
                    {"$group": {
                        "_id": {
                            "product_id": "$products.product_id",
                            "category": "$product_info.category_id",
                            "name": "$product_info.name"
                        },
                        "total_revenue": {"$sum": {"$multiply": ["$products.price", "$products.quantity"]}},
                        "total_quantity": {"$sum": "$products.quantity"}
                    }},
                    {"$sort": {"total_revenue": -1}},
                    {"$limit": 15}
                ]

                result = await mongodb.execute_aggregation("order", pipeline)
                answer = "Top products by revenue (with category):\n"
                for i, item in enumerate(result, 1):
                    name = item['_id']['name']
                    revenue = item['total_revenue']
                    qty = item['total_quantity']
                    cat = item['_id']['category']
                    answer += f"  {i}. {name} (Cat: {cat}): ${revenue:,.2f} ({qty} units)\n"

                return {
                    "success": True,
                    "answer": answer.strip(),
                    "data": result,
                    "metadata": {"tool_used": "complex_pipeline", "confidence": 0.88}
                }
            except Exception as e:
                logger.error(f"Pattern 3 failed: {e}")
                return None

        # PATTERN 4: Orders with multiple conditions (status + payment + amount)
        elif all([
            "order" in question_lower,
            any(w in question_lower for w in ["status", "payment"]),
            any(phrase in question_lower for phrase in ["more than", "greater than", "less than", "between"])
        ]):
            logger.info("Detected orders with multiple filters pattern")
            try:
                match_filter = {"shop_id": shop_id}

                # Status filter
                if "pending" in question_lower:
                    match_filter["status"] = "pending"
                elif "completed" in question_lower or "complete" in question_lower:
                    match_filter["status"] = "completed"

                # Payment filter
                if "paid" in question_lower and "unpaid" not in question_lower:
                    match_filter["payment_status"] = "paid"
                elif "unpaid" in question_lower:
                    match_filter["payment_status"] = "unpaid"

                # Amount filter
                amount_match = re.search(r'(more than|greater than|above|>)\s*\$?(\d+)', question_lower)
                if amount_match:
                    match_filter["grand_total"] = {"$gt": float(amount_match.group(2))}

                pipeline = [
                    {"$match": match_filter},
                    {"$sort": {"created_at": -1}},
                    {"$limit": 50}
                ]

                result = await mongodb.execute_aggregation("order", pipeline)
                answer = f"Found {len(result)} orders matching your criteria:\n"
                for i, order in enumerate(result[:10], 1):
                    answer += f"  {i}. Order {order.get('id')}: ${order.get('grand_total', 0):,.2f} - {order.get('status')} ({order.get('payment_status')})\n"

                return {
                    "success": True,
                    "answer": answer.strip(),
                    "data": result,
                    "metadata": {"tool_used": "complex_pipeline", "confidence": 0.82}
                }
            except Exception as e:
                logger.error(f"Pattern 4 failed: {e}")
                return None

        # PATTERN 5: Customer order frequency analysis
        elif all([
            any(w in question_lower for w in ["customer", "customers"]),
            any(w in question_lower for w in ["frequent", "most orders", "order count", "placed"]),
        ]) and not ("spending" in question_lower or "revenue" in question_lower):
            logger.info("Detected customer order frequency pattern")
            try:
                min_orders = 1
                match = re.search(r'(\d+)\s+or more orders?', question_lower)
                if match:
                    min_orders = int(match.group(1))

                pipeline = [
                    {"$match": {"shop_id": shop_id}},
                    {"$group": {
                        "_id": "$user_id",
                        "order_count": {"$sum": 1},
                        "total_spent": {"$sum": "$grand_total"},
                        "avg_order": {"$avg": "$grand_total"}
                    }},
                    {"$match": {"order_count": {"$gte": min_orders}}},
                    {"$sort": {"order_count": -1}},
                    {"$limit": 20}
                ]

                result = await mongodb.execute_aggregation("order", pipeline)
                answer = f"Customers by order frequency (min {min_orders} orders):\n"
                for i, customer in enumerate(result[:10], 1):
                    answer += f"  {i}. Customer {customer['_id']}: {customer['order_count']} orders (${customer['total_spent']:,.2f} total)\n"

                return {
                    "success": True,
                    "answer": answer.strip(),
                    "data": result,
                    "metadata": {"tool_used": "complex_pipeline", "confidence": 0.87}
                }
            except Exception as e:
                logger.error(f"Pattern 5 failed: {e}")
                return None

        # PATTERN 6: Average order value by payment status
        elif all([
            any(w in question_lower for w in ["average", "avg", "mean"]),
            "order" in question_lower,
            any(w in question_lower for w in ["payment", "paid", "unpaid"])
        ]):
            logger.info("Detected average order by payment status pattern")
            try:
                pipeline = [
                    {"$match": {"shop_id": shop_id}},
                    {"$group": {
                        "_id": "$payment_status",
                        "avg_value": {"$avg": "$grand_total"},
                        "count": {"$sum": 1},
                        "total": {"$sum": "$grand_total"}
                    }},
                    {"$sort": {"avg_value": -1}}
                ]

                result = await mongodb.execute_aggregation("order", pipeline)
                answer = "Average order value by payment status:\n"
                for item in result:
                    status = item['_id'] or "unknown"
                    avg = item['avg_value']
                    count = item['count']
                    total = item['total']
                    answer += f"  {status}: ${avg:,.2f} average ({count} orders, ${total:,.2f} total)\n"

                return {
                    "success": True,
                    "answer": answer.strip(),
                    "data": result,
                    "metadata": {"tool_used": "complex_pipeline", "confidence": 0.90}
                }
            except Exception as e:
                logger.error(f"Pattern 6 failed: {e}")
                return None

        # PATTERN 7: Products never/rarely ordered
        elif all([
            "product" in question_lower,
            any(w in question_lower for w in ["never", "rarely", "not sold", "no sales", "least"])
        ]):
            logger.info("Detected rarely ordered products pattern")
            try:
                # Get all products
                all_products = await mongodb.find_documents("product", {"shop_id": shop_id}, limit=1000)
                product_ids = [p['id'] for p in all_products]

                # Get ordered products
                pipeline = [
                    {"$match": {"shop_id": shop_id}},
                    {"$lookup": {
                        "from": "order_product",
                        "localField": "id",
                        "foreignField": "order_id",
                        "as": "products"
                    }},
                    {"$unwind": "$products"},
                    {"$group": {
                        "_id": "$products.product_id",
                        "order_count": {"$sum": 1},
                        "total_quantity": {"$sum": "$products.quantity"}
                    }},
                    {"$sort": {"order_count": 1}},
                    {"$limit": 20}
                ]

                result = await mongodb.execute_aggregation("order", pipeline)
                ordered_ids = {r['_id'] for r in result}
                never_ordered = [pid for pid in product_ids if pid not in ordered_ids]

                answer = f"Found {len(never_ordered)} products never ordered and {len(result)} rarely ordered products:\n"
                for i, item in enumerate(result[:10], 1):
                    answer += f"  {i}. Product {item['_id']}: {item['order_count']} orders ({item['total_quantity']} units)\n"

                return {
                    "success": True,
                    "answer": answer.strip(),
                    "data": {"never_ordered": never_ordered[:50], "rarely_ordered": result},
                    "metadata": {"tool_used": "complex_pipeline", "confidence": 0.83}
                }
            except Exception as e:
                logger.error(f"Pattern 7 failed: {e}")
                return None

        # PATTERN 8: Orders by date range
        elif any(phrase in question_lower for phrase in [
            "last month", "this month", "last week", "this week",
            "last 30 days", "last 7 days", "in", "during"
        ]) and "order" in question_lower:
            logger.info("Detected orders by date range pattern")
            try:
                from datetime import datetime, timedelta

                now = datetime.utcnow()
                start_date = None

                if "last month" in question_lower:
                    start_date = now - timedelta(days=30)
                elif "last week" in question_lower or "last 7 days" in question_lower:
                    start_date = now - timedelta(days=7)
                elif "last 30 days" in question_lower:
                    start_date = now - timedelta(days=30)
                elif "this week" in question_lower:
                    start_date = now - timedelta(days=now.weekday())

                match_filter = {"shop_id": shop_id}
                if start_date:
                    match_filter["created_at"] = {"$gte": start_date}

                pipeline = [
                    {"$match": match_filter},
                    {"$group": {
                        "_id": None,
                        "count": {"$sum": 1},
                        "total_revenue": {"$sum": "$grand_total"},
                        "avg_order": {"$avg": "$grand_total"}
                    }}
                ]

                result = await mongodb.execute_aggregation("order", pipeline)
                if result:
                    data = result[0]
                    answer = f"Orders in specified period:\n"
                    answer += f"  Total orders: {data['count']}\n"
                    answer += f"  Total revenue: ${data['total_revenue']:,.2f}\n"
                    answer += f"  Average order: ${data['avg_order']:,.2f}"
                else:
                    answer = "No orders found in the specified period"

                return {
                    "success": True,
                    "answer": answer,
                    "data": result,
                    "metadata": {"tool_used": "complex_pipeline", "confidence": 0.85}
                }
            except Exception as e:
                logger.error(f"Pattern 8 failed: {e}")
                return None

        # PATTERN 9: Product pairs (frequently bought together)
        elif any(phrase in question_lower for phrase in [
            "bought together", "frequently bought", "product pairs",
            "often purchased", "commonly ordered"
        ]):
            logger.info("Detected product pairs pattern")
            try:
                pipeline = [
                    {"$match": {"shop_id": shop_id}},
                    {"$lookup": {
                        "from": "order_product",
                        "localField": "id",
                        "foreignField": "order_id",
                        "as": "products"
                    }},
                    {"$match": {"products.1": {"$exists": True}}},  # At least 2 products
                    {"$unwind": "$products"},
                    {"$group": {
                        "_id": "$id",
                        "product_ids": {"$push": "$products.product_id"}
                    }},
                    {"$limit": 100}
                ]

                result = await mongodb.execute_aggregation("order", pipeline)

                # Count pairs
                from collections import Counter
                pairs = Counter()
                for order in result:
                    pids = order['product_ids']
                    for i in range(len(pids)):
                        for j in range(i+1, len(pids)):
                            pair = tuple(sorted([pids[i], pids[j]]))
                            pairs[pair] += 1

                top_pairs = pairs.most_common(10)
                answer = "Top product pairs frequently bought together:\n"
                for i, (pair, count) in enumerate(top_pairs, 1):
                    answer += f"  {i}. Products {pair[0]} & {pair[1]}: {count} times\n"

                return {
                    "success": True,
                    "answer": answer.strip(),
                    "data": [{"products": list(p), "count": c} for p, c in top_pairs],
                    "metadata": {"tool_used": "complex_pipeline", "confidence": 0.80}
                }
            except Exception as e:
                logger.error(f"Pattern 9 failed: {e}")
                return None

        # PATTERN 10: Revenue by payment method
        elif all([
            any(w in question_lower for w in ["revenue", "sales", "total"]),
            any(w in question_lower for w in ["payment method", "payment status", "paid", "unpaid"])
        ]) and "order" not in question_lower:
            logger.info("Detected revenue by payment method pattern")
            try:
                pipeline = [
                    {"$match": {"shop_id": shop_id}},
                    {"$group": {
                        "_id": "$payment_status",
                        "total_revenue": {"$sum": "$grand_total"},
                        "order_count": {"$sum": 1},
                        "avg_order": {"$avg": "$grand_total"}
                    }},
                    {"$sort": {"total_revenue": -1}}
                ]

                result = await mongodb.execute_aggregation("order", pipeline)
                answer = "Revenue breakdown by payment status:\n"
                total = sum(r['total_revenue'] for r in result)
                for item in result:
                    status = item['_id'] or "unknown"
                    revenue = item['total_revenue']
                    count = item['order_count']
                    pct = (revenue / total * 100) if total > 0 else 0
                    answer += f"  {status}: ${revenue:,.2f} ({pct:.1f}%) - {count} orders\n"

                return {
                    "success": True,
                    "answer": answer.strip(),
                    "data": result,
                    "metadata": {"tool_used": "complex_pipeline", "confidence": 0.88}
                }
            except Exception as e:
                logger.error(f"Pattern 10 failed: {e}")
                return None

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

    def _convert_datetime_to_string(self, filter_dict: Dict[str, Any]) -> Dict[str, Any]:
        """
        Keep datetime objects as-is for MongoDB datetime comparison.
        MongoDB stores created_at/updated_at as datetime objects, not strings.
        """
        from datetime import datetime

        if not filter_dict:
            return filter_dict

        # Return as-is - no conversion needed
        # MongoDB will handle datetime comparisons natively
        return filter_dict

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
            # Normalize filter/filters parameter (both are used)
            filter_param = params.get("filters") or params.get("filter", {})

            # Convert datetime objects to ISO strings for MongoDB (since created_at is stored as string)
            filter_param = self._convert_datetime_to_string(filter_param)

            if tool_name == "count_documents":
                return await mongodb_mcp.count_documents(
                    collection=params.get("collection", "order"),
                    shop_id=shop_id,
                    filter=filter_param
                )

            elif tool_name == "find_documents":
                return await mongodb_mcp.find_documents(
                    collection=params.get("collection", "order"),
                    shop_id=shop_id,
                    filter=filter_param,
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
                    filter=filter_param
                )

            elif tool_name == "calculate_sum":
                return await mongodb_mcp.calculate_sum(
                    collection=params.get("collection", "order"),
                    shop_id=shop_id,
                    sum_field=params.get("sum_field", "grand_total"),
                    group_by=params.get("group_by"),
                    filter=filter_param
                )

            elif tool_name == "calculate_average":
                return await mongodb_mcp.calculate_average(
                    collection=params.get("collection", "order"),
                    shop_id=shop_id,
                    avg_field=params.get("avg_field", "grand_total"),
                    group_by=params.get("group_by"),
                    filter=filter_param
                )

            elif tool_name == "get_top_n":
                return await mongodb_mcp.get_top_n(
                    collection=params.get("collection", "order"),
                    shop_id=shop_id,
                    sort_by=params.get("sort_by", "grand_total"),
                    n=params.get("limit", 5),
                    ascending=params.get("ascending", False),
                    filter=filter_param
                )

            elif tool_name == "get_date_range":
                return await mongodb_mcp.get_date_range(
                    collection=params.get("collection", "order"),
                    shop_id=shop_id,
                    date_field=params.get("date_field", "created_at"),
                    days_back=params.get("days_back", 7),
                    filter=filter_param
                )

            elif tool_name == "get_best_selling_products":
                return await mongodb_mcp.get_best_selling_products(
                    shop_id=shop_id,
                    limit=params.get("limit", 10),
                    filter=filter_param
                )

            elif tool_name == "get_top_customers_by_spending":
                return await mongodb_mcp.get_top_customers_by_spending(
                    shop_id=shop_id,
                    limit=params.get("limit", 10),
                    filter=filter_param
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
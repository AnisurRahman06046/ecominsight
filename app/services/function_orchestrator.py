import time
from typing import Dict, Any, Optional
import logging

from app.services.intent_router import intent_router, Intent
from app.services.database_tools import database_tools
from app.services.ollama_service import ollama_service
from app.services.cache_service import cache_service
from app.core.config import settings

logger = logging.getLogger(__name__)


class FunctionOrchestrator:

    def __init__(self):
        self.intent_router = intent_router
        self.database_tools = database_tools
        self.ollama = ollama_service
        self.cache = cache_service

        self.intent_to_function = {
            Intent.PRODUCT_COUNT: self.database_tools.count_products,
            Intent.ORDER_COUNT: self.database_tools.count_orders,
            Intent.CUSTOMER_COUNT: self.database_tools.count_customers,
            Intent.CATEGORY_COUNT: self.database_tools.count_categories,
            Intent.TOTAL_REVENUE: self.database_tools.total_revenue,
            Intent.AVERAGE_ORDER_VALUE: self.database_tools.average_order_value,
            Intent.TOP_PRODUCTS: self.database_tools.top_products,
            Intent.TOP_CUSTOMERS: self.database_tools.top_customers,
            Intent.RECENT_ORDERS: self.database_tools.recent_orders,
            Intent.SALES_BY_STATUS: self.database_tools.sales_by_status,
        }

    async def initialize(self):
        await self.cache.initialize()
        logger.info("Function orchestrator initialized")

    async def process_query(
        self,
        shop_id: str,
        question: str,
        context: Optional[Dict[str, Any]] = None,
        use_cache: bool = True,
    ) -> Dict[str, Any]:
        start_time = time.time()

        if use_cache and settings.enable_cache:
            cached_result = await self.cache.get(f"{shop_id}:{question}")
            if cached_result:
                logger.info(f"Cache hit for query: {question[:50]}...")
                return {
                    **cached_result,
                    "cached": True,
                    "processing_time": time.time() - start_time,
                }

        intent, params = self.intent_router.classify(question)
        logger.info(f"Intent: {intent.value}, Params: {params}")

        if intent == Intent.GREETING:
            result = await self._handle_greeting(question)
        elif intent == Intent.UNKNOWN:
            result = await self._handle_unknown(shop_id, question)
        else:
            result = await self._handle_intent(intent, int(shop_id), params, question)

        result["query_type"] = intent.value
        result["processing_time"] = time.time() - start_time
        result["cached"] = False

        if use_cache and settings.enable_cache and result.get("answer"):
            await self.cache.set(
                f"{shop_id}:{question}",
                {
                    "answer": result["answer"],
                    "data": result.get("data"),
                    "query_type": result["query_type"],
                },
                ttl=settings.cache_ttl,
            )

        return result

    async def _handle_intent(
        self,
        intent: Intent,
        shop_id: int,
        params: Dict[str, Any],
        question: str
    ) -> Dict[str, Any]:
        try:
            tool_function = self.intent_to_function.get(intent)
            if not tool_function:
                logger.warning(f"No function mapped for intent: {intent.value}")
                return await self._handle_unknown(shop_id, question)

            logger.info(f"Calling tool: {tool_function.__name__} with params: {params}")
            tool_result = await tool_function(shop_id, **params)

            logger.info(f"Tool result: {tool_result}")

            answer = await self._format_answer_with_llm(question, tool_result, intent.value)

            return {
                "answer": answer,
                "data": tool_result,
                "metadata": {
                    "intent": intent.value,
                    "params": params,
                    "tool_used": tool_function.__name__
                }
            }

        except Exception as e:
            logger.error(f"Intent handling failed: {e}", exc_info=True)
            return {
                "answer": f"Sorry, I encountered an error: {str(e)}",
                "data": None,
                "metadata": {"error": str(e)}
            }

    async def _format_answer_with_llm(
        self,
        question: str,
        tool_result: Dict[str, Any],
        intent: str
    ) -> str:
        try:
            # Try LLM formatting but with shorter timeout
            prompt = f"""Question: {question}
Data: {tool_result}

Answer the question naturally using EXACT numbers from the data. Be brief."""

            response = await self.ollama.client.post(
                f"{self.ollama.base_url}/api/generate",
                json={
                    "model": self.ollama.model,
                    "prompt": prompt,
                    "stream": False,
                    "temperature": 0.1,
                },
                timeout=10
            )

            response.raise_for_status()
            result = response.json()
            answer = result.get("response", "").strip()

            # Validate LLM didn't hallucinate numbers
            if answer and "count" in tool_result:
                expected_count = str(tool_result["count"])
                if expected_count not in answer:
                    logger.warning(f"LLM hallucinated count. Expected {expected_count}, got: {answer}")
                    return self._fallback_format(question, tool_result, intent)

            if answer:
                return answer
            else:
                return self._fallback_format(question, tool_result, intent)

        except Exception as e:
            logger.error(f"LLM formatting failed: {e}")
            return self._fallback_format(question, tool_result, intent)

    def _fallback_format(
        self,
        question: str,
        tool_result: Dict[str, Any],
        intent: str
    ) -> str:
        if "count" in tool_result:
            count = tool_result["count"]
            time_period = tool_result.get("time_period", "")
            time_str = f" {time_period}" if time_period else ""

            if "product" in intent:
                return f"You have {count} products{time_str}."
            elif "order" in intent:
                return f"You have {count} orders{time_str}."
            elif "customer" in intent:
                return f"You have {count} customers{time_str}."
            elif "category" in intent:
                return f"You have {count} categories."

        if "total_revenue" in tool_result:
            revenue = tool_result["total_revenue"]
            order_count = tool_result.get("order_count", 0)
            time_period = tool_result.get("time_period", "")
            time_str = f" {time_period}" if time_period else ""

            return f"Your total revenue{time_str} is ${revenue:,.2f} from {order_count} orders."

        if "average_order_value" in tool_result:
            aov = tool_result["average_order_value"]
            return f"Your average order value is ${aov:,.2f}."

        if "top_products" in tool_result:
            products = tool_result["top_products"]
            if products:
                product_list = "\n".join([
                    f"{i+1}. {p.get('product_name', 'Unknown')} - {p.get('quantity_sold', 0)} sold"
                    for i, p in enumerate(products)
                ])
                return f"Your top selling products are:\n{product_list}"
            return "No products found."

        if "top_customers" in tool_result:
            customers = tool_result["top_customers"]
            if customers:
                customer_list = "\n".join([
                    f"{i+1}. {c.get('customer_name', 'Unknown')} - ${c.get('total_spent', 0):,.2f} spent"
                    for i, c in enumerate(customers)
                ])
                return f"Your top customers are:\n{customer_list}"
            return "No customers found."

        if "orders" in tool_result:
            orders = tool_result["orders"]
            count = len(orders)
            return f"Found {count} recent orders."

        return f"Result: {str(tool_result)[:200]}"

    async def _handle_greeting(self, question: str) -> Dict[str, Any]:
        responses = {
            "default": "Hello! I'm your e-commerce analytics assistant. Ask me about your products, orders, customers, or revenue."
        }

        return {
            "answer": responses["default"],
            "data": None,
            "metadata": {}
        }

    async def _handle_unknown(self, shop_id: int, question: str) -> Dict[str, Any]:
        return {
            "answer": "Sorry, I couldn't understand your question. Try asking about:\n- Product count\n- Order count\n- Revenue\n- Top products or customers\n- Recent orders",
            "data": None,
            "metadata": {"fallback": True}
        }


function_orchestrator = FunctionOrchestrator()
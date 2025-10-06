"""
Hugging Face Response Generator
Generates natural language responses without Ollama dependency
"""

import logging
from typing import Dict, Any, Optional
import json

logger = logging.getLogger(__name__)


class HFResponseGenerator:
    """Generate natural language responses using Hugging Face models."""

    def __init__(self):
        self.generator = None
        self.initialized = False
        self._initialize_generator()

    def _initialize_generator(self):
        """Initialize text generation model."""
        try:
            from transformers import pipeline
            # Try multiple models in order of preference
            models_to_try = [
                # GPT-2 style models - much more natural and conversational
                ("distilgpt2", "text-generation"),                 # 82MB, natural conversational responses
                ("gpt2", "text-generation"),                        # 548MB, better quality
                # Fallback to instruction models
                ("google/flan-t5-base", "text2text-generation"),   # 250MB
                ("google/flan-t5-small", "text2text-generation"),  # 80MB
            ]

            for model_name, task in models_to_try:
                try:
                    logger.info(f"Trying to load {model_name}...")
                    self.generator = pipeline(
                        task,
                        model=model_name,
                        device=-1,  # CPU
                        max_length=200
                    )
                    self.initialized = True
                    self.model_name = model_name
                    self.task = task
                    logger.info(f"HF Response Generator initialized with {model_name}")
                    return
                except Exception as e:
                    logger.warning(f"Failed to load {model_name}: {e}")
                    continue

            # If all fail, mark as not initialized
            self.initialized = False
            logger.warning("All HF models failed. Using template-based responses.")

        except Exception as e:
            logger.warning(f"HF generator initialization failed: {e}. Using template-based responses.")
            self.initialized = False

    def generate_response(self, data: Dict[str, Any], question: str,
                         tool_name: str) -> str:
        """
        Generate natural language response from query results.

        Args:
            data: Query result data
            question: Original user question
            tool_name: Tool that was used

        Returns:
            Natural language response string
        """
        # If HF model available, use it to generate natural response
        if self.initialized and self.generator:
            try:
                logger.info(f"Attempting HF generation for: {question[:50]}")
                enhanced = self._enhance_with_hf(question, data, tool_name)
                if enhanced:
                    logger.info(f"Generated successfully: {enhanced[:100]}")
                    return enhanced
                else:
                    logger.warning("Generation returned None, using template")
            except Exception as e:
                logger.warning(f"HF generation failed: {e}", exc_info=True)

        # Fallback to template-based response
        logger.info("Using template-based response")
        template_response = self._generate_template_response(data, question, tool_name)
        return template_response

    def _generate_template_response(self, data: Dict[str, Any], question: str,
                                   tool_name: str) -> str:
        """Generate response using templates (fast, reliable)."""

        question_lower = question.lower()

        # Count queries
        if tool_name == "count_documents":
            count = data.get("count", 0)
            collection = self._extract_collection_from_question(question)
            if count == 0:
                return f"You don't have any {collection}s in the system."
            elif count == 1:
                return f"You have 1 {collection}."
            else:
                return f"You have {count} {collection}s."

        # Sum queries
        elif tool_name == "calculate_sum":
            results = data.get("result", [])
            if results and len(results) > 0:
                total = results[0].get("total", 0)
                count = results[0].get("count", 0)
                if total > 0:
                    # Make it more natural based on question
                    if "may" in question_lower or "month" in question_lower or "year" in question_lower or "week" in question_lower:
                        return f"Your total sales for the period were ${total:,.2f} from {count} orders."
                    else:
                        return f"The total sales are ${total:,.2f} from {count} orders."
            return "I don't see any sales data for the specified period."

        # Average queries
        elif tool_name == "calculate_average":
            results = data.get("result", [])
            if results and len(results) > 0:
                avg = results[0].get("average", 0)
                count = results[0].get("count", 0)
                if avg > 0:
                    return f"The average order value is ${avg:,.2f} based on {count} orders."
            return "I couldn't calculate the average for the specified period."

        # Top customers
        elif tool_name == "get_top_customers_by_spending":
            customers = data.get("customers", [])
            if customers:
                top_list = []
                for i, c in enumerate(customers[:5], 1):
                    name = c.get("name", f"Customer {c.get('user_id', 'Unknown')}")
                    spent = c.get("total_spent", 0)
                    orders = c.get("order_count", 0)
                    top_list.append(f"{i}. {name}: ${spent:,.2f} ({orders} orders)")
                return "Top customers by spending:\n" + "\n".join(top_list)
            return "No customer data found."

        # Best selling products
        elif tool_name == "get_best_selling_products":
            products = data.get("products", [])
            if products:
                top_list = []
                for i, p in enumerate(products[:10], 1):
                    name = p.get("name", f"Product {p.get('product_id', 'Unknown')}")
                    quantity = p.get("total_quantity", 0)
                    revenue = p.get("total_revenue", 0)
                    top_list.append(f"{i}. {name}: {quantity} sold, ${revenue:,.2f} revenue")
                return "Best selling products:\n" + "\n".join(top_list)
            return "No product sales data found."

        # Group and count
        elif tool_name == "group_and_count":
            groups = data.get("groups", [])
            if groups:
                # Check if groups have 'total' field (revenue/sum)
                if groups[0].get("total") is not None:
                    summary = ", ".join([f"{g['_id']}: ${g['total']:,.2f} ({g['count']} orders)" for g in groups[:10]])
                    return f"Revenue breakdown: {summary}"
                else:
                    summary = ", ".join([f"{g['_id']}: {g['count']}" for g in groups[:10]])
                    return f"Breakdown: {summary}"
            return "No groups found."

        # Find documents
        elif tool_name == "find_documents":
            count = data.get("count", 0)
            collection = self._extract_collection_from_question(question)
            return f"Found {count} {collection}{'s' if count != 1 else ''} matching your criteria."

        # Date range
        elif tool_name == "get_date_range":
            documents = data.get("documents", [])
            count = len(documents) if documents else 0
            return f"Found {count} orders from the specified date range."

        # Generic fallback
        else:
            return "Query completed successfully."

    def _enhance_with_hf(self, question: str, data: Dict[str, Any],
                        tool_name: str) -> Optional[str]:
        """
        Generate natural language response with variety using template variations.

        Since LLMs hallucinate on factual data, we use randomized templates for variety
        while keeping facts accurate.
        """
        try:
            import random

            # Use template-based responses with variations for natural feel
            return self._generate_varied_template_response(data, question, tool_name)

        except Exception as e:
            logger.error(f"Response generation failed: {e}", exc_info=True)
            return None

    def _generate_varied_template_response(self, data: Dict[str, Any], question: str,
                                          tool_name: str) -> str:
        """Generate varied natural language responses using randomized templates."""
        import random

        question_lower = question.lower()

        # Count queries
        if tool_name == "count_documents":
            count = data.get("count", 0)
            collection = self._extract_collection_from_question(question)

            if count == 0:
                templates = [
                    f"You don't have any {collection}s in the system.",
                    f"There are no {collection}s currently in your database.",
                    f"I couldn't find any {collection}s.",
                    f"No {collection}s found in the system."
                ]
            elif count == 1:
                templates = [
                    f"You have 1 {collection}.",
                    f"There is 1 {collection} in your system.",
                    f"I found 1 {collection}.",
                ]
            else:
                templates = [
                    f"You have {count} {collection}s.",
                    f"There are {count} {collection}s in your system.",
                    f"I found {count} {collection}s.",
                    f"Your store has {count} {collection}s.",
                ]
            return random.choice(templates)

        # Sum queries
        elif tool_name == "calculate_sum":
            results = data.get("result", [])
            if results and len(results) > 0:
                total = results[0].get("total", 0)
                count = results[0].get("count", 0)
                if total > 0:
                    templates = [
                        f"Your total sales were ${total:,.2f} from {count} orders.",
                        f"You generated ${total:,.2f} in sales across {count} orders.",
                        f"The total is ${total:,.2f} based on {count} orders.",
                        f"Total sales: ${total:,.2f} ({count} orders).",
                        f"You had ${total:,.2f} in revenue from {count} orders.",
                        f"Sales totaled ${total:,.2f} with {count} orders placed.",
                    ]
                    return random.choice(templates)

            templates = [
                "I don't see any sales data for the specified period.",
                "No sales found for this period.",
                "There were no sales during this time frame.",
                "No revenue data available for the requested period."
            ]
            return random.choice(templates)

        # Average queries
        elif tool_name == "calculate_average":
            results = data.get("result", [])
            if results and len(results) > 0:
                avg = results[0].get("average", 0)
                count = results[0].get("count", 0)
                if avg > 0:
                    templates = [
                        f"The average order value is ${avg:,.2f} based on {count} orders.",
                        f"Average order value: ${avg:,.2f} ({count} orders).",
                        f"You're averaging ${avg:,.2f} per order across {count} orders.",
                        f"Each order averages ${avg:,.2f} based on {count} total orders.",
                    ]
                    return random.choice(templates)

            templates = [
                "I couldn't calculate the average for the specified period.",
                "No data available to calculate averages.",
                "Unable to determine average - no orders found."
            ]
            return random.choice(templates)

        # Top customers
        elif tool_name == "get_top_customers_by_spending":
            customers = data.get("customers", [])
            if customers:
                top_list = []
                for i, c in enumerate(customers[:5], 1):
                    name = c.get("name", f"Customer {c.get('user_id', 'Unknown')}")
                    spent = c.get("total_spent", 0)
                    orders = c.get("order_count", 0)
                    top_list.append(f"{i}. {name}: ${spent:,.2f} ({orders} orders)")

                headers = [
                    "Top customers by spending:",
                    "Here are your top customers:",
                    "Best customers by revenue:",
                    "Your highest-spending customers:"
                ]
                return random.choice(headers) + "\n" + "\n".join(top_list)
            return "No customer data found."

        # Best selling products
        elif tool_name == "get_best_selling_products":
            products = data.get("products", [])
            if products:
                top_list = []
                for i, p in enumerate(products[:10], 1):
                    name = p.get("name", f"Product {p.get('product_id', 'Unknown')}")
                    quantity = p.get("total_quantity", 0)
                    revenue = p.get("total_revenue", 0)
                    top_list.append(f"{i}. {name}: {quantity} sold, ${revenue:,.2f} revenue")

                headers = [
                    "Best selling products:",
                    "Top products by sales:",
                    "Your best-performing products:",
                    "Most popular products:"
                ]
                return random.choice(headers) + "\n" + "\n".join(top_list)
            return "No product sales data found."

        # Group and count
        elif tool_name == "group_and_count":
            groups = data.get("groups", [])
            if groups:
                if groups[0].get("total") is not None:
                    summary = ", ".join([f"{g['_id']}: ${g['total']:,.2f} ({g['count']} orders)" for g in groups[:10]])
                    templates = [
                        f"Revenue breakdown: {summary}",
                        f"Sales by category: {summary}",
                        f"Here's the breakdown: {summary}"
                    ]
                else:
                    summary = ", ".join([f"{g['_id']}: {g['count']}" for g in groups[:10]])
                    templates = [
                        f"Breakdown: {summary}",
                        f"Count by category: {summary}",
                        f"Here's the distribution: {summary}"
                    ]
                return random.choice(templates)
            return "No groups found."

        # Find documents
        elif tool_name == "find_documents":
            count = data.get("count", 0)
            collection = self._extract_collection_from_question(question)
            templates = [
                f"Found {count} {collection}{'s' if count != 1 else ''} matching your criteria.",
                f"I found {count} matching {collection}{'s' if count != 1 else ''}.",
                f"{count} {collection}{'s' if count != 1 else ''} match your search.",
            ]
            return random.choice(templates)

        # Date range
        elif tool_name == "get_date_range":
            documents = data.get("documents", [])
            count = len(documents) if documents else 0
            templates = [
                f"Found {count} orders from the specified date range.",
                f"I found {count} orders in that time period.",
                f"{count} orders match the date range you specified.",
            ]
            return random.choice(templates)

        # Generic fallback
        else:
            return "Query completed successfully."

    def _check_has_data(self, data: Dict[str, Any], tool_name: str) -> bool:
        """Check if there's actual data to report (prevents hallucination)."""
        # For sum/average, check if total exists and > 0
        if tool_name in ["calculate_sum", "calculate_average"]:
            results = data.get("result", [])
            if not results or len(results) == 0:
                return False
            total = results[0].get("total") or results[0].get("average")
            if total is None or total == 0:
                return False
            return True  # Has data!

        # For count
        if tool_name == "count_documents":
            count = data.get("count", 0)
            return count > 0

        # For documents/lists
        if data.get("result") == [] or data.get("result") is None:
            return False

        if data.get("documents") == [] or data.get("documents") is None:
            return False

        if data.get("products") == [] or data.get("products") is None:
            return False

        if data.get("customers") == [] or data.get("customers") is None:
            return False

        if data.get("groups") == [] or data.get("groups") is None:
            return False

        return True

    def _extract_data_context(self, data: Dict[str, Any]) -> str:
        """Extract meaningful context from data for prompt."""
        context_parts = []

        # Extract counts
        if "count" in data:
            context_parts.append(f"Count: {data['count']}")

        # Extract result data
        if "result" in data:
            results = data["result"]
            if isinstance(results, list) and len(results) > 0:
                first = results[0]
                if "total" in first:
                    total = first.get('total', 0)
                    if total == 0 or total is None:
                        context_parts.append("Total: $0 (no data in this period)")
                    else:
                        context_parts.append(f"Total: ${total:,.2f}")
                if "average" in first:
                    context_parts.append(f"Average: ${first['average']:,.2f}")
                if "count" in first:
                    count = first.get('count', 0)
                    context_parts.append(f"Item count: {count}")
            else:
                context_parts.append("No results found")

        # Extract customer data
        if "customers" in data:
            customers = data["customers"]
            if isinstance(customers, list):
                if len(customers) == 0:
                    context_parts.append("No customers found")
                else:
                    context_parts.append(f"Number of customers: {len(customers)}")
                    # Add top customer info
                    top = customers[0]
                    context_parts.append(f"Top customer: {top.get('name', 'Unknown')} - ${top.get('total_spent', 0):,.2f}")

        # Extract product data
        if "products" in data:
            products = data["products"]
            if isinstance(products, list):
                if len(products) == 0:
                    context_parts.append("No products found")
                else:
                    context_parts.append(f"Number of products: {len(products)}")

        # Extract groups
        if "groups" in data:
            groups = data["groups"]
            if isinstance(groups, list):
                if len(groups) == 0:
                    context_parts.append("No groups found")
                else:
                    context_parts.append(f"Groups found: {len(groups)}")
                    for g in groups[:5]:  # Top 5 groups
                        context_parts.append(f"- {g.get('_id', 'Unknown')}: {g.get('count', 0)} items")

        # Extract documents
        if "documents" in data:
            docs = data["documents"]
            if isinstance(docs, list):
                if len(docs) == 0:
                    context_parts.append("No documents found")
                else:
                    context_parts.append(f"Documents found: {len(docs)}")

        return "\n".join(context_parts) if context_parts else "No data available for the specified query"

    def _extract_collection_from_question(self, question: str) -> str:
        """Extract collection name from question."""
        question_lower = question.lower()

        if "product" in question_lower:
            return "product"
        elif "customer" in question_lower or "user" in question_lower:
            return "customer"
        elif "category" in question_lower or "categories" in question_lower:
            return "category"
        elif "order" in question_lower:
            return "order"
        else:
            return "item"

    def format_data_summary(self, data: Any, max_items: int = 5) -> str:
        """Format data into readable summary."""
        if isinstance(data, list):
            if len(data) == 0:
                return "No results found."
            elif len(data) <= max_items:
                return f"Found {len(data)} result(s)."
            else:
                return f"Found {len(data)} results (showing top {max_items})."
        elif isinstance(data, dict):
            if "count" in data:
                return f"Count: {data['count']}"
            elif "total" in data:
                return f"Total: {data['total']}"
        return "Results retrieved."


# Global instance
hf_response_generator = HFResponseGenerator()
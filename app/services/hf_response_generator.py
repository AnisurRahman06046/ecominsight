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
                ("google/flan-t5-base", "text2text-generation"),  # Better quality, 250MB
                ("facebook/bart-large-cnn", "summarization"),      # Good for natural text
                ("google/flan-t5-small", "text2text-generation"),  # Fallback
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
        # Try template-based first (faster, more reliable)
        template_response = self._generate_template_response(data, question, tool_name)

        # If HF model available, optionally enhance the response
        if self.initialized and self.generator:
            try:
                enhanced = self._enhance_with_hf(template_response, question, data)
                return enhanced if enhanced else template_response
            except Exception as e:
                logger.warning(f"HF enhancement failed: {e}")
                return template_response

        return template_response

    def _generate_template_response(self, data: Dict[str, Any], question: str,
                                   tool_name: str) -> str:
        """Generate response using templates (fast, reliable)."""

        # Count queries
        if tool_name == "count_documents":
            count = data.get("count", 0)
            collection = self._extract_collection_from_question(question)
            return f"You have {count} {collection}{'s' if count != 1 else ''}."

        # Sum queries
        elif tool_name == "calculate_sum":
            results = data.get("result", [])
            if results and len(results) > 0:
                total = results[0].get("total", 0)
                return f"Total: ${total:,.2f}"
            return "Could not calculate sum."

        # Average queries
        elif tool_name == "calculate_average":
            results = data.get("result", [])
            if results and len(results) > 0:
                avg = results[0].get("average", 0)
                count = results[0].get("count", 0)
                return f"Average: ${avg:,.2f} (based on {count} items)"
            return "Could not calculate average."

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

    def _enhance_with_hf(self, template_response: str, question: str,
                        data: Dict[str, Any]) -> Optional[str]:
        """
        Enhance template response using HF model with full context.

        This makes the response more natural and conversational.
        """
        try:
            # Extract actual data values for better context
            data_summary = self._extract_data_context(data)

            # Create a comprehensive prompt with question, data, and template
            if hasattr(self, 'model_name') and 'phi-2' in self.model_name:
                # Phi-2 is a causal LM - needs instruct-style prompt
                prompt = f"""Instruct: You are a helpful e-commerce analytics assistant. Answer the user's question clearly and concisely based on the data provided.

User Question: {question}

Data Available:
{data_summary}

Provide a single, clear sentence answer:
Output:"""

            elif hasattr(self, 'model_name') and 'flan-t5' in self.model_name:
                # FLAN-T5 works best with clear instructions and context
                prompt = f"""You are a helpful e-commerce analytics assistant. Answer the user's question based on the data provided.

User Question: {question}

Data Available:
{data_summary}

Current Answer: {template_response}

Provide a natural, clear answer to the user's question using the data:"""

            else:
                # For other models
                prompt = f"""Convert this data into a natural response.

Question: {question}
Data: {data_summary}
Template: {template_response}

Natural response:"""

            # Generate
            if hasattr(self.generator, 'task') and self.generator.task == 'text-generation':
                # For causal LM models like Phi-2
                result = self.generator(
                    prompt,
                    max_new_tokens=100,
                    min_new_tokens=10,
                    do_sample=False,  # Deterministic
                    num_return_sequences=1,
                    pad_token_id=50256  # Use GPT-2 pad token
                )
                generated = result[0]['generated_text']
                # Extract only the generated part (remove prompt)
                enhanced = generated[len(prompt):].strip()
            else:
                # For text2text generation (FLAN-T5)
                result = self.generator(
                    prompt,
                    max_length=200,
                    min_length=10,
                    do_sample=False,  # Deterministic
                    num_return_sequences=1
                )
                enhanced = result[0]['generated_text'].strip()

            # Validate the enhanced response
            if enhanced and len(enhanced) > 15 and not enhanced.startswith("Question:"):
                logger.info(f"Enhanced response: {enhanced[:100]}")
                return enhanced
            else:
                logger.debug("Enhanced response not good enough, using template")
                return None

        except Exception as e:
            logger.debug(f"HF enhancement failed: {e}")
            return None

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
                    context_parts.append(f"Total: ${first['total']:,.2f}")
                if "average" in first:
                    context_parts.append(f"Average: ${first['average']:,.2f}")
                if "count" in first:
                    context_parts.append(f"Item count: {first['count']}")

        # Extract customer data
        if "customers" in data:
            customers = data["customers"]
            if isinstance(customers, list) and len(customers) > 0:
                context_parts.append(f"Number of customers: {len(customers)}")
                # Add top customer info
                if len(customers) > 0:
                    top = customers[0]
                    context_parts.append(f"Top customer: {top.get('name', 'Unknown')} - ${top.get('total_spent', 0):,.2f}")

        # Extract product data
        if "products" in data:
            products = data["products"]
            if isinstance(products, list) and len(products) > 0:
                context_parts.append(f"Number of products: {len(products)}")

        # Extract groups
        if "groups" in data:
            groups = data["groups"]
            if isinstance(groups, list) and len(groups) > 0:
                context_parts.append(f"Groups found: {len(groups)}")
                for g in groups[:5]:  # Top 5 groups
                    context_parts.append(f"- {g.get('_id', 'Unknown')}: {g.get('count', 0)} items")

        # Extract documents
        if "documents" in data:
            docs = data["documents"]
            if isinstance(docs, list):
                context_parts.append(f"Documents found: {len(docs)}")

        return "\n".join(context_parts) if context_parts else "No specific data available"

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
"""
Few-Shot Response Generator
Uses conversational LLM for natural language generation with role-based prompting
"""

import logging
from typing import Dict, Any, Optional, List
from transformers import AutoTokenizer, AutoModelForCausalLM
import torch

logger = logging.getLogger(__name__)


class FewShotResponseGenerator:
    """Generate natural language responses using conversational models with few-shot prompting."""

    def __init__(self, model_name: str = "TinyLlama/TinyLlama-1.1B-Chat-v1.0"):
        """
        Initialize with conversational model.

        Options (all open-source, no auth):
        - TinyLlama/TinyLlama-1.1B-Chat-v1.0 (~2.2GB, FAST - RECOMMENDED for quick responses)
        - microsoft/phi-2 (~5GB, Better quality)
        - HuggingFaceH4/zephyr-7b-beta (~15GB, Best quality but slow)

        These models support proper chat format with system/user/assistant roles!
        """
        self.model_name = model_name
        self.tokenizer = None
        self.model = None
        self.initialized = False
        self._initialize_model()

    def _initialize_model(self):
        """Initialize the conversational model."""
        try:
            logger.info(f"Loading conversational model: {self.model_name}...")

            self.tokenizer = AutoTokenizer.from_pretrained(self.model_name)
            self.model = AutoModelForCausalLM.from_pretrained(
                self.model_name,
                torch_dtype=torch.float16 if torch.cuda.is_available() else torch.float32,
                device_map="auto" if torch.cuda.is_available() else None,
                low_cpu_mem_usage=True
            )

            # Set pad token if not set
            if self.tokenizer.pad_token is None:
                self.tokenizer.pad_token = self.tokenizer.eos_token

            self.initialized = True
            logger.info(f"✓ Conversational model loaded successfully: {self.model_name}")

        except Exception as e:
            logger.error(f"Failed to load {self.model_name}: {e}")

            # Fallback to TinyLlama
            if self.model_name != "TinyLlama/TinyLlama-1.1B-Chat-v1.0":
                try:
                    logger.info("Falling back to TinyLlama/TinyLlama-1.1B-Chat-v1.0...")
                    self.model_name = "TinyLlama/TinyLlama-1.1B-Chat-v1.0"
                    self.tokenizer = AutoTokenizer.from_pretrained(self.model_name)
                    self.model = AutoModelForCausalLM.from_pretrained(
                        self.model_name,
                        torch_dtype=torch.float16 if torch.cuda.is_available() else torch.float32,
                        low_cpu_mem_usage=True
                    )

                    if self.tokenizer.pad_token is None:
                        self.tokenizer.pad_token = self.tokenizer.eos_token

                    self.initialized = True
                    logger.info(f"✓ Fallback model loaded: {self.model_name}")
                except Exception as fallback_error:
                    logger.error(f"Fallback failed: {fallback_error}")
                    self.initialized = False
            else:
                self.initialized = False

    def _build_chat_messages(self, question: str, data_summary: str) -> List[Dict[str, str]]:
        """
        Build chat messages with system prompt and few-shot examples.
        This is the proper way to do few-shot prompting with conversational models!
        """
        messages = [
            {
                "role": "system",
                "content": "You are a helpful e-commerce analytics assistant. Answer queries about sales data in natural, varied language. Be concise and include specific numbers from the data. IMPORTANT: Match the time period from the user's question exactly - if they ask about 'today', say 'today' in your response, if 'yesterday', say 'yesterday', etc. Never mix up time periods."
            },
            # Few-shot examples as conversation history
            {
                "role": "user",
                "content": "What is my total sales today? Data: Total sales: $1,850.00 (2 orders)"
            },
            {
                "role": "assistant",
                "content": "Today you received 2 orders totaling $1,850.00."
            },
            {
                "role": "user",
                "content": "What are my sales today? Data: Total sales: $4,960.00 (5 orders)"
            },
            {
                "role": "assistant",
                "content": "You've made $4,960.00 in sales today from 5 orders."
            },
            {
                "role": "user",
                "content": "What is my total sales yesterday? Data: Total sales: $33,210.00 (32 orders)"
            },
            {
                "role": "assistant",
                "content": "Yesterday you had 32 orders, bringing in $33,210.00 in revenue."
            },
            {
                "role": "user",
                "content": "What is my total revenue this week? Data: Total sales: $5,430.00 (15 orders)"
            },
            {
                "role": "assistant",
                "content": "This week's performance: 15 orders worth $5,430.00."
            },
            {
                "role": "user",
                "content": "Total sales today? Data: Total sales: $950.00 (3 orders)"
            },
            {
                "role": "assistant",
                "content": "Your store generated $950.00 from 3 orders today."
            },
            {
                "role": "user",
                "content": "How much revenue today? Data: Total sales: $12,340.00 (8 orders)"
            },
            {
                "role": "assistant",
                "content": "Today's revenue is $12,340.00 from 8 orders."
            },
            # The actual user query
            {
                "role": "user",
                "content": f"{question} Data: {data_summary}"
            }
        ]

        return messages

    def generate_response(self, question: str, data: Dict[str, Any],
                         tool_name: str) -> Optional[str]:
        """
        Generate natural language response using conversational model.

        Args:
            question: User's question
            data: Query result data
            tool_name: Tool that was used

        Returns:
            Natural language response or None if generation fails
        """
        if not self.initialized:
            logger.warning("Model not initialized")
            return None

        try:
            # For list-based tools with multiple items, return formatted data directly
            # Only use LLM for simple single-value responses (calculate_sum, calculate_average)
            if tool_name in ["get_best_selling_products", "get_top_customers_by_spending", "group_and_count"]:
                direct_response = self._extract_data_context(data, tool_name, question)
                logger.info(f"Direct response (no LLM): '{direct_response[:100]}'")
                return direct_response

            # Extract data context
            data_summary = self._extract_data_context(data, tool_name, question)

            # Check if no data
            if "No" in data_summary and ("found" in data_summary or "available" in data_summary):
                return data_summary

            # Build chat messages with few-shot examples
            messages = self._build_chat_messages(question, data_summary)

            # Format using chat template (proper way for conversational models)
            formatted_prompt = self.tokenizer.apply_chat_template(
                messages,
                tokenize=False,
                add_generation_prompt=True
            )

            # Tokenize
            inputs = self.tokenizer(
                formatted_prompt,
                return_tensors="pt",
                truncation=True,
                max_length=1024
            )

            # Move to same device as model
            if torch.cuda.is_available():
                inputs = {k: v.to(self.model.device) for k, v in inputs.items()}

            # Generate with sampling for variation
            outputs = self.model.generate(
                **inputs,
                max_new_tokens=80,
                do_sample=True,
                temperature=0.9,  # Good balance of creativity and coherence
                top_p=0.95,
                top_k=50,
                repetition_penalty=1.2,
                pad_token_id=self.tokenizer.pad_token_id,
                eos_token_id=self.tokenizer.eos_token_id
            )

            # Decode only the new tokens (not the prompt)
            response = self.tokenizer.decode(
                outputs[0][inputs['input_ids'].shape[1]:],
                skip_special_tokens=True
            ).strip()

            logger.info(f"Generated response: '{response[:100]}'")

            # Validate response quality
            if not self._validate_response(response, question, data_summary):
                logger.warning(f"Response validation failed: '{response}'")
                return None

            return response

        except Exception as e:
            logger.error(f"Response generation failed: {e}", exc_info=True)
            return None

    def _validate_response(self, response: str, question: str, data_summary: str) -> bool:
        """
        Validate that the generated response makes sense.
        """
        # Basic validation
        if len(response) < 3:
            return False

        if len(response) > 500:
            logger.warning(f"Response too long: {len(response)} chars")
            return False

        response_lower = response.lower()
        question_lower = question.lower()

        # Check for nonsense patterns
        nonsense_patterns = [
            "as an ai" in response_lower,
            "i cannot" in response_lower,
            "i don't have access" in response_lower,
            len(response.split()) < 4,  # Too short
        ]

        if any(nonsense_patterns):
            logger.warning(f"Nonsense pattern detected in response: {response[:50]}")
            return False

        # Must contain data-related content for analytics questions
        analytics_keywords = ["revenue", "sales", "order", "customer", "product", "count", "total", "$"]
        is_analytics_query = any(kw in question_lower for kw in ["how many", "total", "revenue", "sales", "average", "top", "customer", "product", "order"])

        if is_analytics_query:
            has_data_reference = any(kw in response_lower for kw in analytics_keywords) or any(char.isdigit() for char in response)
            if not has_data_reference:
                logger.warning(f"Analytics query but no data in response: {response[:50]}")
                return False

        return True

    def _extract_data_context(self, data: Dict[str, Any], tool_name: str, question: str = "") -> str:
        """Extract data context for prompt."""

        # Count queries
        if tool_name == "count_documents":
            count = data.get("count", 0)
            return f"Count: {count}"

        # Sum queries
        elif tool_name == "calculate_sum":
            results = data.get("result", [])
            if results and len(results) > 0:
                total = results[0].get("total", 0)
                count = results[0].get("count", 0)

                # Format based on count
                if count > 0:
                    if count == 1:
                        return f"Total sales: ${total:,.2f} (1 order)"
                    else:
                        return f"Total sales: ${total:,.2f} ({count:,} orders)"
                else:
                    return "No sales data found for this period"
            return "No sales data available"

        # Average queries
        elif tool_name == "calculate_average":
            results = data.get("result", [])
            if results and len(results) > 0:
                avg = results[0].get("average", 0) or 0
                count = results[0].get("count", 0) or 0
                if avg > 0:
                    return f"Average: ${avg:,.2f} ({count:,} orders)"
                else:
                    return f"Unable to calculate average from {count:,} orders"
            return "No data available to calculate average"

        # Top customers
        elif tool_name == "get_top_customers_by_spending":
            customers = data.get("customers", [])
            if customers:
                if len(customers) == 1:
                    top = customers[0]
                    name = top.get("name", "Unknown")
                    spent = top.get("total_spent", 0)
                    return f"Top customer: {name}, Total spent: ${spent:,.2f}"
                else:
                    customer_list = []
                    for i, c in enumerate(customers, 1):
                        name = c.get("name", "Unknown")
                        spent = c.get("total_spent", 0)
                        orders = c.get("order_count", 0)
                        customer_list.append(f"{i}. {name} - Spent: ${spent:,.2f}, Orders: {orders}")
                    return "Top customers by spending:\n" + "\n".join(customer_list)
            return "No customers found"

        # Best selling products
        elif tool_name == "get_best_selling_products":
            products = data.get("products", [])
            if products:
                if len(products) == 1:
                    top = products[0]
                    name = top.get("name", "Unknown")
                    quantity = top.get("total_quantity", 0)
                    return f"Top product: {name}, Quantity sold: {quantity}"
                else:
                    product_list = []
                    for i, p in enumerate(products, 1):
                        name = p.get("name", "Unknown")
                        quantity = p.get("total_quantity", 0)
                        revenue = p.get("total_revenue", 0)
                        product_list.append(f"{i}. {name} - Sold: {quantity:.0f} units, Revenue: ${revenue:,.2f}")
                    return "Top selling products:\n" + "\n".join(product_list)
            return "No products found"

        # Group and count
        elif tool_name == "group_and_count":
            groups = data.get("groups", [])
            if groups:
                question_lower = question.lower()
                wants_top_only = any(pattern in question_lower for pattern in [
                    "which", "what", "highest", "most", "best", "top", "largest", "biggest",
                    "lowest", "least", "worst", "fewest", "smallest", "bottom"
                ]) and not any(pattern in question_lower for pattern in [
                    "breakdown", "distribution", "all", "list", "show all"
                ])

                if wants_top_only and len(groups) > 0:
                    top_group = groups[0]
                    group_id = top_group.get("_id")
                    count = top_group.get("count", 0)

                    is_lowest_query = any(kw in question_lower for kw in [
                        "lowest", "least", "minimum", "fewest", "smallest", "worst", "bottom"
                    ])
                    superlative = "lowest" if is_lowest_query else "highest"

                    if isinstance(group_id, dict):
                        if "day" in group_id and "month" in group_id and "year" in group_id:
                            return f"{group_id['year']}-{group_id['month']:02d}-{group_id['day']:02d} has the {superlative} orders with {count:,}."
                        elif "month" in group_id and "year" in group_id:
                            month_names = ["", "January", "February", "March", "April", "May", "June",
                                         "July", "August", "September", "October", "November", "December"]
                            month_name = month_names[group_id["month"]]
                            year = group_id["year"]
                            return f"{month_name} {year} has the {superlative} orders with {count:,} orders."
                    else:
                        return f"{group_id} has the {superlative} with {count:,} orders."
                else:
                    result_list = []
                    for i, g in enumerate(groups[:10], 1):
                        group_id = g.get("_id")
                        count = g.get("count", 0)

                        if isinstance(group_id, dict):
                            if "day" in group_id and "month" in group_id and "year" in group_id:
                                result_list.append(f"{i}. {group_id['year']}-{group_id['month']:02d}-{group_id['day']:02d}: {count:,} orders")
                            elif "month" in group_id and "year" in group_id:
                                month_names = ["", "Jan", "Feb", "Mar", "Apr", "May", "Jun",
                                             "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
                                month_name = month_names[group_id["month"]]
                                result_list.append(f"{i}. {month_name} {group_id['year']}: {count:,} orders")
                        else:
                            result_list.append(f"{i}. {group_id}: {count:,}")

                    return "Breakdown:\n" + "\n".join(result_list)
            return "No data found for grouping"

        # Generic
        else:
            count = data.get("count", 0)
            return f"Count: {count}"


# Global instance
few_shot_response_generator = FewShotResponseGenerator()

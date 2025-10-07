"""
Few-Shot Response Generator
Uses Flan-T5 for accurate data-to-text generation
"""

import logging
from typing import Dict, Any, Optional
from transformers import AutoTokenizer, AutoModelForSeq2SeqLM

logger = logging.getLogger(__name__)


class FewShotResponseGenerator:
    """Generate natural language responses using Flan-T5 (instruction-tuned model)."""

    def __init__(self, model_name: str = "google/flan-t5-base"):
        """
        Initialize with instruction-tuned model.

        Options (all open-source, no auth):
        - google/flan-t5-base (250MB, BEST for data-to-text - RECOMMENDED)
        - google/flan-t5-large (780MB, slightly better quality)

        Flan-T5 is instruction-tuned for following prompts accurately,
        perfect for converting structured data to natural language!
        Note: GPT-2 hallucinates, don't use for factual data.
        """
        self.model_name = model_name
        self.tokenizer = None
        self.model = None
        self.initialized = False
        self._initialize_model()

    def _initialize_model(self):
        """Initialize the Flan-T5 model for data-to-text."""
        try:
            logger.info(f"Loading Flan-T5 model: {self.model_name}...")

            self.tokenizer = AutoTokenizer.from_pretrained(self.model_name)
            self.model = AutoModelForSeq2SeqLM.from_pretrained(self.model_name)

            self.initialized = True
            logger.info(f"✓ Flan-T5 loaded successfully: {self.model_name}")

        except Exception as e:
            logger.error(f"Failed to load {self.model_name}: {e}")

            # Fallback to base model
            if self.model_name != "google/flan-t5-base":
                try:
                    logger.info("Falling back to google/flan-t5-base...")
                    self.model_name = "google/flan-t5-base"
                    self.tokenizer = AutoTokenizer.from_pretrained(self.model_name)
                    self.model = AutoModelForSeq2SeqLM.from_pretrained(self.model_name)

                    self.initialized = True
                    logger.info(f"✓ Fallback model loaded: {self.model_name}")
                except Exception as fallback_error:
                    logger.error(f"Fallback failed: {fallback_error}")
                    self.initialized = False
            else:
                self.initialized = False

    def _build_few_shot_prompt(self, question: str, data_summary: str) -> str:
        """
        Build instruction prompt for Flan-T5.
        Different prompts for different query types.
        """
        # Check if this is a count query or a sum/total query
        if "Count:" in data_summary and "Total:" not in data_summary:
            # Simple count query
            question_lower = question.lower()
            entity = "items"
            if "product" in question_lower:
                entity = "products"
            elif "order" in question_lower:
                entity = "orders"
            elif "customer" in question_lower:
                entity = "customers"
            elif "categor" in question_lower:
                entity = "categories"

            prompt = f"""Answer this e-commerce question naturally using the data provided.

Question: How many {entity} are there?
Data: {data_summary}
Answer: You have"""

        elif "Total:" in data_summary:
            # Sum/Total query - provide the total amount
            # Extract question context to determine if it's revenue, sales, etc.
            question_lower = question.lower()

            if "revenue" in question_lower:
                prompt = f"""Answer this question about total revenue.

Data: {data_summary}
Answer: The total revenue is"""
            else:
                prompt = f"""Answer this question about total sales.

Data: {data_summary}
Answer: The total sales amount is"""

        else:
            # Generic prompt
            prompt = f"""Convert this e-commerce data into a natural answer.

Data: {data_summary}
Natural answer:"""

        return prompt

    def generate_response(self, question: str, data: Dict[str, Any],
                         tool_name: str) -> Optional[str]:
        """
        Generate natural language response using Flan-T5.

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
            # For list-based tools and calculations, return formatted data directly
            # No need for Flan-T5 to rephrase structured data
            if tool_name in ["get_best_selling_products", "get_top_customers_by_spending", "calculate_average", "calculate_sum", "group_and_count"]:
                direct_response = self._extract_data_context(data, tool_name, question)
                logger.info(f"Direct response (no Flan-T5): '{direct_response[:100]}'")
                return direct_response

            # Extract data context
            data_summary = self._extract_data_context(data, tool_name, question)

            # Build instruction prompt (improved to prevent echoing)
            prompt = self._build_few_shot_prompt(question, data_summary)

            # Tokenize with Flan-T5
            inputs = self.tokenizer(
                prompt,
                return_tensors="pt",
                max_length=512,
                truncation=True
            )

            # Generate with Flan-T5 using deterministic beam search
            outputs = self.model.generate(
                inputs.input_ids,
                max_new_tokens=60,
                do_sample=False,  # Disable sampling for deterministic output
                num_beams=4,  # Use beam search for better quality
                early_stopping=True,
                no_repeat_ngram_size=3,
                repetition_penalty=1.2
            )

            response = self.tokenizer.decode(outputs[0], skip_special_tokens=True).strip()

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
        Prevents nonsense like "Thanks 10 times" or "Hello how are you" for analytics.
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
            # Conversational responses to analytics questions
            ("revenue" in question_lower or "sales" in question_lower or "total" in question_lower) and ("hello" in response_lower or "how are you" in response_lower),
            ("how many" in question_lower or "count" in question_lower) and ("thanks" in response_lower and "times" in response_lower),
            ("customer" in question_lower or "product" in question_lower) and len(response.split()) < 4,  # Too short for analytics
        ]

        if any(nonsense_patterns):
            logger.warning(f"Nonsense pattern detected in response: {response[:50]}")
            return False

        # Must contain data-related keywords for analytics questions
        analytics_keywords = ["revenue", "sales", "order", "customer", "product", "count", "total", "average", "$"]
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

                # Format based on count - more natural language
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
                avg = results[0].get("average", 0) or 0  # Handle None
                count = results[0].get("count", 0) or 0
                if avg > 0:
                    return f"The average order value is ${avg:,.2f} (based on {count:,} orders)"
                else:
                    return f"Unable to calculate average. Found {count:,} orders but average returned ${avg:,.2f}. This may be a data type issue."
            return "No data available to calculate average"

        # Top customers
        elif tool_name == "get_top_customers_by_spending":
            customers = data.get("customers", [])
            if customers:
                # Return multiple customers if requested
                if len(customers) == 1:
                    top = customers[0]
                    name = top.get("name", "Unknown")
                    spent = top.get("total_spent", 0)
                    return f"Top customer: {name}, Total spent: ${spent:,.2f}"
                else:
                    # Format multiple customers as a list
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
                # Return multiple products if requested
                if len(products) == 1:
                    top = products[0]
                    name = top.get("name", "Unknown")
                    quantity = top.get("total_quantity", 0)
                    return f"Top product: {name}, Quantity sold: {quantity}"
                else:
                    # Format multiple products as a list
                    product_list = []
                    for i, p in enumerate(products, 1):
                        name = p.get("name", "Unknown")
                        quantity = p.get("total_quantity", 0)
                        revenue = p.get("total_revenue", 0)
                        product_list.append(f"{i}. {name} - Sold: {quantity:.0f} units, Revenue: ${revenue:,.2f}")
                    return "Top selling products:\n" + "\n".join(product_list)
            return "No products found"

        # Group and count (time-based or field-based grouping)
        elif tool_name == "group_and_count":
            groups = data.get("groups", [])
            if groups:
                # Check if user wants just the top result ("which X has highest Y")
                question_lower = question.lower()
                wants_top_only = any(pattern in question_lower for pattern in [
                    "which", "what", "highest", "most", "best", "top", "largest", "biggest",
                    "lowest", "least", "worst", "fewest", "smallest", "bottom"
                ]) and not any(pattern in question_lower for pattern in [
                    "breakdown", "distribution", "all", "list", "show all"
                ])

                if wants_top_only and len(groups) > 0:
                    # Return only the top result
                    top_group = groups[0]
                    group_id = top_group.get("_id")
                    count = top_group.get("count", 0)

                    # Determine if user asked for lowest/highest
                    is_lowest_query = any(kw in question_lower for kw in [
                        "lowest", "least", "minimum", "fewest", "smallest", "worst", "bottom"
                    ])
                    superlative = "lowest" if is_lowest_query else "highest"

                    # Format based on group type
                    if isinstance(group_id, dict):
                        # Time-based grouping (month/day)
                        if "month" in group_id and "year" in group_id:
                            month_names = ["", "January", "February", "March", "April", "May", "June",
                                         "July", "August", "September", "October", "November", "December"]
                            month_name = month_names[group_id["month"]]
                            year = group_id["year"]
                            return f"{month_name} {year} has the {superlative} orders with {count:,} orders."
                        elif "day" in group_id:
                            return f"{group_id['year']}-{group_id['month']:02d}-{group_id['day']:02d} has the {superlative} orders with {count:,}."
                    else:
                        # Simple field grouping
                        return f"{group_id} has the {superlative} with {count:,} orders."
                else:
                    # Show full breakdown
                    result_list = []
                    for i, g in enumerate(groups[:10], 1):  # Limit to top 10
                        group_id = g.get("_id")
                        count = g.get("count", 0)

                        if isinstance(group_id, dict):
                            # Time-based
                            if "month" in group_id and "year" in group_id:
                                month_names = ["", "Jan", "Feb", "Mar", "Apr", "May", "Jun",
                                             "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
                                month_name = month_names[group_id["month"]]
                                result_list.append(f"{i}. {month_name} {group_id['year']}: {count:,} orders")
                            elif "day" in group_id:
                                result_list.append(f"{i}. {group_id['year']}-{group_id['month']:02d}-{group_id['day']:02d}: {count:,} orders")
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

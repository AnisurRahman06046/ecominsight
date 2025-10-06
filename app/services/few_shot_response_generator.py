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
        Clear instruction format to prevent echoing.
        """
        prompt = f"""Answer the e-commerce question using only the provided data.

Data: Count 156
Answer: You have 156 products in your store.

Data: Total $12,345.67 from 42 orders
Answer: Your total revenue is $12,345.67 from 42 orders.

Data: Top customer John Smith spent $5,420.00
Answer: Your top customer is John Smith, who has spent $5,420.00.

Data: {data_summary}
Answer:"""
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
            # Extract data context
            data_summary = self._extract_data_context(data, tool_name)

            # Build instruction prompt (improved to prevent echoing)
            prompt = self._build_few_shot_prompt(question, data_summary)

            # Tokenize with Flan-T5
            inputs = self.tokenizer(
                prompt,
                return_tensors="pt",
                max_length=512,
                truncation=True
            )

            # Generate with Flan-T5 (seq2seq)
            outputs = self.model.generate(
                inputs.input_ids,
                max_new_tokens=60,
                do_sample=True,
                temperature=0.7,
                top_p=0.9,
                repetition_penalty=1.2,
                no_repeat_ngram_size=2
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

    def _extract_data_context(self, data: Dict[str, Any], tool_name: str) -> str:
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
                return f"Total: ${total:,.2f}, Item count: {count}"
            return "Total: $0.00, Item count: 0"

        # Average queries
        elif tool_name == "calculate_average":
            results = data.get("result", [])
            if results and len(results) > 0:
                avg = results[0].get("average", 0)
                count = results[0].get("count", 0)
                return f"Average: ${avg:,.2f}, Item count: {count}"
            return "Average: $0.00, Item count: 0"

        # Top customers
        elif tool_name == "get_top_customers_by_spending":
            customers = data.get("customers", [])
            if customers:
                top = customers[0]
                name = top.get("name", "Unknown")
                spent = top.get("total_spent", 0)
                return f"Top customer: {name}, Total spent: ${spent:,.2f}"
            return "No customers found"

        # Best selling products
        elif tool_name == "get_best_selling_products":
            products = data.get("products", [])
            if products:
                top = products[0]
                name = top.get("name", "Unknown")
                quantity = top.get("total_quantity", 0)
                return f"Top product: {name}, Quantity sold: {quantity}"
            return "No products found"

        # Generic
        else:
            count = data.get("count", 0)
            return f"Count: {count}"


# Global instance
few_shot_response_generator = FewShotResponseGenerator()

"""ML-based intent classification using small language model."""

import logging
from typing import Dict, Any, Tuple, Optional
from enum import Enum
import json
import httpx

from app.services.intent_router import Intent
from app.core.config import settings

logger = logging.getLogger(__name__)


class MLIntentClassifier:
    """ML-based intent classifier using local LLM."""

    def __init__(self):
        self.ollama_host = settings.ollama_host
        self.model = settings.ollama_model
        self.client = httpx.AsyncClient(timeout=30)

        # Define intents and their descriptions for the model
        self.intent_descriptions = {
            Intent.PRODUCT_COUNT: "Counting total number of products",
            Intent.ORDER_COUNT: "Counting total number of orders",
            Intent.CUSTOMER_COUNT: "Counting total number of customers",
            Intent.CATEGORY_COUNT: "Counting total number of categories",
            Intent.TOTAL_REVENUE: "Calculating total sales revenue or money earned",
            Intent.AVERAGE_ORDER_VALUE: "Calculating average order value or AOV",
            Intent.TOP_PRODUCTS: "Finding best selling or most popular products",
            Intent.TOP_CUSTOMERS: "Finding top customers by spending",
            Intent.RECENT_ORDERS: "Showing recent or latest orders",
            Intent.SALES_BY_STATUS: "Breaking down orders by status",
            Intent.GREETING: "Greeting or saying hello",
            Intent.UNKNOWN: "Unknown or unclear question"
        }

    async def classify(self, question: str) -> Tuple[Intent, Dict[str, Any]]:
        """
        Classify intent using ML model.

        Returns:
            Tuple of (Intent, params_dict)
        """
        try:
            # Build prompt for intent classification
            intents_list = "\n".join([
                f"- {intent.value}: {desc}"
                for intent, desc in self.intent_descriptions.items()
            ])

            prompt = f"""Classify this e-commerce question into ONE intent category.

Question: {question}

Available intents:
{intents_list}

Return ONLY valid JSON with this exact format:
{{
  "intent": "intent_name",
  "confidence": 0.95,
  "time_period": null,
  "limit": null,
  "status": null
}}

Rules:
- intent must be one of the values above (e.g., "product_count", "order_count")
- confidence is 0.0 to 1.0
- Extract time_period if mentioned (e.g., "today", "last week", "this month")
- Extract limit for top N queries (e.g., "top 5" → limit: 5)
- Extract status if mentioned (e.g., "pending", "completed")

JSON response:"""

            response = await self.client.post(
                f"{self.ollama_host}/api/generate",
                json={
                    "model": self.model,
                    "prompt": prompt,
                    "stream": False,
                    "format": "json",
                    "temperature": 0.1,
                },
            )

            response.raise_for_status()
            result = response.json()

            # Parse the response
            generated_text = result.get("response", "{}").strip()

            # Clean up JSON if needed
            if "```json" in generated_text:
                start = generated_text.find("```json") + 7
                end = generated_text.find("```", start)
                generated_text = generated_text[start:end].strip()
            elif "```" in generated_text:
                start = generated_text.find("```") + 3
                end = generated_text.find("```", start)
                generated_text = generated_text[start:end].strip()

            # Find JSON bounds
            if not generated_text.startswith("{"):
                start = generated_text.find("{")
                end = generated_text.rfind("}") + 1
                if start >= 0 and end > start:
                    generated_text = generated_text[start:end]

            logger.info(f"ML classifier raw output: {generated_text[:200]}")

            parsed = json.loads(generated_text)

            # Extract intent
            intent_str = parsed.get("intent", "unknown")
            confidence = parsed.get("confidence", 0.0)

            # Convert string to Intent enum
            try:
                intent = Intent[intent_str.upper()]
            except (KeyError, AttributeError):
                try:
                    intent = Intent(intent_str)
                except ValueError:
                    logger.warning(f"Unknown intent '{intent_str}', using UNKNOWN")
                    intent = Intent.UNKNOWN

            # Extract parameters
            params = {}
            if parsed.get("time_period"):
                params["time_period"] = parsed["time_period"]
            if parsed.get("limit"):
                params["limit"] = int(parsed["limit"])
            if parsed.get("status"):
                params["status"] = parsed["status"]

            logger.info(f"ML classified as {intent.value} (confidence: {confidence:.2f}), params: {params}")

            return intent, params

        except Exception as e:
            logger.error(f"ML intent classification failed: {e}")
            # Fallback to unknown
            return Intent.UNKNOWN, {}

    async def close(self):
        """Close HTTP client."""
        await self.client.aclose()


# Global instance
ml_intent_classifier = MLIntentClassifier()
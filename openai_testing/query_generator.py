"""
MongoDB Query Generator using OpenRouter API
Generates MongoDB aggregation pipelines from natural language questions
"""
import json
import logging
import requests
from typing import Dict, Any, Optional, List
from .config import openrouter_config

logger = logging.getLogger(__name__)


class QueryGenerator:
    """Generate MongoDB queries using OpenRouter LLM"""

    def __init__(self):
        self.config = openrouter_config
        self.api_url = self.config.api_base_url

    def _call_openrouter(self, messages: List[Dict[str, str]], temperature: Optional[float] = None) -> Optional[str]:
        """
        Call OpenRouter API with messages and retry logic for rate limits.

        Args:
            messages: List of chat messages
            temperature: Temperature for generation (uses config default if not provided)

        Returns:
            Generated text or None if failed
        """
        if not self.config.api_key:
            logger.error("OPENROUTER_API_KEY not set in environment")
            return None

        import time

        headers = {
            "Authorization": f"Bearer {self.config.api_key}",
            "Content-Type": "application/json"
        }

        payload = {
            "model": self.config.query_generation_model,
            "messages": messages,
            "temperature": temperature if temperature is not None else self.config.temperature,
            "max_tokens": self.config.max_tokens
        }

        # Retry with exponential backoff for rate limits
        max_retries = 3
        retry_delay = 10  # Start with 10 seconds (free tier has strict limits)

        for attempt in range(max_retries):
            try:
                logger.info(f"Calling OpenRouter API (attempt {attempt + 1}/{max_retries}) with model: {self.config.query_generation_model}")

                response = requests.post(
                    self.api_url,
                    headers=headers,
                    json=payload,
                    timeout=self.config.timeout
                )

                # Handle rate limiting (429)
                if response.status_code == 429:
                    retry_after = int(response.headers.get('Retry-After', retry_delay))
                    logger.warning(f"Rate limited (429). Retrying after {retry_after} seconds...")

                    if attempt < max_retries - 1:
                        time.sleep(retry_after)
                        retry_delay *= 2  # Exponential backoff
                        continue
                    else:
                        logger.error("Max retries reached for rate limit")
                        return None

                response.raise_for_status()
                result = response.json()

                if "choices" in result and len(result["choices"]) > 0:
                    content = result["choices"][0]["message"]["content"]
                    logger.info("Successfully received response from OpenRouter")
                    return content
                else:
                    logger.error(f"Unexpected response format: {result}")
                    return None

            except requests.exceptions.Timeout:
                logger.error("OpenRouter API request timed out")
                return None
            except requests.exceptions.RequestException as e:
                logger.error(f"OpenRouter API request failed: {e}")
                if attempt < max_retries - 1:
                    logger.info(f"Retrying in {retry_delay} seconds...")
                    time.sleep(retry_delay)
                    retry_delay *= 2
                    continue
                return None
            except Exception as e:
                logger.error(f"Unexpected error calling OpenRouter: {e}")
                return None

        return None

    def generate_query(self, user_question: str, schema: str, shop_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """
        Generate MongoDB aggregation pipeline from user question and schema.

        Args:
            user_question: Natural language question from user
            schema: Database schema as formatted string
            shop_id: Shop ID for filtering (if applicable)

        Returns:
            Dictionary containing:
                - collection: Collection name to query
                - pipeline: MongoDB aggregation pipeline
                - tool_name: Suggested tool/operation name
        """
        system_prompt = """You are a MongoDB query expert. Convert natural language questions into MongoDB aggregation pipelines.

CRITICAL RULES:
1. Return ONLY valid JSON (no markdown, no explanations):
{
  "collection": "collection_name",
  "pipeline": [...],
  "tool_name": "operation_name"
}

2. ALWAYS filter by shop_id first in $match
3. For ORDER collection: use "grand_total" field for sales (NOT subtotal)
4. For date fields: created_at is stored as STRING in format "YYYY-MM-DDTHH:MM:SS"
   - Use $gte and $lt for date ranges
   - Format: "2025-10-07T00:00:00" (no Z suffix)
5. For sales totals: use {"$sum": {"$toDouble": "$grand_total"}}

TOOL NAMES:
- calculate_sum: total/sum/revenue queries
- calculate_average: average queries
- count_documents: counting queries
- get_best_selling_products: top products
- get_top_customers_by_spending: top customers
- group_and_count: grouping queries

Example 1 - Today's sales:
Question: "What is my total sales today?" (Current date: 2025-10-08)
Response:
{
  "collection": "order",
  "pipeline": [
    {"$match": {"shop_id": "1", "created_at": {"$gte": "2025-10-08T00:00:00", "$lt": "2025-10-09T00:00:00"}}},
    {"$group": {"_id": null, "total": {"$sum": {"$toDouble": "$grand_total"}}, "count": {"$sum": 1}}}
  ],
  "tool_name": "calculate_sum"
}

Example 1b - Yesterday's sales (IMPORTANT: Use grand_total field and proper date range):
Question: "What is my total sales yesterday?" (Current date: 2025-10-08)
Response:
{
  "collection": "order",
  "pipeline": [
    {"$match": {"shop_id": "1", "created_at": {"$gte": "2025-10-07T00:00:00", "$lt": "2025-10-08T00:00:00"}}},
    {"$group": {"_id": null, "total": {"$sum": {"$toDouble": "$grand_total"}}, "count": {"$sum": 1}}}
  ],
  "tool_name": "calculate_sum"
}

Example 2:
Question: "Show me top 5 selling products"
Response:
{
  "collection": "order_item",
  "pipeline": [
    {"$match": {"shop_id": "1"}},
    {"$group": {"_id": "$product_id", "total_quantity": {"$sum": "$quantity"}, "total_revenue": {"$sum": "$subtotal"}}},
    {"$sort": {"total_quantity": -1}},
    {"$limit": 5}
  ],
  "tool_name": "get_best_selling_products"
}"""

        # Get current date for context (use UTC to match database timezone)
        from datetime import datetime, timezone
        current_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        current_datetime = datetime.now(timezone.utc).isoformat()

        user_prompt = f"""Database Schema:
{schema}

Current Date: {current_date}
User Question: {user_question}

Important: When calculating dates like "today", "yesterday", "this week", use the Current Date above as reference.
"""

        if shop_id:
            user_prompt += f"\nShop ID: {shop_id} (use this to filter if collection has shop_id field)"

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]

        response_text = self._call_openrouter(messages)

        if not response_text:
            logger.error("Failed to get response from OpenRouter")
            return None

        # Try to extract JSON from response
        try:
            # Remove markdown code blocks if present
            response_text = response_text.strip()
            if response_text.startswith("```json"):
                response_text = response_text[7:]
            if response_text.startswith("```"):
                response_text = response_text[3:]
            if response_text.endswith("```"):
                response_text = response_text[:-3]
            response_text = response_text.strip()

            query_data = json.loads(response_text)

            # Validate structure
            if not all(key in query_data for key in ["collection", "pipeline", "tool_name"]):
                logger.error(f"Invalid query structure: {query_data}")
                return None

            logger.info(f"Generated query for collection: {query_data['collection']}")
            logger.info(f"Tool name: {query_data['tool_name']}")
            logger.debug(f"Pipeline: {json.dumps(query_data['pipeline'], indent=2)}")

            return query_data

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON from response: {e}")
            logger.error(f"Response text: {response_text}")
            return None
        except Exception as e:
            logger.error(f"Error processing query generation: {e}")
            return None


# Global instance
query_generator = QueryGenerator()

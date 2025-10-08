"""
Natural Language Response Generator using OpenRouter API
Converts query results into natural language responses
"""
import json
import logging
import requests
from typing import Dict, Any, Optional, List
from .config import openrouter_config

logger = logging.getLogger(__name__)


class ResponseGenerator:
    """Generate natural language responses from query results using OpenRouter LLM"""

    def __init__(self):
        self.config = openrouter_config
        self.api_url = self.config.api_base_url

    def _call_openrouter(self, messages: List[Dict[str, str]], temperature: Optional[float] = None) -> Optional[str]:
        """
        Call OpenRouter API with messages.

        Args:
            messages: List of chat messages
            temperature: Temperature for generation (uses config default if not provided)

        Returns:
            Generated text or None if failed
        """
        if not self.config.api_key:
            logger.error("OPENROUTER_API_KEY not set in environment")
            return None

        try:
            headers = {
                "Authorization": f"Bearer {self.config.api_key}",
                "Content-Type": "application/json"
            }

            payload = {
                "model": self.config.response_generation_model,
                "messages": messages,
                "temperature": temperature if temperature is not None else 0.7,  # Higher temp for varied responses
                "max_tokens": self.config.max_tokens
            }

            logger.info(f"Calling OpenRouter API with model: {self.config.response_generation_model}")

            response = requests.post(
                self.api_url,
                headers=headers,
                json=payload,
                timeout=self.config.timeout
            )

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
            return None
        except Exception as e:
            logger.error(f"Unexpected error calling OpenRouter: {e}")
            return None

    def generate_response(
        self,
        user_question: str,
        query_results: Any,
        tool_name: Optional[str] = None
    ) -> Optional[str]:
        """
        Generate natural language response from query results.

        Args:
            user_question: Original question from user
            query_results: Results from MongoDB query execution
            tool_name: Name of the tool/operation used (optional, for context)

        Returns:
            Natural language response string or None if failed
        """
        system_prompt = """You are a helpful e-commerce analytics assistant.
Your task is to convert data results into clear, natural language responses.

IMPORTANT RULES:
1. Be conversational and natural
2. Include specific numbers from the data
3. Keep responses concise (2-3 sentences max)
4. If no data, say so politely
5. Format numbers nicely (use commas for thousands, 2 decimals for currency)
6. Return ONLY the natural language response, no JSON or extra formatting

Examples:

Question: "What is my total sales today?"
Data: [{"_id": null, "total": 1850.50, "count": 2}]
Response: "Today you received 2 orders totaling $1,850.50."

Question: "Show me top 3 products"
Data: [
  {"_id": 1, "name": "Product A", "total_quantity": 150, "total_revenue": 4500},
  {"_id": 2, "name": "Product B", "total_quantity": 120, "total_revenue": 3600}
]
Response: "Your top selling products are Product A with 150 units sold ($4,500 revenue) and Product B with 120 units sold ($3,600 revenue)."

Question: "How many orders today?"
Data: {"count": 15}
Response: "You have 15 orders today."
"""

        # Format query results for the prompt
        results_str = json.dumps(query_results, indent=2, default=str)

        user_prompt = f"""Question: {user_question}

Query Results:
{results_str}

Please convert these results into a natural, conversational response to the user's question."""

        if tool_name:
            user_prompt += f"\n\nOperation type: {tool_name}"

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]

        response_text = self._call_openrouter(messages, temperature=0.7)

        if not response_text:
            logger.error("Failed to get response from OpenRouter")
            return None

        # Clean up response (remove any markdown or extra formatting)
        response_text = response_text.strip()
        if response_text.startswith('"') and response_text.endswith('"'):
            response_text = response_text[1:-1]

        logger.info(f"Generated natural language response: {response_text[:100]}...")

        return response_text


# Global instance
response_generator = ResponseGenerator()

"""Ollama service for LLM interactions."""

import json
import httpx
from typing import Dict, Any, List, Optional
import logging
from tenacity import retry, stop_after_attempt, wait_exponential

from app.core.config import settings

logger = logging.getLogger(__name__)


class OllamaService:
    """Service for interacting with Ollama API."""

    def __init__(self):
        self.base_url = settings.ollama_host
        self.model = settings.ollama_model
        self.client = httpx.AsyncClient(timeout=settings.ollama_timeout)
        self.system_prompt = self._build_system_prompt()

    def _build_system_prompt(self) -> str:
        """Build the system prompt for MongoDB query generation."""
        return """You are a MongoDB aggregation expert. You MUST return ONLY valid JSON with exactly these fields:
- "pipeline": array of MongoDB aggregation stages
- "collection": string (order, product, customer, or order_product)
- "answer_template": string template for formatting results

Collections:
- order: {id, shop_id, user_id, subtotal, grand_total, status, created_at}
- order_product: {id, order_id, product_id, name, quantity, price, total_price}
- product: {id, shop_id, name, status, created_at}
- customer: {id, shop_id, first_name, last_name, email, created_at}

CRITICAL RULES:
1. shop_id is INTEGER: {"shop_id": 10}
2. ONLY return JSON - no text before or after
3. Use simple pipelines - avoid complex operations
4. For "recent" queries, use limit and sort by created_at descending

REQUIRED JSON FORMAT:
{
  "pipeline": [...],
  "collection": "order",
  "answer_template": "Found {count} results"
}

EXAMPLES:

Recent orders:
{
  "pipeline": [{"$match": {"shop_id": 10}}, {"$sort": {"created_at": -1}}, {"$limit": 10}],
  "collection": "order",
  "answer_template": "Found {count} recent orders"
}

Count orders:
{
  "pipeline": [{"$match": {"shop_id": 10}}, {"$count": "total"}],
  "collection": "order",
  "answer_template": "Found {total} orders"
}

Orders with multiple items:
{
  "pipeline": [
    {"$match": {"shop_id": 10}},
    {"$lookup": {"from": "order_product", "localField": "id", "foreignField": "order_id", "as": "items"}},
    {"$addFields": {"item_count": {"$size": "$items"}}},
    {"$match": {"item_count": {"$gt": 3}}},
    {"$limit": 10}
  ],
  "collection": "order",
  "answer_template": "Found orders with more than 3 items"
}"""

    async def initialize(self):
        """Initialize the Ollama service."""
        try:
            # Test connection
            models = await self.list_models()
            logger.info(f"Ollama connected. Available models: {len(models)}")

            # Check if required model is available
            if not any(self.model in m.get("name", "") for m in models):
                logger.warning(f"Model {self.model} not found. Pulling...")
                await self.pull_model(self.model)

        except Exception as e:
            logger.error(f"Failed to initialize Ollama: {e}")

    async def close(self):
        """Close the HTTP client."""
        await self.client.aclose()

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
    async def generate_query(
        self, question: str, shop_id: str, context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Generate MongoDB query from natural language question.

        Returns:
            Dict with pipeline, collection, and answer_template
        """
        try:
            user_prompt = f"""Shop ID: {shop_id}
Question: {question}
{f"Context: {json.dumps(context)}" if context else ""}

Generate a MongoDB aggregation pipeline to answer this question."""

            response = await self.client.post(
                f"{self.base_url}/api/generate",
                json={
                    "model": self.model,
                    "system": self.system_prompt,
                    "prompt": user_prompt,
                    "stream": False,
                    "format": "json",
                    "temperature": 0.1,  # Low temperature for consistency
                },
            )

            response.raise_for_status()
            result = response.json()

            # Parse the response
            generated_text = result.get("response", "{}").strip()

            # Clean up the response - remove any markdown formatting or extra text
            if "```json" in generated_text:
                # Extract JSON from markdown code block
                start = generated_text.find("```json") + 7
                end = generated_text.find("```", start)
                generated_text = generated_text[start:end].strip()
            elif "```" in generated_text:
                # Extract JSON from code block
                start = generated_text.find("```") + 3
                end = generated_text.find("```", start)
                generated_text = generated_text[start:end].strip()

            # Find JSON object bounds
            if generated_text.startswith("{") and generated_text.endswith("}"):
                json_text = generated_text
            else:
                # Try to extract JSON from the text
                start = generated_text.find("{")
                end = generated_text.rfind("}") + 1
                if start >= 0 and end > start:
                    json_text = generated_text[start:end]
                else:
                    json_text = generated_text

            parsed = json.loads(json_text)

            # Validate required fields
            if not all(k in parsed for k in ["pipeline", "collection", "answer_template"]):
                missing = [k for k in ["pipeline", "collection", "answer_template"] if k not in parsed]
                raise ValueError(f"Missing required fields in LLM response: {missing}")

            return parsed

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse LLM response: {e}")
            logger.error(f"Raw LLM response: {generated_text}")
            # Return a fallback simple query
            return {
                "pipeline": [{"$match": {"shop_id": int(shop_id)}}, {"$limit": 10}],
                "collection": "order",
                "answer_template": "Found recent data"
            }
        except Exception as e:
            logger.error(f"Query generation failed: {e}")
            logger.error(f"Full error details: {type(e).__name__}: {str(e)}")
            # Return a fallback simple query
            return {
                "pipeline": [{"$match": {"shop_id": int(shop_id)}}, {"$limit": 10}],
                "collection": "order",
                "answer_template": "Found recent data"
            }

    async def generate_answer(
        self, question: str, data: Any, query_type: str = "general"
    ) -> str:
        """
        Generate natural language answer from query results.

        Args:
            question: Original user question
            data: Query results
            query_type: Type of query for context

        Returns:
            Natural language answer
        """
        try:
            prompt = f"""Question: {question}
Query Type: {query_type}
Data: {json.dumps(data, default=str)}

Generate a natural, conversational answer to the question based on the data.
Be concise but informative. If the data is empty, provide a helpful message."""

            response = await self.client.post(
                f"{self.base_url}/api/generate",
                json={
                    "model": self.model,
                    "prompt": prompt,
                    "stream": False,
                    "temperature": 0.3,
                },
            )

            response.raise_for_status()
            result = response.json()
            return result.get("response", "I couldn't generate an answer.")

        except Exception as e:
            logger.error(f"Answer generation failed: {e}")
            return f"I found the data but couldn't format the answer: {str(data)[:200]}"

    async def analyze_with_rag(
        self, question: str, context_documents: List[str], shop_id: str
    ) -> str:
        """
        Generate analytical insights using RAG context.

        Args:
            question: User's analytical question
            context_documents: Relevant documents from vector search
            shop_id: Shop identifier

        Returns:
            Analytical answer
        """
        try:
            context = "\n\n".join(context_documents)

            prompt = f"""You are analyzing e-commerce data for shop {shop_id}.

Question: {question}

Relevant Context:
{context}

Based on the context above, provide an analytical answer to the question.
Focus on insights, patterns, and actionable recommendations.
If the context doesn't contain enough information, acknowledge this."""

            response = await self.client.post(
                f"{self.base_url}/api/generate",
                json={
                    "model": self.model,
                    "prompt": prompt,
                    "stream": False,
                    "temperature": 0.5,
                },
            )

            response.raise_for_status()
            result = response.json()
            return result.get("response", "Unable to generate analysis.")

        except Exception as e:
            logger.error(f"RAG analysis failed: {e}")
            return "I encountered an error while analyzing the data."

    async def list_models(self) -> List[Dict[str, Any]]:
        """List available Ollama models."""
        try:
            response = await self.client.get(f"{self.base_url}/api/tags")
            response.raise_for_status()
            data = response.json()
            return data.get("models", [])
        except Exception as e:
            logger.error(f"Failed to list models: {e}")
            return []

    async def pull_model(self, model_name: str):
        """Pull a new model from Ollama."""
        try:
            response = await self.client.post(
                f"{self.base_url}/api/pull",
                json={"name": model_name},
                timeout=600,  # 10 minutes for large models
            )
            response.raise_for_status()
            logger.info(f"Successfully pulled model: {model_name}")
        except Exception as e:
            logger.error(f"Failed to pull model {model_name}: {e}")
            raise


# Global instance (will be initialized in main.py)
ollama_service = OllamaService()
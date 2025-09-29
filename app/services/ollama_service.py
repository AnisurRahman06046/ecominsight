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
        self.schema_manager = None
        self.system_prompt = None

    def _build_system_prompt(self) -> str:
        """Build the system prompt for MongoDB query generation using dynamic schema."""
        if not self.schema_manager or not self.schema_manager.get_formatted_schema():
            return """You MUST return ONLY a JSON object with these EXACT three fields:
1. "collection" - string with collection name (use "order" as default)
2. "pipeline" - array of MongoDB aggregation stages
3. "answer_template" - string template for the answer

Your response MUST be ONLY this JSON - nothing else:
{
  "collection": "order",
  "pipeline": [{"$match": {"shop_id": 1}}, {"$limit": 10}],
  "answer_template": "Found {count} results"
}

CRITICAL: Use "pipeline" NOT "pipe", include ALL three fields"""

        schema_context = self.schema_manager.get_formatted_schema()

        return f"""You MUST return ONLY a JSON object with these EXACT three fields:
1. "collection" - string with collection name from schema
2. "pipeline" - array of MongoDB aggregation stages
3. "answer_template" - string template for the answer

{schema_context}

EXAMPLE PATTERNS TO FOLLOW:

For counting:
{{
  "collection": "order",
  "pipeline": [
    {{"$match": {{"shop_id": 1}}}},
    {{"$count": "total"}}
  ],
  "answer_template": "Found {{total}} orders"
}}

For filtering with conditions (greater than):
{{
  "collection": "order",
  "pipeline": [
    {{"$match": {{"shop_id": 1, "grand_total": {{"$gt": 1000}}}}}}
  ],
  "answer_template": "Found {{count}} orders over $1000"
}}

For grouping and counting:
{{
  "collection": "order",
  "pipeline": [
    {{"$match": {{"shop_id": 1}}}},
    {{"$group": {{
      "_id": "$status",
      "count": {{"$sum": 1}}
    }}}}
  ],
  "answer_template": "Orders grouped by status"
}}

For top N with sorting:
{{
  "collection": "order",
  "pipeline": [
    {{"$match": {{"shop_id": 1}}}},
    {{"$sort": {{"grand_total": -1}}}},
    {{"$limit": 5}}
  ],
  "answer_template": "Top 5 orders by value"
}}

For calculating totals:
{{
  "collection": "order",
  "pipeline": [
    {{"$match": {{"shop_id": 1}}}},
    {{"$group": {{
      "_id": null,
      "total_revenue": {{"$sum": "$grand_total"}},
      "count": {{"$sum": 1}}
    }}}}
  ],
  "answer_template": "Total revenue: {{total_revenue}}"
}}

CRITICAL RULES:
- ALWAYS start with {{"$match": {{"shop_id": <number>}}}}
- Use MongoDB operators: $gt, $lt, $gte, $lte, $eq, $ne for comparisons
- Use $group for aggregations with $sum, $avg, $max, $min
- Use $sort before $limit for "top N" queries
- Return ONLY JSON, no explanations"""

    async def initialize(self, schema_manager=None):
        """Initialize the Ollama service."""
        try:
            if schema_manager:
                self.schema_manager = schema_manager
                logger.info("Schema manager attached to Ollama service")

            self.system_prompt = self._build_system_prompt()

            models = await self.list_models()
            logger.info(f"Ollama connected. Available models: {len(models)}")

            if not any(self.model in m.get("name", "") for m in models):
                logger.warning(f"Model {self.model} not found. Pulling...")
                await self.pull_model(self.model)

        except Exception as e:
            logger.error(f"Failed to initialize Ollama: {e}")

    async def close(self):
        """Close the HTTP client."""
        await self.client.aclose()

    def _get_relevant_collections(self, question: str) -> List[str]:
        """Identify relevant collections based on question keywords and relationships."""
        question_lower = question.lower()

        collection_keywords = {
            "order": ["order", "purchase", "transaction", "sale", "sold", "revenue", "payment"],
            "product": ["product", "item", "inventory", "stock", "sku"],
            "customer": ["customer", "user", "client", "buyer"],
            "category": ["category", "categories", "type", "classification"],
            "order_product": ["order item", "order detail", "line item"],
        }

        primary_collections = []
        for collection, keywords in collection_keywords.items():
            if any(keyword in question_lower for keyword in keywords):
                primary_collections.append(collection)

        if not primary_collections:
            primary_collections = ["order", "product", "customer"]

        all_relevant = set(primary_collections)

        if self.schema_manager:
            for collection in primary_collections:
                related = self.schema_manager.get_related_collections(collection)
                all_relevant.update(related)

        logger.info(f"Primary collections: {primary_collections}, Related: {list(all_relevant - set(primary_collections))}")

        return list(all_relevant)

    def _build_dynamic_system_prompt(self, relevant_collections: List[str]) -> str:
        """Build system prompt with only relevant collections."""
        if not self.schema_manager or not self.schema_manager.get_schema():
            return self._build_system_prompt()

        schema = self.schema_manager.get_schema()

        filtered_schema = {
            "database_name": schema.get("database_name"),
            "collections": {k: v for k, v in schema["collections"].items() if k in relevant_collections}
        }

        from app.services.schema_extractor import schema_extractor
        schema_text = schema_extractor.format_schema_for_llm(filtered_schema)

        return f"""You are a MongoDB query generator. Analyze the question and generate appropriate MongoDB pipeline.

SCHEMA:
{schema_text}

REQUIRED OUTPUT FORMAT - Return ONLY this JSON structure:
{{
  "collection": "<collection_name>",
  "pipeline": [<array of stages>],
  "answer_template": "<template string>"
}}

QUERY PATTERNS:

1. For "count" questions use $count:
   {{"$match": {{"shop_id": 1}}}}, {{"$count": "total"}}

2. For "greater than/less than" use comparison operators:
   {{"$match": {{"shop_id": 1, "field": {{"$gt": value}}}}}}

3. For "group by" use $group:
   {{"$group": {{"_id": "$field", "count": {{"$sum": 1}}}}}}

4. For "top N" use $sort + $limit:
   {{"$sort": {{"field": -1}}}}, {{"$limit": 5}}

5. For "sum/average" use $group with operators:
   {{"$group": {{"_id": null, "total": {{"$sum": "$field"}}}}}}

CRITICAL:
- ALWAYS use "pipeline" (not "pipe")
- ALWAYS include all 3 fields
- ALWAYS start with $match for shop_id
- Return ONLY JSON, no text"""

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
    async def generate_query(
        self, question: str, shop_id: str, context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Generate MongoDB query from natural language question.

        Returns:
            Dict with pipeline, collection, and answer_template
        """
        shop_id_int = int(shop_id) if shop_id.isdigit() else 10

        # First, use LLM for intent classification
        try:
            from app.services.llm_intent_classifier import llm_intent_classifier

            # Get intent classification from LLM
            intent_data = await llm_intent_classifier.classify_intent(question, shop_id)

            # Generate pipeline based on intent
            if intent_data and intent_data.get("primary_collection"):
                result = await llm_intent_classifier.generate_pipeline_from_intent(intent_data, shop_id_int)
                logger.info(f"Using LLM intent-based query for: {question}")
                logger.info(f"Intent: {intent_data}")
                return result
        except Exception as e:
            logger.debug(f"LLM intent classification failed: {e}")

        # Second, try using the template-based approach as fallback
        try:
            from app.services.query_templates import smart_query_builder

            template_result = smart_query_builder.build_query(question, shop_id_int)

            # Check if template gave a meaningful result (not default)
            if len(template_result.get("pipeline", [])) > 2 or \
               any(stage for stage in template_result.get("pipeline", [])
                   if "$group" in stage or "$count" in stage or "$sort" in stage):
                logger.info(f"Using template-based query for: {question}")
                return template_result
        except Exception as e:
            logger.debug(f"Template approach failed, falling back to raw LLM: {e}")

        # Final fallback to raw LLM generation
        try:
            relevant_collections = self._get_relevant_collections(question)
            logger.info(f"Relevant collections for query: {relevant_collections}")

            dynamic_prompt = self._build_dynamic_system_prompt(relevant_collections)

            # Convert shop_id to integer for the prompt
            shop_id_int = int(shop_id) if shop_id.isdigit() else 10

            user_prompt = f"""Question: {question}
Shop ID: {shop_id_int} (use this exact integer value in $match)

Return ONLY the JSON object with collection, pipeline, and answer_template fields."""

            # Try improved prompt first
            try:
                from app.services.improved_llm_prompts import get_mongodb_generation_prompt

                # Get schema context
                schema_text = ""
                if self.schema_manager:
                    schema_text = self.schema_manager.get_formatted_schema()

                improved_prompt = get_mongodb_generation_prompt(
                    schema_context=schema_text,
                    question=question,
                    shop_id=shop_id_int
                )

                response = await self.client.post(
                    f"{self.base_url}/api/generate",
                    json={
                        "model": self.model,
                        "prompt": improved_prompt,
                        "stream": False,
                        "format": "json",
                        "temperature": 0.05,  # Lower temperature for more consistent output
                    },
                )
            except:
                # Fallback to original prompt
                response = await self.client.post(
                    f"{self.base_url}/api/generate",
                    json={
                        "model": self.model,
                        "system": dynamic_prompt,
                        "prompt": user_prompt,
                        "stream": False,
                        "format": "json",
                        "temperature": 0.1,
                    },
                )

            response.raise_for_status()
            result = response.json()

            # Parse the response
            generated_text = result.get("response", "{}").strip()
            logger.info(f"Raw LLM output (first 500 chars): {generated_text[:500]}")

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
            logger.error(f"Raw LLM response: {result.get('response', 'No response')[:500]}")
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
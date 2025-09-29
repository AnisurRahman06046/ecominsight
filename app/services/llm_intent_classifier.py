"""
LLM-based Intent Classification for Better Query Understanding
Uses the LLM to understand user intent and map to correct collections
"""

import json
import logging
from typing import Dict, Any, Optional
import httpx
from app.core.config import settings

logger = logging.getLogger(__name__)

class LLMIntentClassifier:
    """Use LLM to classify intent and determine collection/query structure"""

    def __init__(self):
        self.base_url = settings.ollama_host
        self.model = settings.ollama_model
        self.client = httpx.AsyncClient(timeout=30)
        self.schema = None

    async def _get_schema_context(self) -> str:
        """Get the actual database schema for context"""
        try:
            # Try to get schema from the schema extractor service
            from app.services.schema_extractor import schema_extractor

            if not self.schema:
                # Get schema if not cached
                self.schema = schema_extractor.get_schema()

            if self.schema and self.schema.get("collections"):
                # Format schema for LLM understanding
                schema_text = "ACTUAL DATABASE COLLECTIONS AND FIELDS:\n\n"
                for collection_name, collection_info in self.schema["collections"].items():
                    schema_text += f"Collection: {collection_name}\n"
                    if "fields" in collection_info:
                        fields = collection_info["fields"]
                        # Show first 10 important fields
                        important_fields = []
                        for field_name, field_info in list(fields.items())[:15]:
                            field_type = field_info.get("type", "unknown")
                            important_fields.append(f"{field_name} ({field_type})")
                        schema_text += f"  Fields: {', '.join(important_fields)}\n"

                    if "sample_count" in collection_info:
                        schema_text += f"  Total Records: {collection_info['sample_count']}\n"

                    if "relationships" in collection_info:
                        for rel in collection_info["relationships"]:
                            schema_text += f"  Related to: {rel['target_collection']} via {rel['field']}\n"

                    schema_text += "\n"

                return schema_text
            else:
                # Fallback to hardcoded schema if dynamic schema not available
                return """Available Collections:
- order: Contains customer orders (fields: id, order_number, user_id, grand_total, status, created_at, shop_id, etc.)
- product: Contains products (fields: id, name, price, sku, inventory, category_id, shop_id, etc.)
- category: Contains product categories (fields: id, name, description, parent_id, shop_id, etc.)
- customer: Contains customer information (fields: id, name, email, phone, shop_id, etc.)
- order_product: Links orders to products (fields: order_id, product_id, quantity, price, etc.)"""

        except Exception as e:
            logger.warning(f"Could not get schema context: {e}")
            # Return basic schema as fallback
            return """Available Collections:
- order: Contains customer orders (fields: id, order_number, user_id, grand_total, status, created_at, shop_id, etc.)
- product: Contains products (fields: id, name, price, sku, inventory, category_id, shop_id, etc.)
- category: Contains product categories (fields: id, name, description, parent_id, shop_id, etc.)
- customer: Contains customer information (fields: id, name, email, phone, shop_id, etc.)
- order_product: Links orders to products (fields: order_id, product_id, quantity, price, etc.)"""

    async def classify_intent(self, question: str, shop_id: str) -> Dict[str, Any]:
        """
        Use LLM to understand the user's intent and determine:
        1. Which collection to query
        2. What type of operation (count, filter, aggregate, etc.)
        3. Query parameters
        """

        # Get actual schema from the database
        schema_context = await self._get_schema_context()

        # Try improved intent classification
        try:
            from app.services.improved_llm_prompts import get_intent_classification_prompt
            prompt = get_intent_classification_prompt(
                schema_context=schema_context,
                question=question,
                shop_id=shop_id
            )
        except:
            # Fallback to original prompt
            prompt = f"""Analyze this e-commerce query and determine the MongoDB collection and operation needed.

User Question: "{question}"
Shop ID: {shop_id}

DATABASE SCHEMA:
{schema_context}

Respond with ONLY this JSON structure:
{{
  "primary_collection": "<collection name>",
  "operation_type": "<count|filter|group|aggregate|top_n|list>",
  "intent": "<what user wants>",
  "filters": {{}},
  "sort_field": null,
  "group_by": null,
  "limit": null
}}

Examples:
Q: "how many categories do i have?"
{{
  "primary_collection": "category",
  "operation_type": "count",
  "intent": "count all categories",
  "filters": {{}},
  "sort_field": null,
  "group_by": null,
  "limit": null
}}

Q: "show top 5 customers by spending"
{{
  "primary_collection": "order",
  "operation_type": "top_n",
  "intent": "find top customers by total spending",
  "filters": {{}},
  "sort_field": "grand_total",
  "group_by": "user_id",
  "limit": 5
}}

Q: "list all products in electronics category"
{{
  "primary_collection": "product",
  "operation_type": "filter",
  "intent": "get products in specific category",
  "filters": {{"category": "electronics"}},
  "sort_field": null,
  "group_by": null,
  "limit": null
}}"""

        try:
            response = await self.client.post(
                f"{self.base_url}/api/generate",
                json={
                    "model": self.model,
                    "prompt": prompt,
                    "stream": False,
                    "format": "json",
                    "temperature": 0.1,
                }
            )

            response.raise_for_status()
            result = response.json()

            # Parse LLM response
            generated_text = result.get("response", "{}").strip()

            # Clean up response
            if "```json" in generated_text:
                start = generated_text.find("```json") + 7
                end = generated_text.find("```", start)
                generated_text = generated_text[start:end].strip()
            elif "```" in generated_text:
                start = generated_text.find("```") + 3
                end = generated_text.find("```", start)
                generated_text = generated_text[start:end].strip()

            # Parse JSON
            intent_data = json.loads(generated_text)

            logger.info(f"LLM Intent Classification: {intent_data}")
            return intent_data

        except Exception as e:
            logger.error(f"LLM intent classification failed: {e}")
            # Fallback to basic keyword matching
            return self._fallback_classification(question)

    def _fallback_classification(self, question: str) -> Dict[str, Any]:
        """Fallback classification based on keywords"""
        question_lower = question.lower()

        # Check for category-specific keywords
        if any(word in question_lower for word in ["category", "categories"]):
            if "count" in question_lower or "how many" in question_lower:
                return {
                    "primary_collection": "category",
                    "operation_type": "count",
                    "intent": "count categories",
                    "filters": {},
                    "sort_field": None,
                    "group_by": None,
                    "limit": None
                }
            else:
                return {
                    "primary_collection": "category",
                    "operation_type": "list",
                    "intent": "list categories",
                    "filters": {},
                    "sort_field": None,
                    "group_by": None,
                    "limit": 10
                }

        # Check for product keywords
        elif any(word in question_lower for word in ["product", "item", "sku"]):
            return {
                "primary_collection": "product",
                "operation_type": "list",
                "intent": "query products",
                "filters": {},
                "sort_field": None,
                "group_by": None,
                "limit": 10
            }

        # Check for customer keywords
        elif any(word in question_lower for word in ["customer", "client", "user"]):
            return {
                "primary_collection": "customer",
                "operation_type": "list",
                "intent": "query customers",
                "filters": {},
                "sort_field": None,
                "group_by": None,
                "limit": 10
            }

        # Default to orders
        else:
            return {
                "primary_collection": "order",
                "operation_type": "list",
                "intent": "query orders",
                "filters": {},
                "sort_field": None,
                "group_by": None,
                "limit": 10
            }

    async def generate_pipeline_from_intent(self, intent_data: Dict[str, Any], shop_id: int) -> Dict[str, Any]:
        """Generate MongoDB pipeline based on intent classification"""

        collection = intent_data.get("primary_collection", "order")
        operation = intent_data.get("operation_type", "list")
        filters = intent_data.get("filters", {})
        sort_field = intent_data.get("sort_field")
        group_by = intent_data.get("group_by")
        limit = intent_data.get("limit", 10)

        pipeline = []

        # Start with shop_id filter for multi-tenant collections
        if collection in ["order", "product", "category", "customer"]:
            match_stage = {"shop_id": shop_id}
            if filters:
                match_stage.update(filters)
            pipeline.append({"$match": match_stage})
        elif filters:
            pipeline.append({"$match": filters})

        # Handle different operation types
        if operation == "count":
            pipeline.append({"$count": "total"})
            answer_template = f"You have {{total}} {collection}s"

        elif operation == "group":
            if group_by:
                pipeline.append({
                    "$group": {
                        "_id": f"${group_by}",
                        "count": {"$sum": 1}
                    }
                })
                if sort_field:
                    pipeline.append({"$sort": {sort_field: -1}})
            answer_template = f"Grouped {collection}s by {group_by}"

        elif operation == "top_n" and group_by:
            pipeline.append({
                "$group": {
                    "_id": f"${group_by}",
                    "total": {"$sum": f"${sort_field}" if sort_field else 1},
                    "count": {"$sum": 1}
                }
            })
            pipeline.append({"$sort": {"total": -1}})
            pipeline.append({"$limit": limit})
            answer_template = f"Top {limit} results"

        elif operation == "filter" or operation == "list":
            if sort_field:
                pipeline.append({"$sort": {sort_field: -1}})
            pipeline.append({"$limit": limit})
            answer_template = f"Found {{count}} {collection}s"

        else:
            # Default behavior
            pipeline.append({"$limit": limit})
            answer_template = f"Found {{count}} {collection}s"

        return {
            "collection": collection,
            "pipeline": pipeline,
            "answer_template": answer_template,
            "intent_classification": intent_data
        }

# Global instance
llm_intent_classifier = LLMIntentClassifier()
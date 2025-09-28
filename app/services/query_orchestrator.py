"""Query orchestrator that coordinates all services."""

import time
from typing import Dict, Any, Optional
import logging
import json

from app.services.intent_classifier import intent_classifier, IntentType
from app.services.kpi_templates import kpi_templates
from app.services.ollama_service import ollama_service
from app.services.rag_service import rag_service
from app.services.cache_service import cache_service
from app.services.intelligent_formatter import intelligent_formatter
from app.core.database import mongodb
from app.core.config import settings

logger = logging.getLogger(__name__)


class QueryOrchestrator:
    """Orchestrates query processing across different services."""

    def __init__(self):
        self.intent_classifier = intent_classifier
        self.kpi_templates = kpi_templates
        self.ollama = ollama_service
        self.rag = rag_service
        self.cache = cache_service

    async def initialize(self):
        """Initialize all services."""
        await self.rag.initialize()
        await self.cache.initialize()
        await intelligent_formatter.initialize()
        logger.info("Query orchestrator initialized")

    async def process_query(
        self,
        shop_id: str,
        question: str,
        context: Optional[Dict[str, Any]] = None,
        use_cache: bool = True,
    ) -> Dict[str, Any]:
        """
        Process a natural language query through the appropriate pipeline.

        Flow:
        1. Check cache
        2. Classify intent
        3. Route to appropriate handler (KPI/LLM/RAG)
        4. Format answer
        5. Cache result

        Returns:
            Dict with answer, data, query_type, and metadata
        """
        start_time = time.time()

        # Step 1: Check cache
        if use_cache and settings.enable_cache:
            cached_result = await self.cache.get(f"{shop_id}:{question}")
            if cached_result:
                logger.info(f"Cache hit for query: {question[:50]}...")
                return {
                    **cached_result,
                    "cached": True,
                    "processing_time": time.time() - start_time,
                }

        # Step 2: Classify intent
        intent_type, kpi_name, params = self.intent_classifier.classify(question)
        logger.info(f"Intent classified as {intent_type.value}, KPI: {kpi_name}, params: {params}")

        result = None

        # Step 3: Route based on intent
        if intent_type == IntentType.CONVERSATIONAL:
            # Conversational: Return friendly response
            result = await self._process_conversational_query(question)

        elif intent_type == IntentType.KPI and settings.use_template_first:
            # Fast path: Use predefined KPI template
            result = await self._process_kpi_query(shop_id, kpi_name, params, question)

        elif intent_type == IntentType.ANALYTICAL and settings.use_rag_for_analytics:
            # Analytical path: Use RAG
            result = await self._process_analytical_query(shop_id, question)

        else:
            # Unknown/Complex: Use LLM
            result = await self._process_llm_query(shop_id, question, context)

        # Step 4: Add metadata
        result["query_type"] = intent_type.value
        result["processing_time"] = time.time() - start_time
        result["cached"] = False

        # Step 5: Cache result
        if use_cache and settings.enable_cache and result.get("answer"):
            await self.cache.set(
                f"{shop_id}:{question}",
                {
                    "answer": result["answer"],
                    "data": result.get("data"),
                    "query_type": result["query_type"],
                },
                ttl=settings.cache_ttl,
            )

        return result

    async def _process_conversational_query(self, question: str) -> Dict[str, Any]:
        """Process conversational/greeting queries."""
        question_lower = question.lower()

        responses = {
            "greeting": "Hello! I'm your e-commerce analytics assistant. I can help you analyze your sales data, orders, customers, and products. What would you like to know?",
            "how_are_you": "I'm doing great, thank you! I'm here to help you analyze your e-commerce data. What insights are you looking for today?",
            "thanks": "You're welcome! Let me know if you need anything else.",
            "goodbye": "Goodbye! Feel free to come back if you need any analytics insights."
        }

        if any(word in question_lower for word in ["hi", "hello", "hey", "greetings", "good morning", "good afternoon", "good evening"]):
            answer = responses["greeting"]
        elif "how are you" in question_lower or "how's it going" in question_lower or "what's up" in question_lower:
            answer = responses["how_are_you"]
        elif "thank" in question_lower:
            answer = responses["thanks"]
        elif any(word in question_lower for word in ["bye", "goodbye", "see you"]):
            answer = responses["goodbye"]
        else:
            answer = responses["greeting"]

        return {
            "answer": answer,
            "data": [],
            "metadata": {}
        }

    async def _process_kpi_query(
        self,
        shop_id: str,
        kpi_name: str,
        params: Dict[str, Any],
        question: str,
    ) -> Dict[str, Any]:
        """Process a known KPI query using templates."""
        try:
            # Get KPI template
            template = self.kpi_templates.get_template(kpi_name)
            if not template:
                logger.warning(f"No template found for KPI: {kpi_name}")
                return await self._process_llm_query(shop_id, question, None)

            # Build pipeline
            pipeline = template["pipeline"](shop_id, params)
            collection = template["collection"]

            # Execute query
            logger.info(f"Executing KPI pipeline on {collection}")
            data = await mongodb.execute_aggregation(collection, pipeline, timeout=settings.max_query_timeout)

            # Format answer - try intelligent formatter first for better UX
            if data and intelligent_formatter.initialized:
                # Use intelligent formatter for better user experience
                answer = intelligent_formatter.format_response(data, question, "kpi_query")
            else:
                # Fallback to template formatting
                answer_template = template["answer_template"]

                # Handle callable templates (for complex formatting)
                if callable(answer_template):
                    answer = answer_template(data)
                else:
                    # Simple template formatting
                    if data:
                        # Extract values from result
                        result_dict = data[0] if isinstance(data, list) and data else {}

                        # Add descriptive context
                        time_desc = params.get("time_period", "")
                        filter_desc = params.get("filter", "")

                        # Determine tense
                        is_were = "was" if time_desc in ["yesterday", "last week", "last month"] else "is"

                        format_dict = {
                            **result_dict,
                            "time_desc": time_desc,
                            "filter_desc": filter_desc,
                            "is_were": is_were,
                            "is_was": is_were,
                        }

                        answer = answer_template.format(**format_dict)
                    else:
                        answer = f"No data found for {kpi_name.replace('_', ' ')}"

            return {
                "answer": answer,
                "data": data,
                "metadata": {
                    "kpi": kpi_name,
                    "params": params,
                    "pipeline": pipeline,
                },
            }

        except Exception as e:
            logger.error(f"KPI query failed: {e}")
            # Fallback to LLM
            return await self._process_llm_query(shop_id, question, None)

    async def _process_llm_query(
        self,
        shop_id: str,
        question: str,
        context: Optional[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Process unknown query using LLM."""
        try:
            # Generate MongoDB query using LLM
            llm_result = await self.ollama.generate_query(question, shop_id, context)

            # Execute the generated pipeline
            collection = llm_result["collection"]
            pipeline = llm_result["pipeline"]

            # Validate pipeline (basic security check)
            if not self._validate_pipeline(pipeline):
                raise ValueError("Generated pipeline failed validation")

            logger.info(f"Executing LLM-generated pipeline on {collection}")
            data = await mongodb.execute_aggregation(collection, pipeline, timeout=settings.max_query_timeout)

            # Format answer using intelligent formatter first, template as fallback
            if data:
                # Try intelligent formatter first for better user experience
                if intelligent_formatter.initialized:
                    answer = intelligent_formatter.format_response(data, question, "llm_query")
                else:
                    # Fallback to template formatting
                    try:
                        answer_template = llm_result["answer_template"]
                        # Create format dictionary based on data type
                        if isinstance(data, list):
                            format_dict = {
                                "count": len(data),
                                "total": len(data),
                                "first": data[0] if data else {},
                            }
                            # If it's a simple count result
                            if len(data) == 1 and isinstance(data[0], dict) and len(data[0]) == 1:
                                format_dict.update(data[0])
                        else:
                            format_dict = data if isinstance(data, dict) else {"result": data}

                        answer = answer_template.format(**format_dict)
                    except Exception as e:
                        logger.warning(f"Template formatting failed: {e}")
                        # Basic fallback
                        if isinstance(data, list):
                            answer = f"Found {len(data)} results"
                        else:
                            answer = f"Query completed: {str(data)[:100]}..."
            else:
                answer = "No data found matching your query."

            return {
                "answer": answer,
                "data": data,
                "metadata": {
                    "generated_pipeline": pipeline,
                    "collection": collection,
                },
            }

        except Exception as e:
            logger.error(f"LLM query failed: {e}")
            return {
                "answer": f"I couldn't process your query. Error: {str(e)}",
                "data": None,
                "metadata": {"error": str(e)},
            }

    async def _process_analytical_query(
        self,
        shop_id: str,
        question: str,
    ) -> Dict[str, Any]:
        """Process analytical query using RAG."""
        try:
            # Search for relevant documents
            relevant_docs = self.rag.search(question, shop_id, n_results=settings.rag_top_k)

            if not relevant_docs:
                # No relevant context, try LLM instead
                logger.info("No RAG documents found, falling back to LLM")
                return await self._process_llm_query(shop_id, question, None)

            # Extract content from documents
            context_documents = [doc["content"] for doc in relevant_docs]

            # Generate analytical answer using RAG
            raw_answer = await self.ollama.analyze_with_rag(question, context_documents, shop_id)

            # Enhance with intelligent formatting if available
            if intelligent_formatter.initialized:
                # For RAG, we mainly enhance the raw answer text
                answer = raw_answer  # RAG already produces natural language
            else:
                answer = raw_answer

            return {
                "answer": answer,
                "data": None,
                "metadata": {
                    "rag_documents": len(relevant_docs),
                    "top_match_distance": relevant_docs[0]["distance"] if relevant_docs else None,
                },
            }

        except Exception as e:
            logger.error(f"Analytical query failed: {e}")
            return {
                "answer": f"I couldn't analyze your query. Error: {str(e)}",
                "data": None,
                "metadata": {"error": str(e)},
            }

    def _validate_pipeline(self, pipeline: list) -> bool:
        """Basic validation of generated pipeline for security."""
        if not isinstance(pipeline, list):
            return False

        # Check for dangerous operations
        dangerous_ops = ["$merge", "$out", "$function", "$accumulator"]

        for stage in pipeline:
            if not isinstance(stage, dict):
                return False

            for op in dangerous_ops:
                if op in stage:
                    logger.warning(f"Dangerous operation {op} in pipeline")
                    return False

        return True


# Global instance
query_orchestrator = QueryOrchestrator()
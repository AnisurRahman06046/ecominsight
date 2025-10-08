"""
OpenRouter Orchestrator
Coordinates the flow: Question -> Query Generation -> Execution -> Response Generation
"""
import logging
import sys
import os
from typing import Dict, Any, Optional

# Add parent directory to path to import app modules
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from app.core.database import mongodb
from app.services.schema_manager import schema_manager
from openai_testing.query_generator import query_generator
from openai_testing.response_generator import response_generator

logger = logging.getLogger(__name__)


class OpenRouterOrchestrator:
    """Orchestrate the complete flow using OpenRouter API"""

    def __init__(self):
        self.initialized = False

    async def initialize(self):
        """Initialize database connection and schema"""
        if self.initialized:
            return

        logger.info("Initializing OpenRouter Orchestrator...")

        # Connect to MongoDB
        connected = await mongodb.connect()
        if not connected:
            raise Exception("Failed to connect to MongoDB")

        # Load schema
        await schema_manager.initialize()
        logger.info("Schema loaded successfully")

        self.initialized = True
        logger.info("OpenRouter Orchestrator initialized")

    async def process_query(
        self,
        user_question: str,
        shop_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Process user query through the complete flow.

        Flow:
        1. Get database schema
        2. Send question + schema to OpenRouter -> Get MongoDB query
        3. Execute query locally on MongoDB
        4. Send question + results to OpenRouter -> Get natural language response

        Args:
            user_question: Natural language question from user
            shop_id: Shop ID for filtering (optional)

        Returns:
            Dictionary with:
                - success: bool
                - answer: Natural language response
                - data: Query results
                - query: Generated MongoDB query
                - error: Error message if failed
        """
        if not self.initialized:
            await self.initialize()

        try:
            # Step 1: Get database schema
            logger.info("=" * 60)
            logger.info("STEP 1: Getting database schema")
            logger.info("=" * 60)

            schema_formatted = schema_manager.get_formatted_schema()
            if not schema_formatted:
                return {
                    "success": False,
                    "error": "Database schema not available",
                    "answer": "I'm unable to process your query right now. Database schema is not loaded."
                }

            logger.info(f"Schema loaded with {len(schema_manager.get_schema().get('collections', {}))} collections")

            # Step 2: Generate MongoDB query using OpenRouter
            logger.info("=" * 60)
            logger.info("STEP 2: Generating MongoDB query using OpenRouter")
            logger.info("=" * 60)
            logger.info(f"User question: {user_question}")
            logger.info(f"Shop ID: {shop_id}")

            query_data = query_generator.generate_query(
                user_question=user_question,
                schema=schema_formatted,
                shop_id=shop_id
            )

            if not query_data:
                return {
                    "success": False,
                    "error": "Failed to generate MongoDB query",
                    "answer": "I'm having trouble understanding your query. Could you rephrase it?"
                }

            logger.info(f"Generated query for collection: {query_data['collection']}")
            logger.info(f"Tool: {query_data['tool_name']}")

            # Step 3: Execute query locally on MongoDB
            logger.info("=" * 60)
            logger.info("STEP 3: Executing query on local MongoDB")
            logger.info("=" * 60)

            collection_name = query_data["collection"]
            pipeline = query_data["pipeline"]

            logger.info(f"Executing aggregation on collection: {collection_name}")

            results = await mongodb.execute_aggregation(collection_name, pipeline)

            logger.info(f"Query returned {len(results) if isinstance(results, list) else 1} result(s)")

            # Step 4: Convert results to natural language using OpenRouter
            logger.info("=" * 60)
            logger.info("STEP 4: Generating natural language response using OpenRouter")
            logger.info("=" * 60)

            natural_response = response_generator.generate_response(
                user_question=user_question,
                query_results=results,
                tool_name=query_data["tool_name"]
            )

            if not natural_response:
                # Fallback to basic response if OpenRouter fails
                natural_response = f"Query executed successfully. Found {len(results) if isinstance(results, list) else 1} result(s)."
                logger.warning("Failed to generate natural language response, using fallback")

            logger.info(f"Final response: {natural_response}")
            logger.info("=" * 60)
            logger.info("QUERY PROCESSING COMPLETE")
            logger.info("=" * 60)

            return {
                "success": True,
                "answer": natural_response,
                "data": results,
                "query": {
                    "collection": collection_name,
                    "pipeline": pipeline,
                    "tool_name": query_data["tool_name"]
                }
            }

        except Exception as e:
            logger.error(f"Error processing query: {e}", exc_info=True)
            return {
                "success": False,
                "error": str(e),
                "answer": "I encountered an error while processing your query. Please try again."
            }

    async def cleanup(self):
        """Cleanup resources"""
        logger.info("Cleaning up OpenRouter Orchestrator...")
        await mongodb.disconnect()
        logger.info("Cleanup complete")


# Global instance
openrouter_orchestrator = OpenRouterOrchestrator()

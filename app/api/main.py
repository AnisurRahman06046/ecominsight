"""Main FastAPI application."""

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import time
import logging
from datetime import datetime

from app.core.config import settings
from app.core.database import mongodb
from app.models.requests import QueryRequest, QueryResponse, HealthResponse
from app.services.query_orchestrator import QueryOrchestrator
from app.services.function_orchestrator import function_orchestrator
from app.services.hybrid_orchestrator import hybrid_orchestrator
from app.services.ollama_service import OllamaService
from app.services.schema_manager import schema_manager
from app.utils.logger import setup_logging

# Setup logging
setup_logging()
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifecycle manager."""
    # Startup
    logger.info(f"Starting {settings.app_name}...")

    # Connect to MongoDB
    connected = await mongodb.connect()
    if not connected:
        logger.error("Failed to connect to MongoDB")
        raise Exception("Database connection failed")

    # Initialize schema manager first
    logger.info("Initializing schema manager...")
    await schema_manager.initialize()
    app.state.schema_manager = schema_manager

    # Initialize services
    app.state.orchestrator = QueryOrchestrator()
    app.state.function_orchestrator = function_orchestrator
    app.state.hybrid_orchestrator = hybrid_orchestrator
    app.state.ollama = OllamaService()

    await app.state.orchestrator.initialize()
    await app.state.function_orchestrator.initialize()
    await app.state.hybrid_orchestrator.initialize()
    await app.state.ollama.initialize(schema_manager=schema_manager)

    logger.info("Application started successfully")
    yield

    # Shutdown
    logger.info("Shutting down...")
    await mongodb.disconnect()
    await app.state.ollama.close()
    logger.info("Shutdown complete")


# Create FastAPI app
app = FastAPI(
    title=settings.app_name,
    version=settings.version,
    description="AI-powered natural language interface for e-commerce analytics",
    lifespan=lifespan,
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def add_process_time_header(request: Request, call_next):
    """Add processing time to response headers."""
    start_time = time.time()
    response = await call_next(request)
    process_time = time.time() - start_time
    response.headers["X-Process-Time"] = str(process_time)
    return response


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "name": settings.app_name,
        "version": settings.version,
        "endpoints": {
            "/health": "Health check",
            "/api/ask": "Process natural language query (LLM-generated queries)",
            "/api/ask-v2": "Process natural language query (Rule-based function calling)",
            "/api/ask-v3": "Process natural language query (ML-based hybrid)",
            "/api/schema": "View database schema",
            "/docs": "Interactive API documentation",
        },
    }


@app.get("/health", response_model=HealthResponse)
async def health_check(request: Request):
    """Health check endpoint."""
    services = {}

    # Check MongoDB
    try:
        await mongodb.database.command("ping")
        services["mongodb"] = True
    except:
        services["mongodb"] = False

    # Check Ollama
    try:
        models = await request.app.state.ollama.list_models()
        services["ollama"] = True
        services["models_available"] = len(models) > 0
    except:
        services["ollama"] = False
        services["models_available"] = False

    # Check cache (if Redis is configured)
    if settings.redis_url:
        try:
            from app.services.cache_service import cache_service

            await cache_service.ping()
            services["cache"] = True
        except:
            services["cache"] = False

    all_healthy = all(services.values())

    return HealthResponse(
        status="healthy" if all_healthy else "degraded",
        timestamp=datetime.utcnow(),
        services=services,
        version=settings.version,
    )


@app.get("/api/collections")
async def list_collections():
    """List all available collections."""
    from app.services.mongodb_mcp_service import mongodb_mcp
    result = await mongodb_mcp.get_collections()
    return result

@app.get("/api/schema")
async def get_schema(request: Request):
    """Get the extracted database schema."""
    try:
        schema_mgr = request.app.state.schema_manager
        return schema_mgr.get_schema_summary()
    except Exception as e:
        logger.error(f"Failed to get schema: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/schema/refresh")
async def refresh_schema(request: Request):
    """Force refresh the database schema."""
    try:
        schema_mgr = request.app.state.schema_manager
        await schema_mgr.refresh_schema()
        return {"message": "Schema refreshed successfully", "summary": schema_mgr.get_schema_summary()}
    except Exception as e:
        logger.error(f"Failed to refresh schema: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/ask", response_model=QueryResponse)
async def process_query(request: Request, query: QueryRequest):
    """
    Process a natural language query.

    The system will:
    1. Check cache for existing results
    2. Classify intent and try predefined KPIs
    3. Use LLM for unknown queries
    4. Use RAG for analytical questions
    5. Return formatted natural language answer
    """
    start_time = time.time()

    try:
        orchestrator: QueryOrchestrator = request.app.state.orchestrator

        # Process the query
        result = await orchestrator.process_query(
            shop_id=query.shop_id,
            question=query.question,
            context=query.context,
            use_cache=query.use_cache,
        )

        processing_time = time.time() - start_time

        return QueryResponse(
            shop_id=query.shop_id,
            question=query.question,
            answer=result["answer"],
            data=result.get("data"),
            query_type=result["query_type"],
            processing_time=processing_time,
            cached=result.get("cached", False),
            metadata=result.get("metadata"),
        )

    except Exception as e:
        logger.error(f"Query processing failed: {e}")
        raise HTTPException(status_code=500, detail=f"Query processing failed: {str(e)}")


@app.post("/api/ask-v2", response_model=QueryResponse)
async def process_query_v2(request: Request, query: QueryRequest):
    """
    Process a natural language query using function calling approach.

    The system will:
    1. Classify intent using rule-based patterns
    2. Call specific database function/tool for that intent
    3. Use LLM only to format the response in natural language
    4. Return formatted answer

    This is more efficient and accurate than LLM-generated queries.
    """
    start_time = time.time()

    try:
        orchestrator = request.app.state.function_orchestrator

        result = await orchestrator.process_query(
            shop_id=query.shop_id,
            question=query.question,
            context=query.context,
            use_cache=query.use_cache,
        )

        processing_time = time.time() - start_time

        return QueryResponse(
            shop_id=query.shop_id,
            question=query.question,
            answer=result["answer"],
            data=result.get("data"),
            query_type=result["query_type"],
            processing_time=processing_time,
            cached=result.get("cached", False),
            metadata=result.get("metadata"),
        )

    except Exception as e:
        logger.error(f"Query processing failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Query processing failed: {str(e)}")


@app.post("/api/ask-v3", response_model=QueryResponse)
async def process_query_v3(request: Request, query: QueryRequest):
    """
    Process a natural language query using ML-based hybrid approach.

    The system will:
    1. Try rule-based classification first (fast)
    2. If rules don't match, use ML model to classify intent
    3. Call specific database function for that intent
    4. Return formatted answer

    This combines the speed of rules with flexibility of ML.
    """
    start_time = time.time()

    try:
        orchestrator = request.app.state.hybrid_orchestrator

        result = await orchestrator.process_query(
            shop_id=query.shop_id,
            question=query.question,
            context=query.context,
            use_cache=query.use_cache,
            use_ml=True,
        )

        processing_time = time.time() - start_time

        return QueryResponse(
            shop_id=query.shop_id,
            question=query.question,
            answer=result["answer"],
            data=result.get("data"),
            query_type=result["query_type"],
            processing_time=processing_time,
            cached=result.get("cached", False),
            metadata=result.get("metadata"),
        )

    except Exception as e:
        logger.error(f"Query processing failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Query processing failed: {str(e)}")


@app.post("/api/mcp/ask", response_model=QueryResponse)
async def mcp_query(request: QueryRequest):
    """
    Process natural language query using MCP (Model Context Protocol) tools.

    This approach uses LLM to select and call specific MongoDB tools
    instead of generating raw MongoDB queries.
    """
    try:
        from app.services.llm_mcp_orchestrator import llm_mcp_orchestrator

        # Convert shop_id to integer
        shop_id = int(request.shop_id)

        # Process using MCP orchestrator
        result = await llm_mcp_orchestrator.process_query(
            question=request.question,
            shop_id=shop_id
        )

        # Convert result to QueryResponse format
        if result.get("success"):
            return QueryResponse(
                shop_id=request.shop_id,
                question=request.question,
                answer=result.get("answer", "Query completed"),
                data=result.get("data", []),
                query_type="mcp",
                processing_time=0.0,  # TODO: Add timing
                cached=False,
                metadata=result.get("metadata", {})
            )
        else:
            raise HTTPException(
                status_code=500,
                detail=result.get("error", "MCP query failed")
            )

    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Invalid shop_id: {str(e)}")
    except Exception as e:
        logger.error(f"MCP query failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"MCP query failed: {str(e)}")


@app.get("/api/models")
async def list_models(request: Request):
    """List available Ollama models."""
    try:
        models = await request.app.state.ollama.list_models()
        return {"models": models, "current": settings.ollama_model}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list models: {str(e)}")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.api.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
    )
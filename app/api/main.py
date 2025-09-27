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
from app.services.ollama_service import OllamaService
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

    # Initialize services
    app.state.orchestrator = QueryOrchestrator()
    app.state.ollama = OllamaService()

    await app.state.orchestrator.initialize()
    await app.state.ollama.initialize()

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
            "/api/ask": "Process natural language query",
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
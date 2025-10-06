"""Main FastAPI application."""

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from contextlib import asynccontextmanager
import time
import logging
from datetime import datetime
from pathlib import Path

from app.core.config import settings
from app.core.database import mongodb
from app.models.requests import QueryRequest, QueryResponse, HealthResponse
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

    # Initialize schema manager
    logger.info("Initializing schema manager...")
    await schema_manager.initialize()
    app.state.schema_manager = schema_manager

    # Initialize Ollama service
    app.state.ollama = OllamaService()
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
    description="AI-powered natural language interface for e-commerce analytics using MCP",
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

# Mount static files
static_dir = Path(__file__).parent.parent.parent / "static"
if static_dir.exists():
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")


@app.middleware("http")
async def add_process_time_header(request: Request, call_next):
    """Add processing time to response headers."""
    start_time = time.time()
    response = await call_next(request)
    process_time = time.time() - start_time
    response.headers["X-Process-Time"] = str(process_time)
    return response


@app.get("/", include_in_schema=False)
async def serve_ui():
    """Serve the query testing UI."""
    static_dir = Path(__file__).parent.parent.parent / "static"
    index_file = static_dir / "index.html"
    if index_file.exists():
        return FileResponse(str(index_file))
    return {
        "name": settings.app_name,
        "version": settings.version,
        "description": "MCP-based natural language query interface",
        "endpoints": {
            "/health": "Health check",
            "/api/mcp/ask": "Process natural language query (MCP tools)",
            "/api/collections": "List available collections",
            "/api/schema": "View database schema",
            "/api/models": "List available Ollama models",
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


@app.get("/api/shops")
async def get_shops():
    """Get list of all shops with their IDs and names."""
    try:
        # Query the shop collection for all unique shops
        pipeline = [
            {"$project": {"id": 1, "name": 1, "slug": 1, "_id": 0}},
            {"$sort": {"id": 1}}
        ]

        shops = await mongodb.execute_aggregation("shop", pipeline)

        if not shops:
            # Fallback: Get unique shop_ids from order collection if shop collection is empty
            logger.warning("Shop collection empty, getting shop IDs from orders")
            pipeline = [
                {"$group": {"_id": "$shop_id"}},
                {"$sort": {"_id": 1}},
                {"$project": {"id": "$_id", "name": {"$concat": ["Shop ", {"$toString": "$_id"}]}, "_id": 0}}
            ]
            shops = await mongodb.execute_aggregation("order", pipeline)

        return {
            "success": True,
            "shops": shops,
            "count": len(shops)
        }
    except Exception as e:
        logger.error(f"Failed to get shops: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/mcp/ask", response_model=QueryResponse)
async def mcp_query(request: QueryRequest):
    """
    Process natural language query using MCP (Model Context Protocol) tools.

    This approach uses:
    1. Pattern matching for known complex queries
    2. Keyword-based tool selection for simple queries
    3. Ollama generation as fallback for novel queries
    """
    start_time = time.time()

    try:
        from app.services.llm_mcp_orchestrator import llm_mcp_orchestrator

        # Convert shop_id to integer
        shop_id = int(request.shop_id)

        # Process using MCP orchestrator
        result = await llm_mcp_orchestrator.process_query(
            question=request.question,
            shop_id=shop_id
        )

        processing_time = time.time() - start_time

        # Convert result to QueryResponse format
        if result.get("success"):
            return QueryResponse(
                shop_id=request.shop_id,
                question=request.question,
                answer=result.get("answer", "Query completed"),
                data=result.get("data", []),
                query_type="mcp",
                processing_time=processing_time,
                cached=False,
                metadata=result.get("metadata", {})
            )
        else:
            # Return user-friendly error message without raising exception
            # This returns 200 status with error info in the response
            return QueryResponse(
                shop_id=request.shop_id,
                question=request.question,
                answer=result.get("answer", "I apologize, but I'm having trouble processing your request."),
                data=[],
                query_type="mcp",
                processing_time=processing_time,
                cached=False,
                metadata={"error": True, "message": result.get("error", "Query failed")}
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
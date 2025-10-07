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
from bson import ObjectId

from app.core.config import settings
from app.core.database import mongodb
from app.models.requests import QueryRequest, QueryResponse, HealthResponse
from app.services.schema_manager import schema_manager
from app.utils.logger import setup_logging
from typing import Optional, Any, Dict, List
# Setup logging
setup_logging()
logger = logging.getLogger(__name__)


def convert_objectid_to_str(data: Any) -> Any:
    """Recursively convert ObjectId to string in data structures."""
    if isinstance(data, ObjectId):
        return str(data)
    elif isinstance(data, dict):
        return {k: convert_objectid_to_str(v) for k, v in data.items()}
    elif isinstance(data, list):
        return [convert_objectid_to_str(item) for item in data]
    else:
        return data


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

    logger.info("Application started successfully")
    yield

    # Shutdown
    logger.info("Shutting down...")
    await mongodb.disconnect()
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

        # Keep shop_id as string (matches database format)
        shop_id = request.shop_id

        # Process using MCP orchestrator
        result = await llm_mcp_orchestrator.process_query(
            question=request.question,
            shop_id=shop_id
        )

        processing_time = time.time() - start_time

        # Convert ObjectId to string in data to avoid serialization errors
        clean_data = convert_objectid_to_str(result.get("data", []))
        clean_metadata = convert_objectid_to_str(result.get("metadata", {}))

        # Convert result to QueryResponse format
        if result.get("success"):
            return QueryResponse(
                shop_id=request.shop_id,
                question=request.question,
                answer=result.get("answer", "Query completed"),
                data=clean_data,
                query_type="mcp",
                processing_time=processing_time,
                cached=False,
                metadata=clean_metadata
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
    """List available HuggingFace models."""
    try:
        return {
            "models": {
                "semantic_router": settings.embedding_model,
                "response_generator": "google/flan-t5-base"
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list models: {str(e)}")


# ========== Data Sync Endpoints ==========

@app.post("/api/sync/trigger")
async def trigger_sync(
    sync_type: str = "incremental",
    tables: Optional[str] = None
):
    """
    Trigger manual data synchronization from MySQL to MongoDB.

    Args:
        sync_type: "full" or "incremental" (default: incremental)
        tables: Comma-separated table names or "all" (default: all)

    Returns:
        Sync summary with statistics
    """
    try:
        from app.sync.sync_scheduler import sync_scheduler

        logger.info(f"Manual {sync_type} sync triggered via API")

        # Temporarily override sync_tables if specified
        original_sync_tables = settings.sync_tables
        if tables:
            settings.sync_tables = tables

        result = await sync_scheduler.trigger_manual_sync(sync_type=sync_type)

        # Restore original settings
        settings.sync_tables = original_sync_tables

        return result

    except Exception as e:
        logger.error(f"Sync trigger failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Sync failed: {str(e)}")


@app.get("/api/sync/status")
async def get_sync_status():
    """
    Get current sync status and scheduler information.

    Returns:
        Sync status including last sync times and scheduler status
    """
    try:
        from app.sync.sync_scheduler import sync_scheduler
        from app.sync.sync_manager import sync_manager

        # Get scheduler status
        scheduler_status = sync_scheduler.get_status()

        # Get sync metadata for all tables
        sync_status = await sync_manager.get_sync_status()

        return {
            "scheduler": scheduler_status,
            "sync_data": sync_status
        }

    except Exception as e:
        logger.error(f"Failed to get sync status: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get status: {str(e)}")


@app.get("/api/sync/test-connection")
async def test_mysql_connection():
    """Test MySQL database connection."""
    try:
        from app.sync.mysql_connector import mysql_connector

        is_connected = mysql_connector.test_connection()

        if is_connected:
            tables = mysql_connector.get_all_tables()
            return {
                "status": "success",
                "connected": True,
                "database": settings.mysql_database,
                "host": settings.mysql_host,
                "tables_count": len(tables),
                "tables": tables[:10]  # Show first 10 tables
            }
        else:
            return {
                "status": "error",
                "connected": False,
                "message": "Failed to connect to MySQL database"
            }

    except Exception as e:
        logger.error(f"MySQL connection test failed: {e}")
        raise HTTPException(status_code=500, detail=f"Connection test failed: {str(e)}")


@app.post("/api/sync/scheduler/start")
async def start_scheduler(interval_seconds: Optional[int] = None):
    """
    Start the automatic sync scheduler.

    Args:
        interval_seconds: Sync interval in seconds (default from settings)

    Returns:
        Scheduler status
    """
    try:
        from app.sync.sync_scheduler import sync_scheduler

        sync_scheduler.start(interval_seconds=interval_seconds)

        return {
            "status": "success",
            "message": "Scheduler started",
            "interval_seconds": interval_seconds or settings.sync_interval
        }

    except Exception as e:
        logger.error(f"Failed to start scheduler: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to start scheduler: {str(e)}")


@app.post("/api/sync/scheduler/stop")
async def stop_scheduler():
    """
    Stop the automatic sync scheduler.

    Returns:
        Scheduler status
    """
    try:
        from app.sync.sync_scheduler import sync_scheduler

        sync_scheduler.stop()

        return {
            "status": "success",
            "message": "Scheduler stopped"
        }

    except Exception as e:
        logger.error(f"Failed to stop scheduler: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to stop scheduler: {str(e)}")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.api.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
    )
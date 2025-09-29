"""
MCP Query API Route
Tests MongoDB MCP tool-based approach
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import Optional

from app.services.llm_mcp_orchestrator import llm_mcp_orchestrator

router = APIRouter()


class MCPQueryRequest(BaseModel):
    shop_id: str = Field(..., description="Shop ID for filtering data")
    question: str = Field(..., description="Natural language question")


class MCPQueryResponse(BaseModel):
    success: bool
    answer: Optional[str] = None
    data: Optional[list] = None
    error: Optional[str] = None
    metadata: Optional[dict] = None


@router.post("/api/mcp/ask", response_model=MCPQueryResponse)
async def mcp_query(request: MCPQueryRequest):
    """
    Process natural language query using MCP tools approach.

    This endpoint uses LLM to select appropriate MongoDB tools
    rather than generating raw MongoDB queries.
    """
    try:
        # Convert shop_id to integer
        shop_id = int(request.shop_id)

        # Process query using MCP orchestrator
        result = await llm_mcp_orchestrator.process_query(
            question=request.question,
            shop_id=shop_id
        )

        return MCPQueryResponse(**result)

    except ValueError as e:
        return MCPQueryResponse(
            success=False,
            error=f"Invalid shop_id: {str(e)}"
        )
    except Exception as e:
        return MCPQueryResponse(
            success=False,
            error=f"Query processing failed: {str(e)}"
        )
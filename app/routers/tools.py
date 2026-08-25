from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional
from app.database import get_db
from app.schemas.tool import (
    ToolCreate,
    ToolUpdate,
    ToolResponse,
    ToolOperationCreate,
    ToolOperationUpdate,
    ToolOperationResponse,
    ToolExecuteRequest,
    ToolRunResult,
)
from app.repositories.tool_repo import ToolRepository
from app.repositories.tool_operation_repo import ToolOperationRepository
from app.runtime.tool_runtime import ToolRuntime

router = APIRouter(prefix="/tools", tags=["Tools Registry"])


# ==========================================
# 1. Tool Container Endpoints
# ==========================================

@router.get("", response_model=List[ToolResponse], summary="List all Tool Containers")
async def list_tools(
    search: Optional[str] = Query(None, description="Search name, displayName, description"),
    category: Optional[str] = Query(None, description="Filter by category (native, external)"),
    kind: Optional[str] = Query(None, description="Filter by kind (native, http, sql, mcp, custom)"),
    status: Optional[str] = Query(None, description="Filter by status (draft, active, disabled)"),
    db: AsyncSession = Depends(get_db),
):
    repo = ToolRepository(db)
    return await repo.get_all(search=search, category=category, kind=kind, status=status)


@router.post(
    "",
    response_model=ToolResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new Tool Container",
)
async def create_tool(
    data: ToolCreate,
    db: AsyncSession = Depends(get_db),
):
    repo = ToolRepository(db)
    existing = await repo.get_by_name(data.name)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Tool with name '{data.name}' already exists.",
        )
    return await repo.create(data)


@router.get("/{tool_id}", response_model=ToolResponse, summary="Get Tool Container by ID")
async def get_tool(
    tool_id: str,
    db: AsyncSession = Depends(get_db),
):
    repo = ToolRepository(db)
    tool = await repo.get_by_id(tool_id)
    if not tool:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Tool with ID '{tool_id}' not found.",
        )
    return tool


@router.put("/{tool_id}", response_model=ToolResponse, summary="Update Tool Container")
async def update_tool(
    tool_id: str,
    data: ToolUpdate,
    db: AsyncSession = Depends(get_db),
):
    repo = ToolRepository(db)
    if data.name:
        existing = await repo.get_by_name(data.name)
        if existing and existing.id != tool_id:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Another tool with name '{data.name}' already exists.",
            )

    updated = await repo.update(tool_id, data)
    if not updated:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Tool with ID '{tool_id}' not found.",
        )
    return updated


@router.delete("/{tool_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Delete Tool Container")
async def delete_tool(
    tool_id: str,
    db: AsyncSession = Depends(get_db),
):
    repo = ToolRepository(db)
    deleted = await repo.delete(tool_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Tool with ID '{tool_id}' not found.",
        )
    return None


# ==========================================
# 2. Tool Operation Child Resource Endpoints
# ==========================================

@router.get("/{tool_id}/operations", response_model=List[ToolOperationResponse], summary="List Operations for Tool")
async def list_operations(
    tool_id: str,
    db: AsyncSession = Depends(get_db),
):
    tool_repo = ToolRepository(db)
    tool = await tool_repo.get_by_id(tool_id)
    if not tool:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Tool '{tool_id}' not found.")

    op_repo = ToolOperationRepository(db)
    return await op_repo.get_by_tool_id(tool_id)


@router.post(
    "/{tool_id}/operations",
    response_model=ToolOperationResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Add an Operation to a Tool",
)
async def create_operation(
    tool_id: str,
    data: ToolOperationCreate,
    db: AsyncSession = Depends(get_db),
):
    tool_repo = ToolRepository(db)
    tool = await tool_repo.get_by_id(tool_id)
    if not tool:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Tool '{tool_id}' not found.")

    op_repo = ToolOperationRepository(db)
    existing = await op_repo.get_by_name(tool_id, data.name)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Operation with name '{data.name}' already exists on tool '{tool.name}'.",
        )
    return await op_repo.create(tool_id, data)


@router.get("/{tool_id}/operations/{operation_id}", response_model=ToolOperationResponse, summary="Get Operation by ID")
async def get_operation(
    tool_id: str,
    operation_id: str,
    db: AsyncSession = Depends(get_db),
):
    op_repo = ToolOperationRepository(db)
    op = await op_repo.get_by_id(tool_id, operation_id)
    if not op:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Operation '{operation_id}' not found.")
    return op


@router.patch("/{tool_id}/operations/{operation_id}", response_model=ToolOperationResponse, summary="Update Operation")
async def update_operation(
    tool_id: str,
    operation_id: str,
    data: ToolOperationUpdate,
    db: AsyncSession = Depends(get_db),
):
    op_repo = ToolOperationRepository(db)
    if data.name:
        existing = await op_repo.get_by_name(tool_id, data.name)
        if existing and existing.id != operation_id:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Another operation named '{data.name}' exists on this tool.",
            )

    updated = await op_repo.update(tool_id, operation_id, data)
    if not updated:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Operation '{operation_id}' not found.")
    return updated


@router.delete("/{tool_id}/operations/{operation_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Delete Operation")
async def delete_operation(
    tool_id: str,
    operation_id: str,
    db: AsyncSession = Depends(get_db),
):
    op_repo = ToolOperationRepository(db)
    deleted = await op_repo.delete(tool_id, operation_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Operation '{operation_id}' not found.")
    return None


# ==========================================
# 3. Authoritative Operation Execution Endpoint
# ==========================================

@router.post(
    "/{tool_id}/operations/{operation_id}/execute",
    response_model=ToolRunResult,
    summary="Execute a Tool Operation Standalone",
)
async def execute_tool_operation(
    tool_id: str,
    operation_id: str,
    req: ToolExecuteRequest,
    db: AsyncSession = Depends(get_db),
):
    tool_repo = ToolRepository(db)
    tool_model = await tool_repo.get_model_by_id(tool_id)
    if not tool_model:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Tool '{tool_id}' not found.")

    op_repo = ToolOperationRepository(db)
    op_model = await op_repo.get_model_by_id(tool_id, operation_id)
    if not op_model:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Operation '{operation_id}' not found on tool '{tool_model.name}'.",
        )

    # Authoritative runtime execution
    return await ToolRuntime.execute_operation(
        tool=tool_model,
        operation=op_model,
        input_data=req.input,
        context=req.context,
    )

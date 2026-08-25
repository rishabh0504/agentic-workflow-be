from fastapi import APIRouter, HTTPException, Depends
from typing import List, Optional, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.repositories.workflow_repo import WorkflowRepository
from app.schemas.workflow import (
    WorkflowCreate,
    WorkflowUpdate,
    WorkflowResponse,
    WorkflowVersionCreate,
    WorkflowVersionResponse,
    WorkflowRunCreate,
    WorkflowRunResponse,
)
from app.runtime.workflow_compiler import WorkflowCompiler

router = APIRouter(prefix="/workflows", tags=["Workflow Authoring & Orchestration"])


@router.get("", response_model=List[WorkflowResponse], summary="List all saved workflows")
async def list_workflows(
    category: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
):
    repo = WorkflowRepository(db)
    return await repo.get_all(category=category)


@router.post("", response_model=WorkflowResponse, summary="Create a new workflow")
async def create_workflow(
    data: WorkflowCreate,
    db: AsyncSession = Depends(get_db),
):
    repo = WorkflowRepository(db)
    existing = await repo.get_by_name(data.name)
    if existing:
        raise HTTPException(status_code=400, detail=f"Workflow with name '{data.name}' already exists.")

    if data.initialVersion and (data.initialVersion.nodes or data.initialVersion.edges):
        valid, errors = WorkflowCompiler.validate_graph(data.initialVersion.nodes, data.initialVersion.edges)
        if not valid and data.status == "PUBLISHED":
            raise HTTPException(status_code=400, detail={"message": "Cannot publish invalid workflow graph", "errors": errors})

    return await repo.create(data)


@router.get("/{workflow_id}", response_model=WorkflowResponse, summary="Get a workflow and its active version")
async def get_workflow(
    workflow_id: str,
    db: AsyncSession = Depends(get_db),
):
    repo = WorkflowRepository(db)
    wf = await repo.get_by_id(workflow_id)
    if not wf:
        raise HTTPException(status_code=404, detail=f"Workflow '{workflow_id}' not found.")
    return wf


@router.put("/{workflow_id}", response_model=WorkflowVersionResponse, summary="Save a new version/draft for a workflow")
async def save_workflow_version(
    workflow_id: str,
    data: WorkflowVersionCreate,
    status: Optional[str] = "DRAFT",
    db: AsyncSession = Depends(get_db),
):
    repo = WorkflowRepository(db)
    try:
        return await repo.save_version(workflow_id, data, status=status or "DRAFT")
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/{workflow_id}/publish", response_model=WorkflowResponse, summary="Validate and publish a workflow version")
async def publish_workflow(
    workflow_id: str,
    version_id: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
):
    repo = WorkflowRepository(db)
    wf = await repo.get_by_id(workflow_id)
    if not wf:
        raise HTTPException(status_code=404, detail=f"Workflow '{workflow_id}' not found.")

    version_to_check = wf.activeVersion
    if version_to_check:
        valid, errors = WorkflowCompiler.validate_graph(version_to_check.nodes, version_to_check.edges)
        if not valid:
            raise HTTPException(status_code=400, detail={"message": "Workflow graph validation failed", "errors": errors})

    try:
        return await repo.publish(workflow_id, version_id=version_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/{workflow_id}/versions", response_model=List[WorkflowVersionResponse], summary="List all version history")
async def get_workflow_versions(
    workflow_id: str,
    db: AsyncSession = Depends(get_db),
):
    repo = WorkflowRepository(db)
    return await repo.get_versions(workflow_id)


@router.delete("/{workflow_id}", status_code=204, summary="Delete a Workflow (Without affecting Agents or Tools)")
async def delete_workflow(
    workflow_id: str,
    db: AsyncSession = Depends(get_db),
):
    repo = WorkflowRepository(db)
    deleted = await repo.delete(workflow_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Workflow '{workflow_id}' not found.")
    return None

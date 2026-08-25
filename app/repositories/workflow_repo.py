from typing import List, Optional, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import datetime, timezone
import time
import secrets
from app.models.workflow import (
    WorkflowModel,
    WorkflowVersionModel,
    WorkflowRunModel,
    WorkflowNodeRunModel,
)
from app.schemas.workflow import (
    WorkflowCreate,
    WorkflowUpdate,
    WorkflowResponse,
    WorkflowVersionResponse,
    WorkflowVersionCreate,
    WorkflowRunResponse,
    WorkflowNodeRunResponse,
)


def version_to_response(v: WorkflowVersionModel) -> WorkflowVersionResponse:
    return WorkflowVersionResponse(
        id=v.id,
        workflowId=v.workflow_id,
        version=v.version,
        status=v.status,
        nodes=v.nodes or [],
        edges=v.edges or [],
        variables=v.variables or {},
        inputSchema=v.input_schema,
        outputSchema=v.output_schema,
        viewport=v.viewport or {"x": 0, "y": 0, "zoom": 1},
        changelog=v.changelog,
        createdAt=v.created_at.isoformat() if v.created_at else datetime.now(timezone.utc).isoformat(),
    )


def workflow_to_response(w: WorkflowModel, active_version: Optional[WorkflowVersionModel] = None) -> WorkflowResponse:
    # Pick active version if available, else first in list
    selected_version = active_version
    if not selected_version and w.versions:
        if w.current_version_id:
            selected_version = next((v for v in w.versions if v.id == w.current_version_id), w.versions[-1])
        else:
            selected_version = w.versions[-1]

    return WorkflowResponse(
        id=w.id,
        name=w.name,
        displayName=w.display_name,
        description=w.description,
        category=w.category,
        status=w.status,
        currentVersionId=w.current_version_id,
        activeVersion=version_to_response(selected_version) if selected_version else None,
        createdAt=w.created_at.isoformat() if w.created_at else datetime.now(timezone.utc).isoformat(),
        updatedAt=w.updated_at.isoformat() if w.updated_at else datetime.now(timezone.utc).isoformat(),
    )


class WorkflowRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_all(self, category: Optional[str] = None) -> List[WorkflowResponse]:
        query = select(WorkflowModel).order_by(WorkflowModel.updated_at.desc())
        if category:
            query = query.where(WorkflowModel.category == category)
        result = await self.db.execute(query)
        models = result.scalars().all()
        return [workflow_to_response(m) for m in models]

    async def get_by_id(self, workflow_id: str) -> Optional[WorkflowResponse]:
        query = select(WorkflowModel).where(WorkflowModel.id == workflow_id)
        result = await self.db.execute(query)
        model = result.scalar_one_or_none()
        return workflow_to_response(model) if model else None

    async def get_model_by_id(self, workflow_id: str) -> Optional[WorkflowModel]:
        query = select(WorkflowModel).where(WorkflowModel.id == workflow_id)
        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def get_by_name(self, name: str) -> Optional[WorkflowResponse]:
        query = select(WorkflowModel).where(WorkflowModel.name == name)
        result = await self.db.execute(query)
        model = result.scalar_one_or_none()
        return workflow_to_response(model) if model else None

    async def create(self, data: WorkflowCreate) -> WorkflowResponse:
        wid = f"wf_{int(time.time() * 1000)}_{secrets.token_hex(3)}"
        now = datetime.now(timezone.utc)

        workflow = WorkflowModel(
            id=wid,
            name=data.name,
            display_name=data.displayName,
            description=data.description,
            category=data.category,
            status=data.status or "DRAFT",
            created_at=now,
            updated_at=now,
        )
        self.db.add(workflow)
        await self.db.flush()

        # Create initial Version 1
        vid = f"wfv_{int(time.time() * 1000)}_{secrets.token_hex(3)}"
        initial_v = data.initialVersion or WorkflowVersionCreate()
        version = WorkflowVersionModel(
            id=vid,
            workflow_id=wid,
            version=1,
            status=data.status or "DRAFT",
            nodes=initial_v.nodes,
            edges=initial_v.edges,
            variables=initial_v.variables,
            input_schema=initial_v.inputSchema,
            output_schema=initial_v.outputSchema,
            viewport=initial_v.viewport,
            changelog=initial_v.changelog or "Initial version",
            created_at=now,
        )
        self.db.add(version)
        workflow.current_version_id = vid

        await self.db.commit()
        await self.db.refresh(workflow)
        return workflow_to_response(workflow, version)

    async def save_version(self, workflow_id: str, version_data: WorkflowVersionCreate, status: str = "DRAFT") -> WorkflowVersionResponse:
        workflow = await self.get_model_by_id(workflow_id)
        if not workflow:
            raise ValueError(f"Workflow '{workflow_id}' not found.")

        now = datetime.now(timezone.utc)
        next_version_num = (max([v.version for v in workflow.versions], default=0)) + 1
        vid = f"wfv_{int(time.time() * 1000)}_{secrets.token_hex(3)}"

        version = WorkflowVersionModel(
            id=vid,
            workflow_id=workflow_id,
            version=next_version_num,
            status=status,
            nodes=version_data.nodes,
            edges=version_data.edges,
            variables=version_data.variables,
            input_schema=version_data.inputSchema,
            output_schema=version_data.outputSchema,
            viewport=version_data.viewport,
            changelog=version_data.changelog,
            created_at=now,
        )
        self.db.add(version)
        workflow.current_version_id = vid
        workflow.status = status
        workflow.updated_at = now

        await self.db.commit()
        await self.db.refresh(version)
        return version_to_response(version)

    async def publish(self, workflow_id: str, version_id: Optional[str] = None) -> WorkflowResponse:
        workflow = await self.get_model_by_id(workflow_id)
        if not workflow:
            raise ValueError(f"Workflow '{workflow_id}' not found.")

        target_vid = version_id or workflow.current_version_id
        target_version = next((v for v in workflow.versions if v.id == target_vid), None)
        if not target_version:
            raise ValueError(f"Version '{target_vid}' not found for workflow.")

        target_version.status = "PUBLISHED"
        workflow.status = "PUBLISHED"
        workflow.current_version_id = target_version.id
        workflow.updated_at = datetime.now(timezone.utc)

        await self.db.commit()
        await self.db.refresh(workflow)
        return workflow_to_response(workflow, target_version)

    async def get_versions(self, workflow_id: str) -> List[WorkflowVersionResponse]:
        query = select(WorkflowVersionModel).where(WorkflowVersionModel.workflow_id == workflow_id).order_by(WorkflowVersionModel.version.desc())
        result = await self.db.execute(query)
        models = result.scalars().all()
        return [version_to_response(m) for m in models]

    async def delete(self, workflow_id: str) -> bool:
        workflow = await self.get_model_by_id(workflow_id)
        if not workflow:
            # Fallback check by unique name
            wf_by_name = await self.get_by_name(workflow_id)
            if wf_by_name:
                workflow = await self.get_model_by_id(wf_by_name.id)

        if not workflow:
            return False

        await self.db.delete(workflow)
        await self.db.commit()
        return True

from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, or_, delete
from datetime import datetime, timezone
import time
import secrets
from app.models.tool import ToolModel
from app.models.tool_operation import ToolOperationModel
from app.schemas.tool import (
    ToolCreate,
    ToolUpdate,
    ToolResponse,
    ToolOperationResponse,
    ToolClassification,
    ToolRuntimeConfig,
)


def operation_model_to_response(model: ToolOperationModel) -> ToolOperationResponse:
    return ToolOperationResponse(
        id=model.id,
        toolId=model.tool_id,
        name=model.name,
        displayName=model.display_name,
        description=model.description,
        inputSchema=model.input_schema or {},
        outputSchema=model.output_schema,
        implementation=model.implementation or {},
        classification=ToolClassification(**(model.classification or {})),
        runtime=ToolRuntimeConfig(**(model.runtime or {})),
        enabled=model.enabled,
        createdAt=model.created_at.isoformat() if model.created_at else datetime.now(timezone.utc).isoformat(),
        updatedAt=model.updated_at.isoformat() if model.updated_at else datetime.now(timezone.utc).isoformat(),
    )


def tool_model_to_response(model: ToolModel) -> ToolResponse:
    return ToolResponse(
        id=model.id,
        name=model.name,
        displayName=model.display_name,
        description=model.description,
        category=model.category,
        kind=model.kind,
        status=model.status,
        version=model.version,
        operations=[operation_model_to_response(op) for op in (model.operations or [])],
        createdAt=model.created_at.isoformat() if model.created_at else datetime.now(timezone.utc).isoformat(),
        updatedAt=model.updated_at.isoformat() if model.updated_at else datetime.now(timezone.utc).isoformat(),
    )


class ToolRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_all(
        self,
        search: Optional[str] = None,
        category: Optional[str] = None,
        kind: Optional[str] = None,
        status: Optional[str] = None,
    ) -> List[ToolResponse]:
        query = select(ToolModel).order_by(ToolModel.created_at.desc())

        if search:
            search_pattern = f"%{search.lower()}%"
            query = query.where(
                or_(
                    ToolModel.name.ilike(search_pattern),
                    ToolModel.display_name.ilike(search_pattern),
                    ToolModel.description.ilike(search_pattern),
                )
            )

        if category:
            query = query.where(ToolModel.category == category)

        if kind:
            query = query.where(ToolModel.kind == kind)

        if status:
            query = query.where(ToolModel.status == status)

        result = await self.db.execute(query)
        models = result.scalars().all()
        return [tool_model_to_response(m) for m in models]

    async def get_by_id(self, tool_id: str) -> Optional[ToolResponse]:
        query = select(ToolModel).where(ToolModel.id == tool_id)
        result = await self.db.execute(query)
        model = result.scalar_one_or_none()
        return tool_model_to_response(model) if model else None

    async def get_model_by_id(self, tool_id: str) -> Optional[ToolModel]:
        query = select(ToolModel).where(ToolModel.id == tool_id)
        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def get_by_name(self, name: str) -> Optional[ToolResponse]:
        query = select(ToolModel).where(ToolModel.name == name)
        result = await self.db.execute(query)
        model = result.scalar_one_or_none()
        return tool_model_to_response(model) if model else None

    async def create(self, data: ToolCreate) -> ToolResponse:
        tool_id = data.id or f"tool_{int(time.time() * 1000)}_{secrets.token_hex(3)}"
        now = datetime.now(timezone.utc)

        model = ToolModel(
            id=tool_id,
            name=data.name,
            display_name=data.displayName,
            description=data.description or "",
            category=data.category,
            kind=data.kind,
            status=data.status,
            version=data.version,
            created_at=now,
            updated_at=now,
        )
        self.db.add(model)
        await self.db.flush()

        # Create initial operations if provided
        if data.operations:
            for op_data in data.operations:
                op_id = op_data.id or f"op_{int(time.time() * 1000)}_{secrets.token_hex(3)}"
                op_model = ToolOperationModel(
                    id=op_id,
                    tool_id=tool_id,
                    name=op_data.name,
                    display_name=op_data.displayName,
                    description=op_data.description or "",
                    input_schema=op_data.inputSchema,
                    output_schema=op_data.outputSchema,
                    implementation=op_data.implementation,
                    classification=op_data.classification.model_dump(),
                    runtime=op_data.runtime.model_dump(),
                    enabled=op_data.enabled,
                    created_at=now,
                    updated_at=now,
                )
                self.db.add(op_model)
            await self.db.flush()

        await self.db.refresh(model)
        return tool_model_to_response(model)

    async def update(self, tool_id: str, data: ToolUpdate) -> Optional[ToolResponse]:
        query = select(ToolModel).where(ToolModel.id == tool_id)
        result = await self.db.execute(query)
        model = result.scalar_one_or_none()

        if not model:
            return None

        if data.name is not None:
            model.name = data.name
        if data.displayName is not None:
            model.display_name = data.displayName
        if data.description is not None:
            model.description = data.description
        if data.category is not None:
            model.category = data.category
        if data.kind is not None:
            model.kind = data.kind
        if data.status is not None:
            model.status = data.status
        if data.version is not None:
            model.version = data.version

        model.updated_at = datetime.now(timezone.utc)
        await self.db.flush()
        await self.db.refresh(model)
        return tool_model_to_response(model)

    async def delete(self, tool_id: str) -> bool:
        query = delete(ToolModel).where(ToolModel.id == tool_id)
        result = await self.db.execute(query)
        return result.rowcount > 0

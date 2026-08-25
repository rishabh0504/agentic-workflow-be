from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
from datetime import datetime, timezone
import time
import secrets
from app.models.tool_operation import ToolOperationModel
from app.schemas.tool import ToolOperationCreate, ToolOperationUpdate, ToolOperationResponse
from app.repositories.tool_repo import operation_model_to_response


class ToolOperationRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_tool_id(self, tool_id: str) -> List[ToolOperationResponse]:
        query = select(ToolOperationModel).where(ToolOperationModel.tool_id == tool_id).order_by(ToolOperationModel.created_at.asc())
        result = await self.db.execute(query)
        models = result.scalars().all()
        return [operation_model_to_response(m) for m in models]

    async def get_by_id(self, tool_id: str, operation_id: str) -> Optional[ToolOperationResponse]:
        query = select(ToolOperationModel).where(
            ToolOperationModel.tool_id == tool_id,
            ToolOperationModel.id == operation_id,
        )
        result = await self.db.execute(query)
        model = result.scalar_one_or_none()
        return operation_model_to_response(model) if model else None

    async def get_model_by_id(self, tool_id: str, operation_id: str) -> Optional[ToolOperationModel]:
        query = select(ToolOperationModel).where(
            ToolOperationModel.tool_id == tool_id,
            ToolOperationModel.id == operation_id,
        )
        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def get_by_name(self, tool_id: str, name: str) -> Optional[ToolOperationResponse]:
        query = select(ToolOperationModel).where(
            ToolOperationModel.tool_id == tool_id,
            ToolOperationModel.name == name,
        )
        result = await self.db.execute(query)
        model = result.scalar_one_or_none()
        return operation_model_to_response(model) if model else None

    async def create(self, tool_id: str, data: ToolOperationCreate) -> ToolOperationResponse:
        op_id = data.id or f"op_{int(time.time() * 1000)}_{secrets.token_hex(3)}"
        now = datetime.now(timezone.utc)

        model = ToolOperationModel(
            id=op_id,
            tool_id=tool_id,
            name=data.name,
            display_name=data.displayName,
            description=data.description or "",
            input_schema=data.inputSchema,
            output_schema=data.outputSchema,
            implementation=data.implementation,
            classification=data.classification.model_dump(),
            runtime=data.runtime.model_dump(),
            enabled=data.enabled,
            created_at=now,
            updated_at=now,
        )
        self.db.add(model)
        await self.db.flush()
        await self.db.refresh(model)
        return operation_model_to_response(model)

    async def update(self, tool_id: str, operation_id: str, data: ToolOperationUpdate) -> Optional[ToolOperationResponse]:
        query = select(ToolOperationModel).where(
            ToolOperationModel.tool_id == tool_id,
            ToolOperationModel.id == operation_id,
        )
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
        if data.inputSchema is not None:
            model.input_schema = data.inputSchema
        if data.outputSchema is not None:
            model.output_schema = data.outputSchema
        if data.implementation is not None:
            model.implementation = data.implementation
        if data.classification is not None:
            model.classification = data.classification.model_dump()
        if data.runtime is not None:
            model.runtime = data.runtime.model_dump()
        if data.enabled is not None:
            model.enabled = data.enabled

        model.updated_at = datetime.now(timezone.utc)
        await self.db.flush()
        await self.db.refresh(model)
        return operation_model_to_response(model)

    async def delete(self, tool_id: str, operation_id: str) -> bool:
        query = delete(ToolOperationModel).where(
            ToolOperationModel.tool_id == tool_id,
            ToolOperationModel.id == operation_id,
        )
        result = await self.db.execute(query)
        return result.rowcount > 0

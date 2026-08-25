import json as _json
from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, or_, delete
from datetime import datetime, timezone
import time
import secrets
from app.models.agent import AgentModel
from app.schemas.agent import AgentCreate, AgentUpdate, AgentResponse, AgentModelConfig, AgentRuntimeConfig


def _parse_jsonb(val):
    """Safely parse a JSONB field that may come back from PostgreSQL as a str or dict."""
    if isinstance(val, dict):
        return val
    if isinstance(val, str):
        try:
            parsed = _json.loads(val)
            return parsed if isinstance(parsed, dict) else {}
        except Exception:
            return {}
    return {}


def model_to_response(model: AgentModel) -> AgentResponse:
    return AgentResponse(
        id=model.id,
        name=model.name,
        displayName=model.display_name,
        description=model.description,
        model=AgentModelConfig(**_parse_jsonb(model.model)),
        instructions=model.instructions or "",
        toolIds=model.tool_ids or [],
        inputSchema=model.input_schema,
        outputSchema=model.output_schema,
        runtime=AgentRuntimeConfig(**_parse_jsonb(model.runtime)),
        status=model.status,
        version=model.version,
        createdAt=model.created_at.isoformat() if model.created_at else datetime.now(timezone.utc).isoformat(),
        updatedAt=model.updated_at.isoformat() if model.updated_at else datetime.now(timezone.utc).isoformat(),
    )


class AgentRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_all(
        self,
        search: Optional[str] = None,
        provider: Optional[str] = None,
        status: Optional[str] = None,
    ) -> List[AgentResponse]:
        query = select(AgentModel).order_by(AgentModel.created_at.desc())

        if search:
            search_pattern = f"%{search.lower()}%"
            query = query.where(
                or_(
                    AgentModel.name.ilike(search_pattern),
                    AgentModel.display_name.ilike(search_pattern),
                    AgentModel.description.ilike(search_pattern),
                )
            )

        if status:
            query = query.where(AgentModel.status == status)

        result = await self.db.execute(query)
        models = result.scalars().all()

        responses = [model_to_response(m) for m in models]
        if provider:
            responses = [r for r in responses if r.model.providerId == provider]

        return responses

    async def get_by_id(self, agent_id: str) -> Optional[AgentResponse]:
        query = select(AgentModel).where(AgentModel.id == agent_id)
        result = await self.db.execute(query)
        model = result.scalar_one_or_none()
        return model_to_response(model) if model else None

    async def get_model_by_id(self, agent_id: str) -> Optional[AgentModel]:
        query = select(AgentModel).where(AgentModel.id == agent_id)
        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def get_by_name(self, name: str) -> Optional[AgentResponse]:
        query = select(AgentModel).where(AgentModel.name == name)
        result = await self.db.execute(query)
        model = result.scalar_one_or_none()
        return model_to_response(model) if model else None

    async def create(self, data: AgentCreate) -> AgentResponse:
        agent_id = data.id or f"agent_{int(time.time() * 1000)}_{secrets.token_hex(3)}"
        now = datetime.now(timezone.utc)

        model = AgentModel(
            id=agent_id,
            name=data.name,
            display_name=data.displayName,
            description=data.description,
            model=data.model.model_dump(),
            instructions=data.instructions,
            tool_ids=data.toolIds,
            input_schema=data.inputSchema,
            output_schema=data.outputSchema,
            runtime=data.runtime.model_dump(),
            status=data.status,
            version=data.version,
            created_at=now,
            updated_at=now,
        )

        self.db.add(model)
        await self.db.flush()
        await self.db.refresh(model)
        return model_to_response(model)

    async def update(self, agent_id: str, data: AgentUpdate) -> Optional[AgentResponse]:
        query = select(AgentModel).where(AgentModel.id == agent_id)
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
        if data.model is not None:
            model.model = data.model.model_dump()
        if data.instructions is not None:
            model.instructions = data.instructions
        if data.toolIds is not None:
            model.tool_ids = data.toolIds
        if data.inputSchema is not None:
            model.input_schema = data.inputSchema
        if data.outputSchema is not None:
            model.output_schema = data.outputSchema
        if data.runtime is not None:
            model.runtime = data.runtime.model_dump()
        if data.status is not None:
            model.status = data.status
        if data.version is not None:
            model.version = data.version

        model.updated_at = datetime.now(timezone.utc)
        await self.db.flush()
        await self.db.refresh(model)
        return model_to_response(model)

    async def delete(self, agent_id: str) -> bool:
        query = delete(AgentModel).where(AgentModel.id == agent_id)
        result = await self.db.execute(query)
        return result.rowcount > 0

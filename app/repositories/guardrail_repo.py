from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, or_
from datetime import datetime, timezone
import time
import secrets
from app.models.guardrail import GuardrailModel, GuardrailRuleModel, GuardrailBindingModel, GuardrailExecutionModel
from app.schemas.guardrail import GuardrailCreate, GuardrailResponse, GuardrailRuleResponse


def guardrail_to_response(model: GuardrailModel) -> GuardrailResponse:
    rules = [
        GuardrailRuleResponse(
            id=r.id,
            guardrailId=r.guardrail_id,
            name=r.name,
            ruleType=r.rule_type,
            operator=r.operator,
            config=r.config or {},
            severity=r.severity,
            enabled=r.enabled,
            orderIndex=r.order_index,
            createdAt=r.created_at.isoformat() if r.created_at else datetime.now(timezone.utc).isoformat(),
        )
        for r in (model.rules or [])
    ]

    return GuardrailResponse(
        id=model.id,
        name=model.name,
        displayName=model.display_name,
        description=model.description,
        category=model.category,
        executionMode=model.execution_mode,
        defaultAction=model.default_action,
        status=model.status,
        config=model.config or {},
        rules=rules,
        version=model.version,
        createdAt=model.created_at.isoformat() if model.created_at else datetime.now(timezone.utc).isoformat(),
        updatedAt=model.updated_at.isoformat() if model.updated_at else datetime.now(timezone.utc).isoformat(),
    )


class GuardrailRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_all(self, category: Optional[str] = None) -> List[GuardrailResponse]:
        query = select(GuardrailModel).order_by(GuardrailModel.created_at.desc())
        if category:
            query = query.where(GuardrailModel.category == category)
        result = await self.db.execute(query)
        models = result.scalars().all()
        return [guardrail_to_response(m) for m in models]

    async def get_by_id(self, guardrail_id: str) -> Optional[GuardrailResponse]:
        query = select(GuardrailModel).where(GuardrailModel.id == guardrail_id)
        result = await self.db.execute(query)
        model = result.scalar_one_or_none()
        return guardrail_to_response(model) if model else None

    async def get_model_by_id(self, guardrail_id: str) -> Optional[GuardrailModel]:
        query = select(GuardrailModel).where(GuardrailModel.id == guardrail_id)
        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def get_by_name(self, name: str) -> Optional[GuardrailResponse]:
        query = select(GuardrailModel).where(GuardrailModel.name == name)
        result = await self.db.execute(query)
        model = result.scalar_one_or_none()
        return guardrail_to_response(model) if model else None

    async def create(self, data: GuardrailCreate) -> GuardrailResponse:
        gid = f"grd_{int(time.time() * 1000)}_{secrets.token_hex(3)}"
        now = datetime.now(timezone.utc)

        model = GuardrailModel(
            id=gid,
            name=data.name,
            display_name=data.displayName,
            description=data.description,
            category=data.category,
            execution_mode=data.executionMode,
            default_action=data.defaultAction,
            status=data.status,
            config=data.config,
            version=1,
            created_at=now,
            updated_at=now,
        )
        self.db.add(model)
        await self.db.flush()

        for idx, rule in enumerate(data.rules):
            rid = f"gru_{int(time.time() * 1000)}_{secrets.token_hex(2)}"
            rule_model = GuardrailRuleModel(
                id=rid,
                guardrail_id=gid,
                name=rule.name,
                rule_type=rule.ruleType,
                operator=rule.operator,
                config=rule.config,
                severity=rule.severity,
                enabled=rule.enabled,
                order_index=rule.orderIndex or idx,
                created_at=now,
            )
            self.db.add(rule_model)

        await self.db.commit()
        await self.db.refresh(model)
        return guardrail_to_response(model)

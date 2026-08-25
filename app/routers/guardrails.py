from fastapi import APIRouter, HTTPException, Depends
from typing import List, Optional, Dict, Any
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.repositories.guardrail_repo import GuardrailRepository
from app.schemas.guardrail import GuardrailCreate, GuardrailResponse, GuardrailResult
from app.runtime.guardrail_runtime import GuardrailManager

router = APIRouter(prefix="/guardrails", tags=["Guardrails Policy Subsystem"])


class GuardrailEvaluateRequest(BaseModel):
    payload: Any
    scope: Optional[str] = "AGENT_OUTPUT"
    workflowRunId: Optional[str] = None
    agentRunId: Optional[str] = None
    context: Optional[Dict[str, Any]] = None


@router.get("", response_model=List[GuardrailResponse], summary="List all configured Guardrails")
async def list_guardrails(
    category: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
):
    repo = GuardrailRepository(db)
    return await repo.get_all(category=category)


@router.post("", response_model=GuardrailResponse, summary="Create a new Guardrail Policy")
async def create_guardrail(
    data: GuardrailCreate,
    db: AsyncSession = Depends(get_db),
):
    repo = GuardrailRepository(db)
    existing = await repo.get_by_name(data.name)
    if existing:
        raise HTTPException(status_code=400, detail=f"Guardrail with name '{data.name}' already exists.")
    return await repo.create(data)


@router.post("/{guardrail_id}/evaluate", response_model=GuardrailResult, summary="Execute a Guardrail check against a payload")
async def evaluate_guardrail(
    guardrail_id: str,
    body: GuardrailEvaluateRequest,
    db: AsyncSession = Depends(get_db),
):
    repo = GuardrailRepository(db)
    model = await repo.get_model_by_id(guardrail_id)
    if not model:
        g_by_name = await repo.get_by_name(guardrail_id)
        if g_by_name:
            model = await repo.get_model_by_id(g_by_name.id)

    if not model:
        raise HTTPException(status_code=404, detail=f"Guardrail '{guardrail_id}' not found.")

    return await GuardrailManager.evaluate(
        guardrail=model,
        payload=body.payload,
        db=db,
        scope=body.scope or "AGENT_OUTPUT",
        workflow_run_id=body.workflowRunId,
        agent_run_id=body.agentRunId,
        context=body.context,
    )

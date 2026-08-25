from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Dict, Any, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.repositories.agent_repo import AgentRepository
from app.runtime.agent_runtime import AgentRuntime

router = APIRouter(prefix="/agents", tags=["Agent Execution & Runs"])


class AgentRunRequest(BaseModel):
    prompt: str
    maxTurns: Optional[int] = None
    workflowRunId: Optional[str] = None
    timeoutSeconds: Optional[float] = 120.0
    modelOverride: Optional[Dict[str, Any]] = None


@router.post("/{agent_id}/run", summary="Execute an Agent with the Multi-Turn Autonomous ReAct Engine")
async def run_agent(
    agent_id: str,
    payload: AgentRunRequest,
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """
    Executes the agent in an authoritative multi-turn loop with attached tools,
    persisting run state and events to PostgreSQL.
    """
    agent_repo = AgentRepository(db)
    agent_model = await agent_repo.get_model_by_id(agent_id)
    if not agent_model:
        agent_by_name = await agent_repo.get_by_name(agent_id)
        if agent_by_name:
            agent_model = await agent_repo.get_model_by_id(agent_by_name.id)

    if not agent_model:
        raise HTTPException(status_code=404, detail=f"Agent '{agent_id}' not found.")

    if agent_model.status != "active":
        raise HTTPException(status_code=400, detail=f"Agent '{agent_id}' is not active (status: {agent_model.status}).")

    try:
        result = await AgentRuntime.run(
            agent=agent_model,
            prompt=payload.prompt,
            db=db,
            max_turns=payload.maxTurns,
            workflow_run_id=payload.workflowRunId,
            timeout_s=payload.timeoutSeconds or 120.0,
            model_override=payload.modelOverride,
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Agent runtime execution error: {str(e)}")

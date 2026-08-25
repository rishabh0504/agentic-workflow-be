from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional
from app.database import get_db
from app.schemas.agent import AgentCreate, AgentUpdate, AgentResponse
from app.repositories.agent_repo import AgentRepository

router = APIRouter(prefix="/agents", tags=["Agents Registry"])


@router.get("", response_model=List[AgentResponse], summary="List all Agent Definitions")
async def list_agents(
    search: Optional[str] = Query(None, description="Search across name, displayName, and description"),
    provider: Optional[str] = Query(None, description="Filter by AI provider (openai, anthropic, ollama, etc.)"),
    status: Optional[str] = Query(None, description="Filter by lifecycle status (draft, active, disabled)"),
    db: AsyncSession = Depends(get_db),
):
    repo = AgentRepository(db)
    return await repo.get_all(search=search, provider=provider, status=status)


@router.post(
    "",
    response_model=AgentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new Agent Definition",
)
async def create_agent(
    data: AgentCreate,
    db: AsyncSession = Depends(get_db),
):
    repo = AgentRepository(db)
    existing = await repo.get_by_name(data.name)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Agent with name '{data.name}' already exists.",
        )
    return await repo.create(data)


@router.get("/{agent_id}", response_model=AgentResponse, summary="Get Agent Definition by ID")
async def get_agent(
    agent_id: str,
    db: AsyncSession = Depends(get_db),
):
    repo = AgentRepository(db)
    agent = await repo.get_by_id(agent_id)
    if not agent:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Agent with ID '{agent_id}' not found.",
        )
    return agent


@router.put("/{agent_id}", response_model=AgentResponse, summary="Update Agent Definition")
async def update_agent(
    agent_id: str,
    data: AgentUpdate,
    db: AsyncSession = Depends(get_db),
):
    repo = AgentRepository(db)
    if data.name:
        existing = await repo.get_by_name(data.name)
        if existing and existing.id != agent_id:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Another agent with name '{data.name}' already exists.",
            )

    updated = await repo.update(agent_id, data)
    if not updated:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Agent with ID '{agent_id}' not found.",
        )
    return updated


@router.delete("/{agent_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Delete Agent Definition")
async def delete_agent(
    agent_id: str,
    db: AsyncSession = Depends(get_db),
):
    repo = AgentRepository(db)
    deleted = await repo.delete(agent_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Agent with ID '{agent_id}' not found.",
        )
    return None

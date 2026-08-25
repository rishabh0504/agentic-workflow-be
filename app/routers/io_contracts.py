from fastapi import APIRouter, HTTPException, Depends, Query, status
from typing import List, Optional, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.repositories.io_contract_repo import IOContractRepository
from app.schemas.io_contract import IOContractCreate, IOContractUpdate, IOContractResponse

router = APIRouter(prefix="/contracts", tags=["I/O Schema Contracts"])


@router.get("", response_model=List[IOContractResponse], summary="List all versioned I/O contracts")
async def list_contracts(
    search: Optional[str] = None,
    status: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
):
    repo = IOContractRepository(db)
    return await repo.get_all(search=search, status=status)


@router.post("", response_model=IOContractResponse, status_code=status.HTTP_201_CREATED, summary="Register an immutable contract version")
async def create_contract(
    data: IOContractCreate,
    db: AsyncSession = Depends(get_db),
):
    repo = IOContractRepository(db)
    existing = await repo.get_by_name_and_version(data.name, data.version)
    if existing:
        raise HTTPException(
            status_code=400,
            detail=f"Contract '{data.name}' version {data.version} already exists. Increment version for updates.",
        )
    return await repo.create(data)


@router.get("/{contract_id}", response_model=IOContractResponse, summary="Get contract by ID or name@version")
async def get_contract(
    contract_id: str,
    db: AsyncSession = Depends(get_db),
):
    repo = IOContractRepository(db)
    
    # Handle slug format: e.g. "research_result@1" or "research_result"
    if "@" in contract_id:
        parts = contract_id.split("@")
        name, ver = parts[0], int(parts[1]) if parts[1].isdigit() else 1
        ctr = await repo.get_by_name_and_version(name, ver)
    else:
        ctr = await repo.get_by_id(contract_id)
        if not ctr:
            # Fallback to latest version by name
            ctr = await repo.get_latest_version(contract_id)

    if not ctr:
        raise HTTPException(status_code=404, detail=f"Contract '{contract_id}' not found.")
    return ctr


@router.put("/{contract_id}", response_model=IOContractResponse, summary="Update contract metadata")
async def update_contract(
    contract_id: str,
    data: IOContractUpdate,
    db: AsyncSession = Depends(get_db),
):
    repo = IOContractRepository(db)
    updated = await repo.update(contract_id, data)
    if not updated:
        raise HTTPException(status_code=404, detail=f"Contract '{contract_id}' not found.")
    return updated


@router.delete("/{contract_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Delete a contract draft")
async def delete_contract(
    contract_id: str,
    db: AsyncSession = Depends(get_db),
):
    repo = IOContractRepository(db)
    deleted = await repo.delete(contract_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Contract '{contract_id}' not found.")
    return None

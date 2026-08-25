from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, or_, and_, desc
from datetime import datetime, timezone
import time
import secrets
from app.models.io_contract import IOContractModel
from app.schemas.io_contract import IOContractCreate, IOContractUpdate, IOContractResponse


def model_to_response(model: IOContractModel) -> IOContractResponse:
    return IOContractResponse(
        id=model.id,
        name=model.name,
        version=model.version,
        displayName=model.display_name,
        description=model.description,
        schema=model.schema or {},
        status=model.status,
        createdAt=model.created_at.isoformat() if model.created_at else datetime.now(timezone.utc).isoformat(),
        updatedAt=model.updated_at.isoformat() if model.updated_at else datetime.now(timezone.utc).isoformat(),
    )


class IOContractRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_all(
        self,
        search: Optional[str] = None,
        status: Optional[str] = None,
    ) -> List[IOContractResponse]:
        query = select(IOContractModel).order_by(IOContractModel.name.asc(), IOContractModel.version.desc())

        if search:
            search_pattern = f"%{search.lower()}%"
            query = query.where(
                or_(
                    IOContractModel.name.ilike(search_pattern),
                    IOContractModel.display_name.ilike(search_pattern),
                    IOContractModel.description.ilike(search_pattern),
                )
            )
        if status:
            query = query.where(IOContractModel.status == status)

        result = await self.db.execute(query)
        models = result.scalars().all()
        return [model_to_response(m) for m in models]

    async def get_by_id(self, contract_id: str) -> Optional[IOContractResponse]:
        query = select(IOContractModel).where(IOContractModel.id == contract_id)
        result = await self.db.execute(query)
        model = result.scalar_one_or_none()
        return model_to_response(model) if model else None

    async def get_by_name_and_version(self, name: str, version: int = 1) -> Optional[IOContractResponse]:
        query = select(IOContractModel).where(
            and_(IOContractModel.name == name, IOContractModel.version == version)
        )
        result = await self.db.execute(query)
        model = result.scalar_one_or_none()
        return model_to_response(model) if model else None

    async def get_latest_version(self, name: str) -> Optional[IOContractResponse]:
        query = (
            select(IOContractModel)
            .where(IOContractModel.name == name)
            .order_by(IOContractModel.version.desc())
            .limit(1)
        )
        result = await self.db.execute(query)
        model = result.scalar_one_or_none()
        return model_to_response(model) if model else None

    async def create(self, data: IOContractCreate) -> IOContractResponse:
        contract_id = data.id or f"ctr_{int(time.time() * 1000)}_{secrets.token_hex(3)}"
        now = datetime.now(timezone.utc)

        model = IOContractModel(
            id=contract_id,
            name=data.name,
            version=data.version,
            display_name=data.displayName,
            description=data.description,
            schema=data.schema_,
            status=data.status,
            created_at=now,
            updated_at=now,
        )

        self.db.add(model)
        await self.db.commit()
        await self.db.refresh(model)
        return model_to_response(model)

    async def update(self, contract_id: str, data: IOContractUpdate) -> Optional[IOContractResponse]:
        query = select(IOContractModel).where(IOContractModel.id == contract_id)
        result = await self.db.execute(query)
        model = result.scalar_one_or_none()

        if not model:
            return None

        if data.displayName is not None:
            model.display_name = data.displayName
        if data.description is not None:
            model.description = data.description
        if data.schema_ is not None:
            model.schema = data.schema_
        if data.status is not None:
            model.status = data.status

        model.updated_at = datetime.now(timezone.utc)
        await self.db.commit()
        await self.db.refresh(model)
        return model_to_response(model)

    async def delete(self, contract_id: str) -> bool:
        query = select(IOContractModel).where(IOContractModel.id == contract_id)
        result = await self.db.execute(query)
        model = result.scalar_one_or_none()
        if not model:
            return False

        await self.db.delete(model)
        await self.db.commit()
        return True

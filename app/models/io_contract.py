from sqlalchemy import Column, String, Integer, JSON, DateTime, Text, UniqueConstraint
from datetime import datetime, timezone
from app.database import Base


class IOContractModel(Base):
    __tablename__ = "io_contracts"

    id = Column(String, primary_key=True, index=True)          # e.g. ctr_1787642866_a1b2c3
    name = Column(String, index=True, nullable=False)          # e.g. research_result
    version = Column(Integer, default=1, nullable=False)       # 1, 2, 3...
    display_name = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    schema = Column(JSON, nullable=False)                      # Standard JSON Schema Draft-07 Object
    status = Column(String, default="PUBLISHED", index=True)   # DRAFT, PUBLISHED, DEPRECATED
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        UniqueConstraint("name", "version", name="uq_contract_name_version"),
    )

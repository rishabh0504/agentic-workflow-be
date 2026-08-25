from sqlalchemy import Column, String, Text, Integer, DateTime
from sqlalchemy.dialects.postgresql import JSONB
from datetime import datetime, timezone
from app.database import Base


class AgentModel(Base):
    __tablename__ = "agents"

    id = Column(String(128), primary_key=True, index=True)
    name = Column(String(128), unique=True, index=True, nullable=False)
    display_name = Column(String(256), nullable=False)
    description = Column(Text, nullable=False, default="")

    model = Column(
        JSONB,
        nullable=False,
        default=lambda: {"providerId": "openai", "model": "gpt-4o", "temperature": 0.3},
    )

    instructions = Column(Text, nullable=False, default="")

    tool_ids = Column(JSONB, nullable=False, default=list)

    input_schema = Column(JSONB, nullable=True)
    output_schema = Column(JSONB, nullable=True)

    runtime = Column(
        JSONB,
        nullable=False,
        default=lambda: {"maxTurns": 10, "timeoutMs": 60000},
    )

    status = Column(String(32), nullable=False, default="active")  # draft, active, disabled
    version = Column(Integer, nullable=False, default=1)

    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

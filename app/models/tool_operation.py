from sqlalchemy import Column, String, Text, Boolean, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
from app.database import Base


class ToolOperationModel(Base):
    __tablename__ = "tool_operations"

    id = Column(String(128), primary_key=True, index=True)
    tool_id = Column(String(128), ForeignKey("tools.id", ondelete="CASCADE"), nullable=False, index=True)

    name = Column(String(128), nullable=False)
    display_name = Column(String(256), nullable=False)
    description = Column(Text, nullable=False, default="")

    input_schema = Column(
        JSONB,
        nullable=False,
        default=lambda: {"type": "object", "properties": {}},
    )
    output_schema = Column(JSONB, nullable=True)

    implementation = Column(JSONB, nullable=False, default=dict)

    classification = Column(
        JSONB,
        nullable=False,
        default=lambda: {"operation": "read", "requiresApproval": False},
    )

    runtime = Column(
        JSONB,
        nullable=False,
        default=lambda: {"timeoutMs": 30000},
    )

    enabled = Column(Boolean, nullable=False, default=True)

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

    # Relationship to Parent ToolModel
    tool = relationship("ToolModel", back_populates="operations")

    __table_args__ = (
        UniqueConstraint("tool_id", "name", name="uq_tool_operation_name"),
    )

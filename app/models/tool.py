from sqlalchemy import Column, String, Text, Integer, DateTime
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
from app.database import Base


class ToolModel(Base):
    __tablename__ = "tools"

    id = Column(String(128), primary_key=True, index=True)
    name = Column(String(128), unique=True, index=True, nullable=False)
    display_name = Column(String(256), nullable=False)
    description = Column(Text, nullable=False, default="")

    category = Column(String(32), nullable=False, default="external")  # native | external
    kind = Column(String(32), nullable=False)  # native | http | sql | mcp | custom

    status = Column(String(32), nullable=False, default="active")  # draft | active | disabled
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

    # 1:N Relationship to ToolOperationModel
    operations = relationship(
        "ToolOperationModel",
        back_populates="tool",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

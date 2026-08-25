from sqlalchemy import Column, String, Text, Integer, Float, DateTime
from sqlalchemy.dialects.postgresql import JSONB
from datetime import datetime, timezone
import uuid
from app.database import Base


class AgentRunModel(Base):
    __tablename__ = "agent_runs"

    id = Column(String(128), primary_key=True, index=True, default=lambda: f"run_{uuid.uuid4().hex[:12]}")
    agent_id = Column(String(128), nullable=False, index=True)
    workflow_run_id = Column(String(128), nullable=True, index=True)
    status = Column(String(32), nullable=False, default="running")  # running, completed, failed, limit_exceeded
    turns_executed = Column(Integer, nullable=False, default=0)
    prompt = Column(Text, nullable=False, default="")
    final_output = Column(JSONB, nullable=True)
    error = Column(Text, nullable=True)
    duration_ms = Column(Float, nullable=False, default=0.0)

    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    completed_at = Column(
        DateTime(timezone=True),
        nullable=True,
    )


class AgentRunEventModel(Base):
    __tablename__ = "agent_run_events"

    id = Column(String(128), primary_key=True, index=True, default=lambda: f"evt_{uuid.uuid4().hex[:12]}")
    agent_run_id = Column(String(128), nullable=False, index=True)
    turn = Column(Integer, nullable=False, default=1)
    event_type = Column(String(64), nullable=False)  # turn.started, tool.executed, turn.completed, agent.completed, agent.failed
    payload = Column(JSONB, nullable=False, default=dict)

    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

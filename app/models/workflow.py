from sqlalchemy import Column, String, Integer, Float, Boolean, JSON, DateTime, ForeignKey, Index, Text
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
from app.database import Base


class WorkflowModel(Base):
    __tablename__ = "workflows"

    id = Column(String, primary_key=True, index=True)
    name = Column(String, unique=True, index=True, nullable=False)
    display_name = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    category = Column(String, default="custom", index=True)  # podcast, research, customer_support
    status = Column(String, default="DRAFT", index=True)     # DRAFT, PUBLISHED, ARCHIVED
    current_version_id = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    versions = relationship("WorkflowVersionModel", back_populates="workflow", cascade="all, delete-orphan", lazy="selectin")
    runs = relationship("WorkflowRunModel", back_populates="workflow", cascade="all, delete-orphan", lazy="selectin")


class WorkflowVersionModel(Base):
    __tablename__ = "workflow_versions"

    id = Column(String, primary_key=True, index=True)
    workflow_id = Column(String, ForeignKey("workflows.id", ondelete="CASCADE"), nullable=False, index=True)
    version = Column(Integer, nullable=False)
    status = Column(String, default="DRAFT", index=True)     # DRAFT, PUBLISHED, ARCHIVED
    nodes = Column(JSON, default=list)                      # Canvas ReactFlow nodes
    edges = Column(JSON, default=list)                      # Canvas ReactFlow edges
    variables = Column(JSON, default=dict)                  # Workflow runtime variables
    input_schema = Column(JSON, nullable=True)
    output_schema = Column(JSON, nullable=True)
    viewport = Column(JSON, default=dict)                   # Editor zoom / pan coordinates
    changelog = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), index=True)

    workflow = relationship("WorkflowModel", back_populates="versions")
    runs = relationship("WorkflowRunModel", back_populates="version", cascade="all, delete-orphan")


class WorkflowRunModel(Base):
    __tablename__ = "workflow_runs"

    id = Column(String, primary_key=True, index=True)
    workflow_id = Column(String, ForeignKey("workflows.id", ondelete="CASCADE"), nullable=False, index=True)
    workflow_version_id = Column(String, ForeignKey("workflow_versions.id", ondelete="CASCADE"), nullable=False, index=True)
    status = Column(String, default="running", index=True)   # running, completed, failed
    input_payload = Column(JSON, nullable=True)
    final_output = Column(JSON, nullable=True)
    duration_ms = Column(Float, default=0.0)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), index=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)

    workflow = relationship("WorkflowModel", back_populates="runs")
    version = relationship("WorkflowVersionModel", back_populates="runs")
    node_runs = relationship("WorkflowNodeRunModel", back_populates="workflow_run", cascade="all, delete-orphan", lazy="selectin")


class WorkflowNodeRunModel(Base):
    __tablename__ = "workflow_node_runs"

    id = Column(String, primary_key=True, index=True)
    workflow_run_id = Column(String, ForeignKey("workflow_runs.id", ondelete="CASCADE"), nullable=False, index=True)
    node_id = Column(String, nullable=False, index=True)
    node_type = Column(String, nullable=False, index=True)
    status = Column(String, nullable=False)                 # running, success, failed
    input_payload = Column(JSON, nullable=True)
    output_payload = Column(JSON, nullable=True)
    error = Column(Text, nullable=True)
    retry_count = Column(Integer, default=0)
    duration_ms = Column(Float, default=0.0)
    started_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    completed_at = Column(DateTime(timezone=True), nullable=True)

    workflow_run = relationship("WorkflowRunModel", back_populates="node_runs")

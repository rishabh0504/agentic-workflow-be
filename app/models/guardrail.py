from sqlalchemy import Column, String, Integer, Float, Boolean, JSON, DateTime, ForeignKey, Index
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
from app.database import Base


class GuardrailModel(Base):
    __tablename__ = "guardrails"

    id = Column(String, primary_key=True, index=True)
    name = Column(String, unique=True, index=True, nullable=False)
    display_name = Column(String, nullable=False)
    description = Column(String, nullable=True)
    category = Column(String, default="custom", index=True)  # input, grounding, safety, output_quality
    execution_mode = Column(String, default="validator")     # validator, transformer, llm_validator, rule_engine, hybrid
    default_action = Column(String, default="BLOCK")         # ALLOW, WARN, RETRY, BLOCK, REWRITE, FALLBACK
    status = Column(String, default="active", index=True)   # active, inactive, draft
    config = Column(JSON, default=dict)
    version = Column(Integer, default=1)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    rules = relationship("GuardrailRuleModel", back_populates="guardrail", cascade="all, delete-orphan", lazy="selectin")
    bindings = relationship("GuardrailBindingModel", back_populates="guardrail", cascade="all, delete-orphan", lazy="selectin")


class GuardrailRuleModel(Base):
    __tablename__ = "guardrail_rules"

    id = Column(String, primary_key=True, index=True)
    guardrail_id = Column(String, ForeignKey("guardrails.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String, nullable=False)
    rule_type = Column(String, nullable=False)  # regex, fact_reference, json_schema, keyword_blacklist, llm_eval
    operator = Column(String, default="matches") # matches, not_matches, contains, greater_than, equal
    config = Column(JSON, default=dict)
    severity = Column(String, default="ERROR")   # INFO, WARNING, ERROR, CRITICAL
    enabled = Column(Boolean, default=True)
    order_index = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    guardrail = relationship("GuardrailModel", back_populates="rules")


class GuardrailBindingModel(Base):
    __tablename__ = "guardrail_bindings"

    id = Column(String, primary_key=True, index=True)
    guardrail_id = Column(String, ForeignKey("guardrails.id", ondelete="CASCADE"), nullable=False, index=True)
    workflow_id = Column(String, nullable=True, index=True)
    node_id = Column(String, nullable=True, index=True)
    scope = Column(String, nullable=False, index=True)  # WORKFLOW_INPUT, AGENT_INPUT, AGENT_OUTPUT, TOOL_INPUT, TOOL_OUTPUT, RAG_OUTPUT, NODE_OUTPUT, WORKFLOW_OUTPUT
    priority = Column(Integer, default=10)
    enabled = Column(Boolean, default=True)
    action_override = Column(String, nullable=True)     # ALLOW, WARN, RETRY, BLOCK, REWRITE, FALLBACK
    config_override = Column(JSON, default=dict)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    guardrail = relationship("GuardrailModel", back_populates="bindings")


class GuardrailExecutionModel(Base):
    __tablename__ = "guardrail_executions"

    id = Column(String, primary_key=True, index=True)
    guardrail_id = Column(String, ForeignKey("guardrails.id", ondelete="SET NULL"), nullable=True, index=True)
    binding_id = Column(String, nullable=True, index=True)
    workflow_run_id = Column(String, nullable=True, index=True)
    agent_run_id = Column(String, nullable=True, index=True)
    scope = Column(String, nullable=False)
    status = Column(String, nullable=False)             # PASSED, FAILED, WARNING, REWRITTEN
    action_taken = Column(String, nullable=False)       # ALLOW, WARN, RETRY, BLOCK, REWRITE, FALLBACK
    score = Column(Float, default=1.0)
    payload_hash = Column(String, nullable=True)
    input_preview = Column(String, nullable=True)       # Redacted preview for audit
    violations = Column(JSON, default=list)             # Standardized violations array
    output_payload = Column(JSON, nullable=True)        # Sanitized/transformed payload if transformer
    duration_ms = Column(Float, default=0.0)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), index=True)

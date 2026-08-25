from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional, Literal


class NormalizedFact(BaseModel):
    id: str  # e.g. "FACT_001"
    claim: str
    normalized_value: Optional[float] = None
    display_value: str
    unit: Optional[str] = None
    metric_type: str  # e.g. "transaction_value", "yield", "price_per_sqft"
    period: str       # e.g. "H1 2026", "2025"
    location: str     # e.g. "Dubai", "Palm Jebel Ali", "Dubai Hills"
    source_url: str
    source_title: str
    source_passage: str
    confidence: float = 0.95
    verification_status: Literal["VERIFIED", "UNVERIFIED", "REJECTED"] = "VERIFIED"


class FactCatalog(BaseModel):
    market_summary: str
    facts: List[NormalizedFact] = Field(default_factory=list)


# --- Guardrail Execution Schemas ---

class GuardrailViolation(BaseModel):
    rule_id: Optional[str] = None
    severity: Literal["INFO", "WARNING", "ERROR", "CRITICAL"] = "ERROR"
    type: Literal["UNSUPPORTED_CLAIM", "CONTRADICTED_CLAIM", "GEOGRAPHIC_MISMATCH", "PII_LEAK", "MARKUP_LEAKAGE", "SCHEMA_VIOLATION", "CUSTOM"]
    message: str
    location: Optional[Dict[str, Any]] = None
    claim: Optional[str] = None
    fact_id: Optional[str] = None
    suggested_fix: Optional[str] = None


class GuardrailResult(BaseModel):
    status: Literal["PASSED", "FAILED", "WARNING", "REWRITTEN"]
    action: Literal["ALLOW", "WARN", "BLOCK", "REWRITE", "RETRY", "FALLBACK"]
    score: float = 1.0
    violations: List[GuardrailViolation] = Field(default_factory=list)
    output_payload: Optional[Any] = None
    duration_ms: float = 0.0
    metadata: Dict[str, Any] = Field(default_factory=dict)


# --- Guardrail Configuration Schemas ---

class GuardrailRuleCreate(BaseModel):
    name: str
    ruleType: str
    operator: str = "matches"
    config: Dict[str, Any] = Field(default_factory=dict)
    severity: str = "ERROR"
    enabled: bool = True
    orderIndex: int = 0


class GuardrailRuleResponse(BaseModel):
    id: str
    guardrailId: str
    name: str
    ruleType: str
    operator: str
    config: Dict[str, Any]
    severity: str
    enabled: bool
    orderIndex: int
    createdAt: str


class GuardrailCreate(BaseModel):
    name: str
    displayName: str
    description: Optional[str] = None
    category: str = "grounding"
    executionMode: str = "validator"
    defaultAction: str = "BLOCK"
    status: str = "active"
    config: Dict[str, Any] = Field(default_factory=dict)
    rules: List[GuardrailRuleCreate] = Field(default_factory=list)


class GuardrailResponse(BaseModel):
    id: str
    name: str
    displayName: str
    description: Optional[str] = None
    category: str
    executionMode: str
    defaultAction: str
    status: str
    config: Dict[str, Any]
    rules: List[GuardrailRuleResponse] = Field(default_factory=list)
    version: int
    createdAt: str
    updatedAt: str

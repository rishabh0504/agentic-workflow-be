from typing import Optional, List, Dict, Any, Union
from pydantic import BaseModel, Field


class SchemaPropertyValidationError(BaseModel):
    path: str
    expected: str
    actual: str
    message: str


class ContractValidationResult(BaseModel):
    is_valid: bool
    contract_name: Optional[str] = None
    contract_version: Optional[int] = None
    errors: List[SchemaPropertyValidationError] = Field(default_factory=list)


class CompatibilityResult(BaseModel):
    is_compatible: bool
    reason: Optional[str] = None
    missing_fields: List[str] = Field(default_factory=list)
    type_mismatches: List[Dict[str, str]] = Field(default_factory=list)


class ResolvedInputPayload(BaseModel):
    payload: Dict[str, Any]
    mode: str = "DIRECT"  # DIRECT, MAPPED
    source_nodes: List[str] = Field(default_factory=list)

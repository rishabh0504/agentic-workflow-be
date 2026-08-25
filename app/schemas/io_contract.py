from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, Dict, Any, List, Literal


ContractStatus = Literal["DRAFT", "PUBLISHED", "DEPRECATED"]


class IOContractBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=128, pattern=r"^[a-zA-Z0-9_-]+$")
    version: int = Field(default=1, ge=1)
    displayName: str = Field(..., min_length=1, max_length=256)
    description: Optional[str] = Field(default="")
    schema_: Dict[str, Any] = Field(..., alias="schema")
    status: ContractStatus = "PUBLISHED"

    model_config = ConfigDict(populate_by_name=True)


class IOContractCreate(IOContractBase):
    id: Optional[str] = None


class IOContractUpdate(BaseModel):
    displayName: Optional[str] = None
    description: Optional[str] = None
    schema_: Optional[Dict[str, Any]] = Field(None, alias="schema")
    status: Optional[ContractStatus] = None

    model_config = ConfigDict(populate_by_name=True)


class IOContractResponse(IOContractBase):
    id: str
    createdAt: str
    updatedAt: str

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

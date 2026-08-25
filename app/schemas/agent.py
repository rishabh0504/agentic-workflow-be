from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, Dict, Any, List, Literal


AgentStatus = Literal["draft", "active", "disabled"]


class AgentModelConfig(BaseModel):
    providerId: str = "openai"
    model: str = "gpt-4o"
    temperature: Optional[float] = Field(default=0.3, ge=0.0, le=2.0)


class AgentRuntimeConfig(BaseModel):
    maxTurns: int = Field(default=10, ge=1, le=100)
    timeoutMs: int = Field(default=60000, ge=1000, le=600000)


class AgentBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=128, pattern=r"^[a-zA-Z0-9_-]+$")
    displayName: str = Field(..., min_length=1, max_length=256)
    description: str = Field(default="")

    model: AgentModelConfig = Field(default_factory=AgentModelConfig)
    instructions: str = Field(default="")

    toolIds: List[str] = Field(default_factory=list)

    inputSchema: Optional[Dict[str, Any]] = None
    outputSchema: Optional[Dict[str, Any]] = None

    runtime: AgentRuntimeConfig = Field(default_factory=AgentRuntimeConfig)
    status: AgentStatus = "active"
    version: int = Field(default=1, ge=1)


class AgentCreate(AgentBase):
    id: Optional[str] = None


class AgentUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=128, pattern=r"^[a-zA-Z0-9_-]+$")
    displayName: Optional[str] = Field(None, min_length=1, max_length=256)
    description: Optional[str] = None
    model: Optional[AgentModelConfig] = None
    instructions: Optional[str] = None
    toolIds: Optional[List[str]] = None
    inputSchema: Optional[Dict[str, Any]] = None
    outputSchema: Optional[Dict[str, Any]] = None
    runtime: Optional[AgentRuntimeConfig] = None
    status: Optional[AgentStatus] = None
    version: Optional[int] = Field(None, ge=1)


class AgentResponse(AgentBase):
    id: str
    createdAt: str
    updatedAt: str

    model_config = ConfigDict(from_attributes=True)

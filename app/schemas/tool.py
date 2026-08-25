from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, Dict, Any, List, Literal, Union


ToolCategory = Literal["native", "external"]
ToolKind = Literal["native", "http", "sql", "mcp", "custom"]
ToolStatus = Literal["draft", "active", "disabled"]
OperationClassificationType = Literal["read", "write", "delete"]
ToolRunStatus = Literal[
    "success",
    "input_validation_error",
    "output_validation_error",
    "execution_error",
    "timeout",
]


# ------------------------------------------
# Operation Classifications & Runtimes
# ------------------------------------------

class ToolClassification(BaseModel):
    operation: OperationClassificationType = "read"
    requiresApproval: bool = False


class ToolRuntimeConfig(BaseModel):
    timeoutMs: int = Field(default=30000, ge=100, le=600000)


# ------------------------------------------
# Implementation Discriminated Union
# ------------------------------------------

class NativeImplementation(BaseModel):
    type: Literal["native"] = "native"
    handler: str
    config: Optional[Dict[str, Any]] = None


class HttpImplementation(BaseModel):
    type: Literal["http"] = "http"
    integrationId: Optional[str] = None
    method: Literal["GET", "POST", "PUT", "PATCH", "DELETE"] = "POST"
    url: str
    headers: Optional[Dict[str, str]] = None
    query: Optional[Dict[str, str]] = None
    body: Optional[Any] = None


class SqlImplementation(BaseModel):
    type: Literal["sql"] = "sql"
    integrationId: str
    query: str
    parameters: Optional[Dict[str, str]] = None


class McpImplementation(BaseModel):
    type: Literal["mcp"] = "mcp"
    serverId: str
    toolName: str
    argumentMapping: Optional[Dict[str, str]] = None


class CustomImplementation(BaseModel):
    type: Literal["custom"] = "custom"
    handler: str


ToolImplementationUnion = Union[
    NativeImplementation,
    HttpImplementation,
    SqlImplementation,
    McpImplementation,
    CustomImplementation,
]


# ------------------------------------------
# Tool Operation Schemas
# ------------------------------------------

class ToolOperationBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=128, pattern=r"^[a-zA-Z0-9_-]+$")
    displayName: str = Field(..., min_length=1, max_length=256)
    description: str = Field(default="")

    inputSchema: Dict[str, Any] = Field(default_factory=lambda: {"type": "object", "properties": {}})
    outputSchema: Optional[Dict[str, Any]] = None

    implementation: Dict[str, Any] = Field(default_factory=dict)
    classification: ToolClassification = Field(default_factory=ToolClassification)
    runtime: ToolRuntimeConfig = Field(default_factory=ToolRuntimeConfig)
    enabled: bool = True


class ToolOperationCreate(ToolOperationBase):
    id: Optional[str] = None


class ToolOperationUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=128, pattern=r"^[a-zA-Z0-9_-]+$")
    displayName: Optional[str] = Field(None, min_length=1, max_length=256)
    description: Optional[str] = None
    inputSchema: Optional[Dict[str, Any]] = None
    outputSchema: Optional[Dict[str, Any]] = None
    implementation: Optional[Dict[str, Any]] = None
    classification: Optional[ToolClassification] = None
    runtime: Optional[ToolRuntimeConfig] = None
    enabled: Optional[bool] = None


class ToolOperationResponse(ToolOperationBase):
    id: str
    toolId: str
    createdAt: str
    updatedAt: str

    model_config = ConfigDict(from_attributes=True)


# ------------------------------------------
# Tool Container Schemas
# ------------------------------------------

class ToolBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=128, pattern=r"^[a-zA-Z0-9_-]+$")
    displayName: str = Field(..., min_length=1, max_length=256)
    description: Optional[str] = ""
    category: ToolCategory = "external"
    kind: ToolKind = "http"
    status: ToolStatus = "active"
    version: int = Field(default=1, ge=1)


class ToolCreate(ToolBase):
    id: Optional[str] = None
    operations: Optional[List[ToolOperationCreate]] = None


class ToolUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=128, pattern=r"^[a-zA-Z0-9_-]+$")
    displayName: Optional[str] = Field(None, min_length=1, max_length=256)
    description: Optional[str] = None
    category: Optional[ToolCategory] = None
    kind: Optional[ToolKind] = None
    status: Optional[ToolStatus] = None
    version: Optional[int] = Field(None, ge=1)


class ToolResponse(ToolBase):
    id: str
    operations: List[ToolOperationResponse] = Field(default_factory=list)
    createdAt: str
    updatedAt: str

    model_config = ConfigDict(from_attributes=True)


# ------------------------------------------
# Execution Request & Response
# ------------------------------------------

class ToolExecuteRequest(BaseModel):
    input: Dict[str, Any] = Field(default_factory=dict)
    context: Optional[Dict[str, Any]] = None


class ToolRunResult(BaseModel):
    id: str
    toolId: str
    operationId: str
    status: ToolRunStatus
    input: Any
    output: Optional[Any] = None
    error: Optional[str] = None
    inputValid: bool
    outputValid: Optional[bool] = None
    durationMs: float
    executedAt: str


class WebSearchResult(BaseModel):
    title: str
    url: str
    snippet: str

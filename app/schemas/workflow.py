from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional, Literal


class WorkflowVersionCreate(BaseModel):
    nodes: List[Dict[str, Any]] = Field(default_factory=list)
    edges: List[Dict[str, Any]] = Field(default_factory=list)
    variables: Dict[str, Any] = Field(default_factory=dict)
    inputSchema: Optional[Dict[str, Any]] = None
    outputSchema: Optional[Dict[str, Any]] = None
    viewport: Dict[str, Any] = Field(default_factory=lambda: {"x": 0, "y": 0, "zoom": 1})
    changelog: Optional[str] = None


class WorkflowVersionResponse(BaseModel):
    id: str
    workflowId: str
    version: int
    status: str
    nodes: List[Dict[str, Any]]
    edges: List[Dict[str, Any]]
    variables: Dict[str, Any]
    inputSchema: Optional[Dict[str, Any]] = None
    outputSchema: Optional[Dict[str, Any]] = None
    viewport: Dict[str, Any]
    changelog: Optional[str] = None
    createdAt: str


class WorkflowCreate(BaseModel):
    name: str
    displayName: str
    description: Optional[str] = None
    category: str = "custom"
    status: str = "DRAFT"
    initialVersion: Optional[WorkflowVersionCreate] = None


class WorkflowUpdate(BaseModel):
    displayName: Optional[str] = None
    description: Optional[str] = None
    category: Optional[str] = None
    status: Optional[str] = None
    versionData: Optional[WorkflowVersionCreate] = None


class WorkflowResponse(BaseModel):
    id: str
    name: str
    displayName: str
    description: Optional[str] = None
    category: str
    status: str
    currentVersionId: Optional[str] = None
    activeVersion: Optional[WorkflowVersionResponse] = None
    createdAt: str
    updatedAt: str


class WorkflowRunCreate(BaseModel):
    inputPayload: Optional[Dict[str, Any]] = Field(default_factory=dict)
    versionId: Optional[str] = None


class WorkflowNodeRunResponse(BaseModel):
    id: str
    nodeId: str
    nodeType: str
    status: str
    inputPayload: Optional[Any] = None
    outputPayload: Optional[Any] = None
    error: Optional[str] = None
    retryCount: int = 0
    durationMs: float = 0.0
    startedAt: str
    completedAt: Optional[str] = None


class WorkflowRunResponse(BaseModel):
    id: str
    workflowId: str
    workflowVersionId: str
    status: str
    inputPayload: Optional[Any] = None
    finalOutput: Optional[Any] = None
    durationMs: float = 0.0
    nodeRuns: List[WorkflowNodeRunResponse] = Field(default_factory=list)
    createdAt: str
    completedAt: Optional[str] = None

from pydantic import BaseModel, Field
from typing import Optional, Any, List, Dict
from datetime import datetime


class ProviderOut(BaseModel):
    id: str
    name: str
    display_name: str
    kind: str
    base_url: Optional[str] = None
    auth_type: str
    enabled: bool
    health: str
    last_checked: Optional[datetime] = None
    metadata_json: Dict[str, Any] = {}

    class Config:
        from_attributes = True


class ModelOut(BaseModel):
    id: str
    provider_name: str
    model_id: str
    display_name: Optional[str] = None
    category: str
    context_window: int
    supports_tools: bool
    supports_vision: bool
    is_local: bool
    estimated_cost_input: float
    estimated_cost_output: float
    health: str
    available: bool
    quota_remaining: Optional[str] = None
    metadata_json: Dict[str, Any] = {}

    class Config:
        from_attributes = True


class TaskCreate(BaseModel):
    title: str
    objective: str
    project_name: Optional[str] = None
    project_dir: Optional[str] = None
    optimization_mode: str = "balanced"
    auto_route: bool = True
    manual_model: Optional[str] = None


class TaskOut(BaseModel):
    id: str
    title: str
    objective: str
    project_name: Optional[str] = None
    project_dir: Optional[str] = None
    status: str
    current_model: Optional[str] = None
    previous_model: Optional[str] = None
    optimization_mode: str
    auto_route: bool
    plan_json: List[Any] = []
    result_summary: Optional[str] = None
    error: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class CheckpointOut(BaseModel):
    id: str
    task_id: str
    label: str
    state_json: Dict[str, Any] = {}
    files_modified: List[Any] = []
    tests_json: Dict[str, Any] = {}
    completed_work: List[Any] = []
    pending_work: List[Any] = []
    handoff_summary: Optional[str] = None
    current_model: Optional[str] = None
    previous_model: Optional[str] = None
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class OptimizeRequest(BaseModel):
    prompt: str
    mode: str = "balanced"
    model: Optional[str] = None
    task_type: Optional[str] = None


class OptimizeResult(BaseModel):
    original: str
    optimized: str
    mode: str
    original_tokens_est: int
    optimized_tokens_est: int
    savings_pct: float
    notes: List[str] = []


class RouteRequest(BaseModel):
    task: str
    task_type: Optional[str] = None
    manual_model: Optional[str] = None


class RouteResult(BaseModel):
    selected_model: str
    provider: str
    reason: str
    task_type: str
    candidates: List[Dict[str, Any]] = []


class UsageSummary(BaseModel):
    total_input_tokens: int
    total_output_tokens: int
    total_cost: float
    by_provider: List[Dict[str, Any]]
    by_model: List[Dict[str, Any]]


class ApprovalOut(BaseModel):
    id: str
    task_id: Optional[str] = None
    action: str
    details: Optional[str] = None
    status: str
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class SessionCreate(BaseModel):
    title: Optional[str] = None
    project_name: Optional[str] = None
    project_dir: Optional[str] = None
    provider_name: Optional[str] = None
    model_id: Optional[str] = None


class SessionOut(BaseModel):
    id: str
    title: Optional[str] = None
    project_name: Optional[str] = None
    project_dir: Optional[str] = None
    provider_name: Optional[str] = None
    model_id: Optional[str] = None
    status: str
    message_count: int
    input_tokens: int
    output_tokens: int
    estimated_cost: float
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    last_active: Optional[datetime] = None

    class Config:
        from_attributes = True


class MessageOut(BaseModel):
    id: str
    session_id: str
    role: str
    content: str
    model_id: Optional[str] = None
    provider_name: Optional[str] = None
    input_tokens: int = 0
    output_tokens: int = 0
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True

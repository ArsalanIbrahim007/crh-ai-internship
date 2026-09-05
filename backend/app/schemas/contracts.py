from typing import Any, Literal

from pydantic import BaseModel, Field


class KPI(BaseModel):
    key: str
    label: str
    value: float | int | str
    unit: str | None = None
    delta: float | None = None


class ChartSpec(BaseModel):
    type: Literal["line", "bar", "area", "pie", "table", "none"] = "none"
    title: str = ""
    x_key: str | None = None
    y_keys: list[str] = Field(default_factory=list)
    rows: list[dict[str, Any]] = Field(default_factory=list)


class SourceRef(BaseModel):
    source_id: str
    title: str
    location: str | None = None
    snippet: str | None = None


class ToolCall(BaseModel):
    tool_name: str
    arguments: dict[str, Any]
    status: Literal["proposed", "approved", "executed", "failed"]


class ChatRequest(BaseModel):
    conversation_id: str | None = None
    query_text: str
    attachment_ids: list[str] = Field(default_factory=list)
    voice_mode: bool = False


class ChatResponse(BaseModel):
    request_id: str
    conversation_id: str
    message_id: str
    answer: str
    intent: str
    kpis: list[KPI] = Field(default_factory=list)
    chart_spec: ChartSpec = Field(default_factory=ChartSpec)
    insights: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    forecast: dict[str, Any] | None = None
    sources: list[SourceRef] = Field(default_factory=list)
    tool_calls: list[ToolCall] = Field(default_factory=list)
    requires_approval: bool = False
    suggested_questions: list[str] = Field(default_factory=list)
    error: dict[str, Any] | None = None

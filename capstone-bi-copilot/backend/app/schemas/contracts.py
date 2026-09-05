from typing import Any, Literal
from datetime import datetime
from pydantic import BaseModel, Field
class KPI(BaseModel):
    key:str; label:str; value:float|int|str; unit:str|None=None; delta:float|None=None
class ChartSpec(BaseModel):
    type:Literal["line","bar","area","pie","table","none"]="none"; title:str=""; x_key:str|None=None; y_keys:list[str]=Field(default_factory=list); rows:list[dict[str,Any]]=Field(default_factory=list)
class SourceRef(BaseModel):
    source_id:str; title:str; location:str|None=None; snippet:str|None=None; score:float|None=None
class ToolCall(BaseModel):
    tool_name:str; arguments:dict[str,Any]=Field(default_factory=dict); status:Literal["proposed","approved","executed","failed","cancelled"]="proposed"; error:str|None=None
class ChatRequest(BaseModel):
    conversation_id:str|None=None; query_text:str; attachment_ids:list[str]=Field(default_factory=list); voice_mode:bool=False
class ApprovalRequest(BaseModel):
    decision:Literal["approve","cancel"]
class ConversationSummary(BaseModel):
    id:str; title:str; updated_at:datetime; message_count:int
class ConversationMessage(BaseModel):
    id:str; role:Literal["user","assistant"]; content:str; created_at:datetime
class ConversationDetail(BaseModel):
    id:str; title:str; messages:list[ConversationMessage]
class ChatResponse(BaseModel):
    request_id:str; conversation_id:str; message_id:str; answer:str; intent:str
    kpis:list[KPI]=Field(default_factory=list); chart_spec:ChartSpec=Field(default_factory=ChartSpec)
    insights:list[str]=Field(default_factory=list); recommendations:list[str]=Field(default_factory=list)
    forecast:dict[str,Any]|None=None; sources:list[SourceRef]=Field(default_factory=list); tool_calls:list[ToolCall]=Field(default_factory=list)
    requires_approval:bool=False; suggested_questions:list[str]=Field(default_factory=list); error:dict[str,Any]|None=None
class LoginRequest(BaseModel): email:str; password:str
class AuthUser(BaseModel): id:int; email:str; role:str
class AuthResponse(BaseModel): access_token:str; token_type:str="bearer"; user:AuthUser

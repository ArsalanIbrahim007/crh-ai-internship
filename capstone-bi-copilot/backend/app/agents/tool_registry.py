from dataclasses import dataclass
from typing import Any,Awaitable,Callable
@dataclass
class RegisteredTool: name:str; description:str; requires_approval:bool; handler:Callable[...,Awaitable[dict[str,Any]]]|None=None
class ToolRegistry:
    def __init__(self): self._tools={}
    def register(self,t:RegisteredTool): self._tools[t.name]=t
    def get(self,n:str): return self._tools.get(n)
    def list(self): return list(self._tools.values())
tool_registry=ToolRegistry()

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal

from app.agents.tool_registry import RegisteredTool, tool_registry

ToolIntent = Literal[
    "email_search", "email_read", "email_draft", "email_send",
    "calendar_read", "calendar_availability", "calendar_create", "calendar_update", "calendar_delete",
]

@dataclass(frozen=True)
class ToolRoute:
    intent: ToolIntent
    tool_name: str
    provider: Literal["gmail", "google-calendar"]
    requires_approval: bool

_ROUTES = {
    "email_search": ("search_email", "gmail", False),
    "email_read": ("read_email", "gmail", False),
    "email_draft": ("draft_email", "gmail", False),
    "email_send": ("send_email", "gmail", True),
    "calendar_read": ("list_calendar_events", "google-calendar", False),
    "calendar_availability": ("check_calendar_availability", "google-calendar", False),
    "calendar_create": ("create_calendar_event", "google-calendar", True),
    "calendar_update": ("update_calendar_event", "google-calendar", True),
    "calendar_delete": ("delete_calendar_event", "google-calendar", True),
}

for intent, (name, provider, approval) in _ROUTES.items():
    if not tool_registry.get(name):
        tool_registry.register(RegisteredTool(name=name, description=f"{intent} through {provider}", requires_approval=approval))

def classify_tool_intent(query: str) -> ToolRoute | None:
    text = " ".join(query.lower().split())
    # The requested communication verb wins even if its content mentions meetings or calendars.
    if re.search(r"\b(send|write|compose|draft|email|e-mail|reply)\b.*\b(email|e-mail|reply|message)\b", text) \
            or re.match(r"^(send|email|e-mail|write|compose|draft|reply)\b", text):
        intent: ToolIntent = "email_draft" if re.match(r"^(draft|compose|write)\b", text) and "send" not in text else "email_send"
    elif re.search(r"\b(search|find|look for)\b.*\b(email|mail|inbox)\b", text): intent = "email_search"
    elif re.search(r"\b(read|open|show)\b.*\b(email|mail|message)\b", text): intent = "email_read"
    elif re.search(r"\b(am i|i am|i'm|check whether i am|check if i am)\b.*\b(free|available|availability)\b", text): intent = "calendar_availability"
    elif re.search(r"\b(schedule|book|create|add|set up)\b.*\b(meeting|calendar|event)\b", text) or "add this to my calendar" in text: intent = "calendar_create"
    elif re.search(r"\b(update|move|reschedule|change)\b.*\b(meeting|calendar|event)\b", text): intent = "calendar_update"
    elif re.search(r"\b(delete|remove|cancel)\b.*\b(meeting|calendar|event)\b", text): intent = "calendar_delete"
    elif re.search(r"\b(show|list|check|what)\b.*\b(calendar|schedule|events?|meetings?)\b", text): intent = "calendar_read"
    else: return None
    name, provider, approval = _ROUTES[intent]
    return ToolRoute(intent, name, provider, approval)

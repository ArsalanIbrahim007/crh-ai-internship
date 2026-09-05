from __future__ import annotations

import json
import re
from datetime import datetime, timedelta, timezone
from uuid import uuid4
from sqlalchemy.orm import Session
from app.agents.tool_routing import classify_tool_intent
from app.db.models import Conversation, Message, ToolAction
from app.schemas.contracts import ChatRequest, ChatResponse, SourceRef, ToolCall
from app.services.alert_service import alert_service
from app.services.analytics_service import analytics_service
from app.services.briefing_service import briefing_service
from app.services.forecast_service import forecast_service
from app.services.llm_service import llm_service
from app.services.rag_service import rag_service

class Supervisor:
    @staticmethod
    def _time_parts(query: str) -> tuple[int, int, str, bool]:
        match = re.search(r"\b(1[0-2]|0?[1-9])(?::([0-5]\d))?\s*(am|pm)?\b", query, re.I)
        if not match: return 9, 0, "AM", False
        return int(match.group(1)), int(match.group(2) or 0), (match.group(3) or "AM").upper(), bool(match.group(3))

    def calendar_arguments(self, query: str) -> tuple[dict, str | None]:
        email = re.search(r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}", query)
        hour, minute, meridiem, explicit = self._time_parts(query)
        if re.search(r"\b(?:at|from)\s+\d", query, re.I) and not explicit:
            return {}, f"Did you mean {hour}:{minute:02d} AM or {hour}:{minute:02d} PM?"
        date_label = "Tomorrow" if "tomorrow" in query.lower() else "Today"
        day = datetime.now().astimezone().date() + (timedelta(days=1) if date_label == "Tomorrow" else timedelta())
        local_hour = hour + 12 if meridiem == "PM" and hour != 12 else (0 if meridiem == "AM" and hour == 12 else hour)
        start = datetime.combine(day, datetime.min.time()).astimezone().replace(hour=local_hour, minute=minute)
        named = re.search(r"\b(?:titled|called|named)\s+(.+?)(?=\s+(?:with|for|today|tomorrow|at)\b|$)", query, re.I)
        title = named.group(1).strip(" ,.-") if named else re.sub(r"\b(schedule|create|add|book|set up)\b", "", query, flags=re.I)
        title = re.sub(r"\b(a|an)?\s*(calendar\s+)?(meeting|event)\b", "", title, flags=re.I)
        title = re.sub(r"\b(today|tomorrow|at|with|for)\b.*$", "", title, flags=re.I).strip(" ,.-") or "Meeting"
        end = start + timedelta(hours=1)
        return {"meeting_title": title[0].upper() + title[1:], "attendees": email.group(0) if email else "", "date": date_label,
                "start_time": f"{hour}:{minute:02d} {meridiem}", "end_time": end.strftime("%I:%M %p").lstrip("0"),
                "start": start.isoformat(), "end": end.isoformat()}, None

    def email_arguments(self, query: str) -> dict:
        recipient = re.search(r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}", query)
        hour, minute, meridiem, explicit = self._time_parts(query)
        if not explicit and hour <= 7 and "final review" in query.lower(): meridiem = "PM"
        when = f"{hour}:{minute:02d} {meridiem} {'tomorrow' if 'tomorrow' in query.lower() else 'today'}"
        final_review = "final review" in query.lower() or "final project review" in query.lower()
        subject = "Final Project Review Meeting" if final_review else "Meeting Invitation"
        body = (f"Hello,\n\nYou are invited to attend the final project review before submission at {when}. Please confirm whether you can attend.\n\nBest regards"
                if final_review else f"Hello,\n\nI’m writing about our meeting at {when}. Please let me know if you are available.\n\nBest regards")
        return {"to": recipient.group(0) if recipient else "", "subject": subject, "message": body}

    def classify_intent(self, query: str) -> str:
        text = query.lower()
        if any(word in text for word in ["document", "policy", "contract", "file", "pdf"]): return "document_search"
        if classify_tool_intent(query): return "tool_action"
        if any(word in text for word in ["forecast", "predict", "next quarter"]): return "forecast"
        if any(word in text for word in ["alert", "threshold", "warning", "critical"]): return "alerts"
        if any(word in text for word in ["briefing", "daily brief", "executive brief"]): return "briefing"
        if any(word in text for word in ["sales", "revenue", "kpi", "margin", "analytics", "orders"]): return "analytics"
        return "general_chat"

    async def run(self, db: Session, request: ChatRequest, user_id: int | None = None, user_role: str = "manager") -> ChatResponse:
        rid, cid, mid = f"req_{uuid4().hex}", request.conversation_id or f"conv_{uuid4().hex}", f"msg_{uuid4().hex}"
        existing = db.get(Conversation, cid)
        if existing and existing.user_id is not None and user_id is not None and existing.user_id != user_id:
            raise PermissionError("Conversation unavailable")
        if not existing:
            db.add(Conversation(id=cid, user_id=user_id, title=request.query_text[:80]))
        elif existing and existing.user_id is None and user_id is not None:
            existing.user_id = user_id
        t0 = datetime.now(timezone.utc)
        db.add(Message(id=f"msg_{uuid4().hex}", conversation_id=cid, role="user", content=request.query_text, created_at=t0)); db.flush()
        intent, kwargs = self.classify_intent(request.query_text), {}
        try:
            if intent == "analytics":
                k, c, i, r = await analytics_service.answer_question(db, request.query_text); answer = i[0] if i else "Here is the sales analysis matching your query."; kwargs.update(kpis=k, chart_spec=c, insights=i, recommendations=r)
            elif intent == "alerts":
                k, _, _, _ = analytics_service.sales_overview(db)
                alerts = []
                for item in k:
                    val = float(item.value) if isinstance(item.value, (int, float)) else 0.0
                    if item.key == "revenue": alerts.extend(alert_service.evaluate(item.key, val, warning_below=100000.0, critical_below=50000.0))
                    elif item.key == "gross_margin": alerts.extend(alert_service.evaluate(item.key, val, warning_below=20.0, critical_below=10.0))
                answer = (f"Found {len(alerts)} active alerts: " + "; ".join(a.message for a in alerts)) if alerts else "All monitored sales KPIs are currently within healthy thresholds."
                kwargs.update(kpis=k, insights=[f"{a.title}: {a.message}" for a in alerts] or ["All metrics within normal limits."])
            elif intent == "briefing":
                k, _, i, _ = analytics_service.sales_overview(db)
                k_dicts = [x.model_dump() for x in k]
                briefing = briefing_service.build(k_dicts, [], [])
                answer = f"Daily Executive Briefing ({briefing['date']}): " + (i[0] if i else "Key performance indicators are healthy.")
                kwargs.update(kpis=k, insights=i)
            elif intent == "forecast":
                _, chart, _, _ = analytics_service.sales_overview(db); answer = "Generated a baseline moving-average forecast."
                kwargs.update(forecast=forecast_service.moving_average([float(row["revenue"]) for row in chart.rows]))
            elif intent == "document_search":
                answer, chunks = await rag_service.answer(db, request.query_text, user_role)
                kwargs.update(sources=[SourceRef(source_id=x.source_id, title=x.title, snippet=x.text[:240], score=x.score) for x in chunks])
            elif intent == "tool_action":
                route, clarification = classify_tool_intent(request.query_text), None
                if route and route.intent == "email_send": arguments = self.email_arguments(request.query_text)
                elif route and route.intent == "calendar_create": arguments, clarification = self.calendar_arguments(request.query_text)
                else: arguments = {"request": request.query_text}
                if clarification: answer = clarification
                elif route:
                    answer = "This action is prepared for human approval before any external write operation."
                    kwargs.update(tool_calls=[ToolCall(tool_name=route.tool_name, arguments=arguments)], requires_approval=route.requires_approval)
                else: answer = "I could not determine which connected tool should handle that request."
            else: answer = await llm_service.complete("You are an AI Business Intelligence Copilot. Be concise, factual, and manager-oriented.", request.query_text)
            db.add(Message(id=mid, conversation_id=cid, role="assistant", content=answer, created_at=t0 + timedelta(milliseconds=50)))
            if kwargs.get("requires_approval"):
                call = kwargs["tool_calls"][0]
                db.add(ToolAction(id=f"action_{uuid4().hex}", message_id=mid, user_id=user_id, tool_name=call.tool_name, arguments_json=json.dumps(call.arguments)))
            db.commit()
            suggestions = [] if kwargs.get("requires_approval") else ["Show sales performance", "Search company documents", "Generate a forecast"]
            return ChatResponse(request_id=rid, conversation_id=cid, message_id=mid, answer=answer, intent=intent, suggested_questions=suggestions, **kwargs)
        except Exception as error:
            db.rollback()
            return ChatResponse(request_id=rid, conversation_id=cid, message_id=mid, answer="I could not complete that request. Please try again.", intent=intent, error={"error_code": "REQUEST_FAILED", "message": str(error)[:180]})

supervisor = Supervisor()

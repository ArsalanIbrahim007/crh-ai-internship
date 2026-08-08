"""What the model can do, and how those requests reach real Python.

Two halves that must stay in step:

  SCHEMAS  - JSON descriptions sent to the model on every turn. This is the model's entire
             knowledge of what exists. If a description is vague the model picks the wrong
             tool, so these are written for the model to read, not for a human.
  DISPATCH - name to callable. Never let the model name a function directly; look it up
             here. A model that hallucinates a tool name gets a clean error instead of an
             attribute lookup on something arbitrary.

Schemas cost tokens on every single turn, so descriptions are kept short. The free tier caps
tokens per minute and verbose schemas burn that budget for no benefit.
"""

from tools.calendar_tool import schedule_event
from tools.email_tool import draft_email
from tools.sql_tool import run_sql
from tools.web_tool import search_web

SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "run_sql",
            "description": (
                "Run a read-only SQL SELECT against the company business database "
                "(customers, orders, order_items, products, employees, regions). "
                "Use this for any question about sales, revenue, customers or products."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "A single SQLite SELECT statement. No semicolons.",
                    },
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_web",
            "description": (
                "Search the public web. Use only for information outside the company "
                "database, such as market context or public company news. "
                "Never use this for internal sales or customer data."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search terms."},
                    "max_results": {
                        "type": "integer",
                        "description": "How many results, 1 to 10. Default 5.",
                    },
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "draft_email",
            "description": (
                "Write an email draft to a file. Does NOT send anything. "
                "Use when the user asks to draft, write or prepare an email."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "to": {"type": "string", "description": "Recipient email address."},
                    "subject": {"type": "string", "description": "Subject line."},
                    "body": {"type": "string", "description": "Full message body."},
                },
                "required": ["to", "subject", "body"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "schedule_event",
            "description": (
                "Create a calendar event file. Does NOT book anything on a live calendar. "
                "Use when the user asks to schedule or set up a meeting."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "title": {"type": "string", "description": "Event title."},
                    "start": {
                        "type": "string",
                        "description": "Start time as YYYY-MM-DD HH:MM, 24 hour clock.",
                    },
                    "duration_minutes": {
                        "type": "integer",
                        "description": "Length in minutes. Default 30.",
                    },
                    "attendees": {
                        "type": "string",
                        "description": "Comma separated email addresses. Optional.",
                    },
                    "description": {
                        "type": "string",
                        "description": "Agenda or notes. Optional.",
                    },
                },
                "required": ["title", "start"],
            },
        },
    },
]

DISPATCH = {
    "run_sql": run_sql,
    "search_web": search_web,
    "draft_email": draft_email,
    "schedule_event": schedule_event,
}

TOOL_NAMES = sorted(DISPATCH)


def call_tool(name: str, arguments: dict) -> tuple[str, object]:
    """Run one tool. Returns (text for the model, the raw result object).

    Every failure mode returns a string the model can read and react to. Raising here
    would kill the conversation, and the model can often recover from a clear error - a
    wrong column name in SQL, for instance, is usually fixed on the second attempt.
    """
    fn = DISPATCH.get(name)
    if fn is None:
        return (f"ERROR: no tool named '{name}'. Available tools: "
                f"{', '.join(TOOL_NAMES)}."), None

    if not isinstance(arguments, dict):
        return f"ERROR: arguments for {name} must be a JSON object.", None

    try:
        result = fn(**arguments)
    except TypeError as e:
        # Wrong or missing argument names - common with smaller models.
        return f"ERROR calling {name}: {e}", None
    except Exception as e:
        return f"ERROR in {name}: {type(e).__name__}: {e}", None

    text = result.to_text() if hasattr(result, "to_text") else str(result)
    return text, result


if __name__ == "__main__":
    import json

    print("tools exposed to the model:", ", ".join(TOOL_NAMES))
    total = len(json.dumps(SCHEMAS))
    print(f"schema size: {total:,} characters (~{total // 4} tokens per turn)")

    print("\ndispatch tests")
    print("-" * 60)
    cases = [
        ("run_sql", {"query": "SELECT COUNT(*) AS n FROM customers"}),
        ("run_sql", {"query": "DROP TABLE customers"}),
        ("nonexistent_tool", {"x": 1}),
        ("draft_email", {"to": "a@b.com"}),                      # missing arguments
        ("schedule_event", {"title": "Sync", "start": "tomorrow"}),
    ]
    for name, args in cases:
        text, _ = call_tool(name, args)
        print(f"  {name:<18} -> {text.splitlines()[0][:70]}")

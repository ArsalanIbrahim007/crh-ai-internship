"""Shows the rate limit headroom on each model this key can reach.

Quotas are per model, so a model that is exhausted does not block the others. This prints
requests and tokens remaining for both the per-minute and per-day windows, which is what
decides whether the copilot can run through a full demo.

    python probe_limits.py
"""

import os

from dotenv import load_dotenv
from groq import Groq

load_dotenv()
client = Groq(api_key=os.getenv("GROQ_API_KEY"))

CANDIDATES = [
    "llama-3.3-70b-versatile",
    "llama-3.1-8b-instant",
    "openai/gpt-oss-120b",
    "openai/gpt-oss-20b",
    "qwen/qwen3.6-27b",
    "groq/compound-mini",
]

# A minimal tool, so the probe also reveals whether the model does structured tool calls.
TOOL = [{
    "type": "function",
    "function": {
        "name": "run_sql",
        "description": "Run a read-only SQL SELECT against the business database.",
        "parameters": {
            "type": "object",
            "properties": {"query": {"type": "string"}},
            "required": ["query"],
        },
    },
}]

print(f"{'model':<28} {'req left':>10} {'tok left':>10} {'tok reset':>12}  tools")
print("-" * 78)

for model in CANDIDATES:
    try:
        raw = client.chat.completions.with_raw_response.create(
            model=model,
            messages=[
                {"role": "system", "content": "You query a business database."},
                {"role": "user", "content": "How many customers are there?"},
            ],
            tools=TOOL,
            tool_choice="auto",
            max_tokens=80,
            temperature=0,
        )
        h = raw.headers
        parsed = raw.parse()
        msg = parsed.choices[0].message

        if msg.tool_calls:
            tools = "structured"
        elif msg.content and "<function" in msg.content:
            tools = "text format"
        else:
            tools = "none"

        print(f"{model:<28} "
              f"{h.get('x-ratelimit-remaining-requests', '?'):>10} "
              f"{h.get('x-ratelimit-remaining-tokens', '?'):>10} "
              f"{h.get('x-ratelimit-reset-tokens', '?'):>12}  {tools}")

    except Exception as e:
        detail = str(e)
        if "rate_limit" in detail:
            note = "RATE LIMITED"
        elif "not found" in detail.lower() or "decommission" in detail.lower():
            note = "unavailable"
        else:
            note = f"{type(e).__name__}"
        print(f"{model:<28} {note}")

print()
print("tok reset in seconds means a per-minute window; minutes or hours means per-day.")

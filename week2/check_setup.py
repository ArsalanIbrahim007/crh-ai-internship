"""Checks the Groq key works and lists which models are available.

Run once after setting up .env:

    python check_setup.py

Prints nothing sensitive - the key is never displayed.
"""

import os
import sys

from dotenv import load_dotenv

load_dotenv()

key = os.getenv("GROQ_API_KEY")
if not key:
    sys.exit("GROQ_API_KEY not found. Check .env exists in this folder and has no quotes.")
if not key.startswith("gsk_"):
    sys.exit("GROQ_API_KEY does not look right - it should start with gsk_")

print("key loaded, length", len(key))

from groq import Groq

client = Groq(api_key=key)

# ---- which models can I actually use? ----
print("\navailable models")
print("-" * 60)
models = sorted(client.models.list().data, key=lambda m: m.id)
for m in models:
    ctx = getattr(m, "context_window", None)
    print("  %-42s %s" % (m.id, f"{ctx:,} ctx" if ctx else ""))

# ---- can it make a plain call? ----
print("\nplain completion")
print("-" * 60)
r = client.chat.completions.create(
    model="llama-3.3-70b-versatile",
    messages=[{"role": "user", "content": "Reply with exactly: setup works"}],
    max_tokens=20,
    temperature=0,
)
print("  reply:", r.choices[0].message.content.strip())
print("  tokens:", r.usage.prompt_tokens, "in,", r.usage.completion_tokens, "out")

# ---- can it call a tool? this is the one that matters ----
print("\ntool calling")
print("-" * 60)

TOOLS = [{
    "type": "function",
    "function": {
        "name": "run_sql",
        "description": "Run a read-only SQL query against the business database.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "A SELECT statement."},
            },
            "required": ["query"],
        },
    },
}]

r = client.chat.completions.create(
    model="llama-3.3-70b-versatile",
    messages=[
        {"role": "system", "content": "You query a business database. Tables: customers, orders, order_items, products."},
        {"role": "user", "content": "How many customers do we have?"},
    ],
    tools=TOOLS,
    tool_choice="auto",
    max_tokens=256,
    temperature=0,
)

msg = r.choices[0].message
if msg.tool_calls:
    for tc in msg.tool_calls:
        print("  tool requested:", tc.function.name)
        print("  arguments:     ", tc.function.arguments)
    print("\n  tool calling works")
else:
    print("  no tool call - model replied with text instead:")
    print("  ", (msg.content or "")[:200])
    print("\n  this would be a problem, tell Claude")

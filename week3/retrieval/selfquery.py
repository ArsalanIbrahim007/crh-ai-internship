"""Self-query retrieval: natural language -> structured filters + semantics.

"restricted legal documents from 2001 about pipeline capacity" carries three
metadata constraints and one semantic query. Embedding the whole string
retrieves on the filter words as if they were content, which is wrong. This
splits them.

The extracted filter is intersected with the user's explicit selections and
then ANDed under the RBAC scope — self-query can narrow access, never widen it.
"""
from __future__ import annotations

import json
import re

from rag import llm, prompts
from retrieval.filters import Filter

VALID_DEPTS = {"Legal", "Trading", "Risk", "HR", "Finance",
               "Compliance", "IT", "General"}
VALID_FMTS = {"email", "pdf", "docx", "html", "csv"}
VALID_CLASS = {"internal", "restricted"}


def _clean_json(text: str) -> str:
    text = re.sub(r"^```(?:json)?|```$", "", text.strip(), flags=re.M)
    start, end = text.find("{"), text.rfind("}")
    return text[start:end + 1] if start >= 0 and end > start else "{}"


def _year(value) -> int | None:
    try:
        y = int(value)
        return y if 1970 <= y <= 2030 else None
    except (TypeError, ValueError):
        return None


def parse_query(question: str, model: str | None = None) -> dict:
    """Returns {"query": str, "filter": Filter, "extracted": dict}."""
    fallback = {"query": question, "filter": Filter(), "extracted": {}}

    try:
        out = llm.chat([
            {"role": "system", "content": prompts.SELFQUERY_SYSTEM},
            {"role": "user", "content": question},
        ], model=model, max_tokens=300, json_mode=True)
        data = json.loads(_clean_json(out["text"]))
    except Exception:
        return fallback

    if not isinstance(data, dict):
        return fallback

    depts = [d for d in (data.get("departments") or []) if d in VALID_DEPTS]
    fmts = [f for f in (data.get("formats") or []) if f in VALID_FMTS]
    classes = [c for c in (data.get("classifications") or [])
               if c in VALID_CLASS]
    y_from = _year(data.get("year_from"))
    y_to = _year(data.get("year_to"))

    semantic = (data.get("query") or "").strip() or question

    extracted = {}
    if depts:
        extracted["departments"] = depts
    if fmts:
        extracted["formats"] = fmts
    if classes:
        extracted["classifications"] = classes
    if y_from:
        extracted["year_from"] = y_from
    if y_to:
        extracted["year_to"] = y_to

    return {
        "query": semantic,
        "filter": Filter(departments=depts, formats=fmts,
                         classifications=classes,
                         year_from=y_from, year_to=y_to),
        "extracted": extracted,
    }
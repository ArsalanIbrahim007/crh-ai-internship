"""Metadata predicates and RBAC scoping, compiled to LanceDB SQL.

Every filter the system applies — user-supplied or security-enforced — funnels
through build_where. Access control that lives anywhere else eventually gets
bypassed by a code path that forgot about it.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Sequence

SAFE = str.maketrans({"'": "", '"': "", ";": "", "\\": ""})


def _q(value: str) -> str:
    """Single-quote a literal after stripping quote characters. LanceDB takes
    a SQL-ish predicate string, so untrusted values never go in raw."""
    return "'" + str(value).translate(SAFE)[:200] + "'"


def _in(column: str, values: Sequence[str]) -> str:
    joined = ", ".join(_q(v) for v in values)
    return f"{column} IN ({joined})"


def _pick(a: list, b: list) -> list:
    """Intersect two allow-lists, keeping `a` if the intersection is empty."""
    if not a:
        return list(b)
    if not b:
        return list(a)
    keep = [x for x in a if x in b]
    return keep or list(a)


def _tighter(a: int | None, b: int | None, use_max: bool) -> int | None:
    vals = [v for v in (a, b) if v is not None]
    if not vals:
        return None
    return max(vals) if use_max else min(vals)


@dataclass
class Filter:
    """User-facing search constraints."""
    departments: list[str] = field(default_factory=list)
    formats: list[str] = field(default_factory=list)
    classifications: list[str] = field(default_factory=list)
    authors: list[str] = field(default_factory=list)
    custodians: list[str] = field(default_factory=list)
    year_from: int | None = None
    year_to: int | None = None
    doc_ids: list[str] = field(default_factory=list)
    thread_keys: list[str] = field(default_factory=list)

    def clauses(self) -> list[str]:
        out: list[str] = []
        if self.departments:
            out.append(_in("department", self.departments))
        if self.formats:
            out.append(_in("fmt", self.formats))
        if self.classifications:
            out.append(_in("classification", self.classifications))
        if self.custodians:
            out.append(_in("custodian", self.custodians))
        if self.doc_ids:
            out.append(_in("doc_id", self.doc_ids))
        if self.thread_keys:
            out.append(_in("thread_key", self.thread_keys))
        if self.authors:
            likes = " OR ".join(
                f"author LIKE '%{str(a).translate(SAFE)[:100]}%'"
                for a in self.authors
            )
            out.append(f"({likes})")
        if self.year_from is not None:
            out.append(f"year >= {int(self.year_from)}")
        if self.year_to is not None:
            out.append(f"year <= {int(self.year_to)}")
        return out

    def is_empty(self) -> bool:
        return not self.clauses()

    def merge(self, other: "Filter") -> "Filter":
        """Intersect two filters. Used when self-query output is combined
        with explicit UI selections. Date bounds tighten, never loosen."""
        return Filter(
            departments=_pick(self.departments, other.departments),
            formats=_pick(self.formats, other.formats),
            classifications=_pick(self.classifications, other.classifications),
            authors=_pick(self.authors, other.authors),
            custodians=_pick(self.custodians, other.custodians),
            year_from=_tighter(self.year_from, other.year_from, use_max=True),
            year_to=_tighter(self.year_to, other.year_to, use_max=False),
            doc_ids=_pick(self.doc_ids, other.doc_ids),
            thread_keys=_pick(self.thread_keys, other.thread_keys),
        )


def build_where(user_filter: Filter | None = None,
                scope: Filter | None = None) -> str | None:
    """Compose the final predicate. `scope` is the RBAC-derived filter and is
    ANDed in unconditionally — it is not negotiable by the caller."""
    clauses: list[str] = []
    if scope is not None:
        clauses.extend(scope.clauses())
    if user_filter is not None:
        clauses.extend(user_filter.clauses())
    if not clauses:
        return None
    return " AND ".join(f"({c})" for c in clauses)
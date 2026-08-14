"""Role-based access control.

Every role maps to a Filter that is ANDed into every query as `scope`. The
retrieval layer has no bypass path — build_where always applies scope, so a
new endpoint cannot forget to enforce it.
"""
from __future__ import annotations

from dataclasses import dataclass

from retrieval.filters import Filter

ALL_DEPARTMENTS = ["Legal", "Trading", "Risk", "HR", "Finance",
                   "Compliance", "IT", "General"]


@dataclass
class Role:
    name: str
    label: str
    departments: list[str]
    classifications: list[str]
    description: str

    def scope(self) -> Filter:
        depts = [] if set(self.departments) == set(ALL_DEPARTMENTS) \
            else list(self.departments)
        return Filter(departments=depts,
                      classifications=list(self.classifications))


ROLES: dict[str, Role] = {
    "executive": Role(
        "executive", "Executive",
        ALL_DEPARTMENTS, ["internal", "restricted"],
        "Unrestricted access to all departments and restricted material.",
    ),
    "legal": Role(
        "legal", "Legal Counsel",
        ["Legal", "Compliance", "Risk", "General"], ["internal", "restricted"],
        "Legal, compliance and risk material including privileged documents.",
    ),
    "trader": Role(
        "trader", "Trading Desk",
        ["Trading", "Risk", "General"], ["internal"],
        "Trading and risk material. No restricted or privileged documents.",
    ),
    "analyst": Role(
        "analyst", "Financial Analyst",
        ["Finance", "Trading", "Risk", "General"], ["internal"],
        "Financial and market material. No restricted documents.",
    ),
    "hr": Role(
        "hr", "HR Partner",
        ["HR", "Compliance", "General"], ["internal", "restricted"],
        "Personnel and compliance material including restricted records.",
    ),
    "contractor": Role(
        "contractor", "External Contractor",
        ["General"], ["internal"],
        "General material only. Most restrictive role.",
    ),
}

DEFAULT_ROLE = "analyst"


def get(role_name: str | None) -> Role:
    return ROLES.get((role_name or "").lower(), ROLES[DEFAULT_ROLE])


def scope_for(role_name: str | None) -> Filter:
    return get(role_name).scope()


def catalogue() -> list[dict]:
    return [{
        "name": r.name, "label": r.label,
        "departments": r.departments,
        "classifications": r.classifications,
        "description": r.description,
    } for r in ROLES.values()]
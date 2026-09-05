"""Single-point security enforcement.

Every piece of LLM-generated content passes through this module before
execution.  There is no second enforcement point — if this module says
"safe", the system runs it; if it says "blocked", the system does not.

Three layers:
1. Input guardrails  — prompt-injection detection on user/agent text.
2. AST code filter   — static analysis of generated Python for banned ops.
3. Tool RBAC matrix  — which agents may invoke which tools.
"""

from __future__ import annotations

import ast
import re
from dataclasses import dataclass

from config import BANNED_MODULES, BANNED_CALLS


# ── Prompt-injection detection ──────────────────────────────────────────

_INJECTION_PATTERNS = [
    re.compile(r"ignore\s+(all\s+)?previous\s+instructions", re.I),
    re.compile(r"you\s+are\s+now\s+(a|an)\s+", re.I),
    re.compile(r"system\s*:\s*", re.I),
    re.compile(r"<\|im_start\|>", re.I),
    re.compile(r"ADMIN\s*OVERRIDE", re.I),
    re.compile(r"do\s+not\s+follow\s+(any|your)\s+(previous|prior)", re.I),
    re.compile(r"reveal\s+(your|the)\s+(system|initial)\s+prompt", re.I),
]


def check_injection(text: str) -> str | None:
    """Return the matched pattern description if injection detected, else None."""
    for pat in _INJECTION_PATTERNS:
        if pat.search(text):
            return f"Injection pattern matched: {pat.pattern}"
    return None


# ── AST code filter ─────────────────────────────────────────────────────

@dataclass
class CodeViolation:
    line: int
    description: str


class _BannedCallVisitor(ast.NodeVisitor):
    """Walk an AST looking for banned imports and function calls."""

    def __init__(self) -> None:
        self.violations: list[CodeViolation] = []

    def visit_Import(self, node: ast.Import) -> None:
        for alias in node.names:
            mod = alias.name.split(".")[0]
            if mod in BANNED_MODULES:
                self.violations.append(
                    CodeViolation(node.lineno, f"Banned import: {alias.name}")
                )
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        if node.module:
            mod = node.module.split(".")[0]
            if mod in BANNED_MODULES:
                self.violations.append(
                    CodeViolation(node.lineno, f"Banned import: from {node.module}")
                )
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> None:
        # Reconstruct dotted name:  os.system(...)  →  "os.system"
        name = self._call_name(node.func)
        if name:
            for banned in BANNED_CALLS:
                if name == banned or name.endswith(f".{banned}"):
                    self.violations.append(
                        CodeViolation(node.lineno, f"Banned call: {name}")
                    )
                    break
        self.generic_visit(node)

    @staticmethod
    def _call_name(node: ast.expr) -> str | None:
        if isinstance(node, ast.Name):
            return node.id
        if isinstance(node, ast.Attribute):
            parent = _BannedCallVisitor._call_name(node.value)
            if parent:
                return f"{parent}.{node.attr}"
            return node.attr
        return None


def validate_code(source: str) -> list[CodeViolation]:
    """Parse Python source and return a list of security violations."""
    try:
        tree = ast.parse(source)
    except SyntaxError as e:
        return [CodeViolation(e.lineno or 0, f"SyntaxError: {e.msg}")]

    visitor = _BannedCallVisitor()
    visitor.visit(tree)
    return visitor.violations


# ── Tool RBAC ───────────────────────────────────────────────────────────

# Maps agent role → set of tool names it may call.
# Any tool not in the set is silently blocked.
TOOL_PERMISSIONS: dict[str, set[str]] = {
    "ceo":          {"memory_recall", "memory_write"},
    "pm":           {"memory_recall", "memory_write"},
    "researcher":   {"web_search", "memory_recall", "memory_write"},
    "swe":          {"write_file", "read_file", "list_workspace", "memory_recall"},
    "qa":           {"run_code", "read_file", "list_workspace", "memory_recall"},
    "tech_writer":  {"write_file", "read_file", "list_workspace", "memory_recall"},
}


def agent_can_use_tool(agent_role: str, tool_name: str) -> bool:
    """Single enforcement point for tool access control."""
    allowed = TOOL_PERMISSIONS.get(agent_role, set())
    return tool_name in allowed

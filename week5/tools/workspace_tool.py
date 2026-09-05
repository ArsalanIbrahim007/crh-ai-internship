"""Controlled file operations restricted to WORKSPACE_DIR.

SWE and Tech Writer agents use these to read/write generated artifacts.
All paths are resolved and validated against WORKSPACE_DIR before any I/O.
"""

from __future__ import annotations

import os
from pathlib import Path

from config import WORKSPACE_DIR
from tools.base import register_tool


def _safe_path(relative: str) -> Path:
    """Resolve a relative path and ensure it stays inside WORKSPACE_DIR."""
    target = (WORKSPACE_DIR / relative).resolve()
    ws = WORKSPACE_DIR.resolve()
    if not str(target).startswith(str(ws)):
        raise PermissionError(f"Path escapes workspace: {relative}")
    return target


# ── write_file ──────────────────────────────────────────────────────────

_WRITE_SCHEMA = {
    "type": "function",
    "function": {
        "name": "write_file",
        "description": (
            "Write content to a file in the project workspace. "
            "Creates parent directories automatically. "
            "Path must be relative to the workspace root."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Relative file path within the workspace (e.g. 'src/main.py').",
                },
                "content": {
                    "type": "string",
                    "description": "The full file content to write.",
                },
            },
            "required": ["path", "content"],
        },
    },
}


@register_tool(_WRITE_SCHEMA)
def write_file(path: str, content: str) -> str:
    target = _safe_path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")
    return f"Written {len(content)} chars to {path}"


# ── read_file ───────────────────────────────────────────────────────────

_READ_SCHEMA = {
    "type": "function",
    "function": {
        "name": "read_file",
        "description": "Read the contents of a file from the workspace.",
        "parameters": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Relative file path within the workspace.",
                },
            },
            "required": ["path"],
        },
    },
}


@register_tool(_READ_SCHEMA)
def read_file(path: str) -> str:
    target = _safe_path(path)
    if not target.exists():
        return f"File not found: {path}"
    content = target.read_text(encoding="utf-8")
    # Cap read output so it fits in context
    if len(content) > 12_000:
        return content[:12_000] + f"\n\n... (truncated, {len(content)} total chars)"
    return content


# ── list_workspace ──────────────────────────────────────────────────────

_LIST_SCHEMA = {
    "type": "function",
    "function": {
        "name": "list_workspace",
        "description": (
            "List files and directories in the workspace. "
            "Returns a tree-like listing."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "subdir": {
                    "type": "string",
                    "description": "Optional subdirectory to list. Defaults to workspace root.",
                    "default": "",
                },
            },
            "required": [],
        },
    },
}


@register_tool(_LIST_SCHEMA)
def list_workspace(subdir: str = "") -> str:
    target = _safe_path(subdir) if subdir else WORKSPACE_DIR
    if not target.exists():
        return f"Directory not found: {subdir or '.'}"

    lines = []
    for root, dirs, files in os.walk(target):
        level = len(Path(root).relative_to(WORKSPACE_DIR).parts)
        indent = "  " * level
        lines.append(f"{indent}{Path(root).name}/")
        sub_indent = "  " * (level + 1)
        for f in sorted(files):
            size = (Path(root) / f).stat().st_size
            lines.append(f"{sub_indent}{f}  ({size} bytes)")
        # Cap output
        if len(lines) > 200:
            lines.append("... (listing truncated)")
            break

    return "\n".join(lines) if lines else "(empty workspace)"

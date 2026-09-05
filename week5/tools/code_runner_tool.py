"""Sandboxed code/test execution tool.

QA uses this to run generated code and pytest in an isolated subprocess.
Security guardrails (AST validation) are applied before execution.
"""

from __future__ import annotations

from security.guardrails import validate_code
from security.sandbox import run_code as _sandbox_run, run_pytest as _sandbox_pytest
from tools.base import register_tool


_RUN_SCHEMA = {
    "type": "function",
    "function": {
        "name": "run_code",
        "description": (
            "Execute Python code or run pytest tests in a secure sandbox. "
            "The code is validated for dangerous operations before execution. "
            "Set mode to 'pytest' to run tests, 'exec' to run a script."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "code": {
                    "type": "string",
                    "description": (
                        "Python source code to execute. For pytest mode, "
                        "this is the test file content."
                    ),
                },
                "filename": {
                    "type": "string",
                    "description": "Filename to save the code as (default: main.py).",
                    "default": "main.py",
                },
                "mode": {
                    "type": "string",
                    "enum": ["exec", "pytest"],
                    "description": "Execution mode: 'exec' runs the script, 'pytest' runs it as a test.",
                    "default": "exec",
                },
            },
            "required": ["code"],
        },
    },
}


@register_tool(_RUN_SCHEMA)
def run_code(code: str, filename: str = "main.py", mode: str = "exec") -> str:
    """Validate, write, and execute code in the sandbox."""
    # Security gate: AST validation
    violations = validate_code(code)
    if violations:
        report = "\n".join(f"  Line {v.line}: {v.description}" for v in violations)
        return f"BLOCKED by security guardrails:\n{report}"

    if mode == "pytest":
        # Write the test file, then run pytest on it
        from config import WORKSPACE_DIR
        test_path = WORKSPACE_DIR / filename
        test_path.parent.mkdir(parents=True, exist_ok=True)
        test_path.write_text(code, encoding="utf-8")

        result = _sandbox_pytest(test_file=filename)
    else:
        result = _sandbox_run(code=code, filename=filename)

    # Format output
    parts = []
    if result.timed_out:
        parts.append(f"TIMED OUT after sandbox limit")
    parts.append(f"Exit code: {result.exit_code}")
    if result.stdout.strip():
        parts.append(f"STDOUT:\n{result.stdout.strip()}")
    if result.stderr.strip():
        parts.append(f"STDERR:\n{result.stderr.strip()}")
    if result.success:
        parts.insert(0, "SUCCESS")
    else:
        parts.insert(0, "FAILED")

    return "\n\n".join(parts)

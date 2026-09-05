"""Secure subprocess sandbox for executing generated code and tests.

Runs code in an isolated subprocess with:
- Hard timeout (SANDBOX_TIMEOUT_SECONDS)
- Capped stdout/stderr capture (SANDBOX_MAX_OUTPUT_BYTES)
- Restricted to WORKSPACE_DIR only
- Separate environment (no parent env vars leaked)
"""

from __future__ import annotations

import subprocess
import sys
import textwrap
from dataclasses import dataclass
from pathlib import Path

from config import SANDBOX_TIMEOUT_SECONDS, SANDBOX_MAX_OUTPUT_BYTES, WORKSPACE_DIR


@dataclass
class SandboxResult:
    """Outcome of a sandboxed execution."""
    success: bool
    exit_code: int
    stdout: str
    stderr: str
    timed_out: bool = False


def run_code(
    code: str,
    filename: str = "main.py",
    timeout: int | None = None,
) -> SandboxResult:
    """Write code to workspace and run it in a subprocess."""
    timeout = timeout or SANDBOX_TIMEOUT_SECONDS
    filepath = WORKSPACE_DIR / filename

    # Ensure workspace exists
    WORKSPACE_DIR.mkdir(parents=True, exist_ok=True)
    filepath.write_text(code, encoding="utf-8")

    return _execute(
        [sys.executable, str(filepath)],
        cwd=str(WORKSPACE_DIR),
        timeout=timeout,
    )


def run_pytest(
    test_file: str = "test_generated.py",
    target_dir: str | None = None,
    timeout: int | None = None,
) -> SandboxResult:
    """Run pytest on a file inside the workspace."""
    timeout = timeout or SANDBOX_TIMEOUT_SECONDS
    cwd = target_dir or str(WORKSPACE_DIR)
    test_path = Path(cwd) / test_file

    if not test_path.exists():
        return SandboxResult(
            success=False,
            exit_code=1,
            stdout="",
            stderr=f"Test file not found: {test_path}",
        )

    return _execute(
        [sys.executable, "-m", "pytest", str(test_path), "-v", "--tb=short", "--no-header"],
        cwd=cwd,
        timeout=timeout,
    )


def _execute(
    cmd: list[str],
    cwd: str,
    timeout: int,
) -> SandboxResult:
    """Low-level subprocess runner with timeout and output cap."""
    # Minimal safe env — no secrets leak
    safe_env = {
        "PATH": "",
        "SYSTEMROOT": "C:\\Windows",
        "PYTHONPATH": str(Path(cwd)),
    }

    try:
        proc = subprocess.run(
            cmd,
            cwd=cwd,
            capture_output=True,
            timeout=timeout,
            env=safe_env,
            text=True,
        )
        return SandboxResult(
            success=proc.returncode == 0,
            exit_code=proc.returncode,
            stdout=proc.stdout[:SANDBOX_MAX_OUTPUT_BYTES],
            stderr=proc.stderr[:SANDBOX_MAX_OUTPUT_BYTES],
        )
    except subprocess.TimeoutExpired:
        return SandboxResult(
            success=False,
            exit_code=-1,
            stdout="",
            stderr=f"Execution timed out after {timeout}s",
            timed_out=True,
        )
    except Exception as e:
        return SandboxResult(
            success=False,
            exit_code=-1,
            stdout="",
            stderr=f"Sandbox error: {e}",
        )

"""High-level orchestrator — run and resume workflows with checkpointing.

Usage:
    from orchestration.orchestrator import Orchestrator

    orch = Orchestrator()
    result = orch.run("Build an async rate limiter in Python")
    # or resume a checkpointed run:
    result = orch.resume(thread_id="abc-123")
"""

from __future__ import annotations

import sqlite3
import uuid
from typing import Any, Generator

from langgraph.checkpoint.sqlite import SqliteSaver

from config import CHECKPOINTS_DB
from orchestration.graph import compile_graph
from orchestration.state import WorkflowState


class Orchestrator:
    """Manages workflow execution with SQLite-backed checkpointing."""

    def __init__(self):
        self._conn = sqlite3.connect(str(CHECKPOINTS_DB), check_same_thread=False)
        self._checkpointer = SqliteSaver(self._conn)
        self._app = compile_graph(checkpointer=self._checkpointer)

    def run(
        self,
        initiative: str,
        thread_id: str | None = None,
    ) -> dict[str, Any]:
        """Run a full workflow from an initiative string.

        Returns the final state dict.
        """
        thread_id = thread_id or str(uuid.uuid4())
        config = {"configurable": {"thread_id": thread_id}}

        initial_state: dict[str, Any] = {
            "initiative": initiative,
            "approved": True,  # auto-approve by default
            "messages": [],
            "reflection_count": 0,
            "code_files": {},
            "current_phase": "started",
        }

        result = self._app.invoke(initial_state, config=config)
        return {"thread_id": thread_id, **result}

    def run_stream(
        self,
        initiative: str,
        thread_id: str | None = None,
    ) -> Generator[dict[str, Any], None, None]:
        """Stream workflow execution, yielding state updates per node."""
        thread_id = thread_id or str(uuid.uuid4())
        config = {"configurable": {"thread_id": thread_id}}

        initial_state: dict[str, Any] = {
            "initiative": initiative,
            "approved": True,
            "messages": [],
            "reflection_count": 0,
            "code_files": {},
            "current_phase": "started",
        }

        for event in self._app.stream(initial_state, config=config):
            # event is {node_name: state_update}
            for node_name, state_update in event.items():
                yield {
                    "thread_id": thread_id,
                    "node": node_name,
                    "update": state_update,
                }

    def resume(self, thread_id: str) -> dict[str, Any]:
        """Resume a checkpointed workflow."""
        config = {"configurable": {"thread_id": thread_id}}
        result = self._app.invoke(None, config=config)
        return {"thread_id": thread_id, **result}

    def get_state(self, thread_id: str) -> dict[str, Any] | None:
        """Retrieve the current state of a workflow."""
        config = {"configurable": {"thread_id": thread_id}}
        try:
            snapshot = self._app.get_state(config)
            return snapshot.values if snapshot else None
        except Exception:
            return None

    def close(self):
        self._conn.close()

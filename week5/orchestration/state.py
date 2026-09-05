"""Workflow state definition for the multi-agent graph.

Uses TypedDict for LangGraph compatibility.  All inter-agent communication
flows through this state — agents read from and write to typed fields,
and conditional edges inspect the state to decide routing.
"""

from __future__ import annotations

from typing import Any, TypedDict


class AgentMessage(TypedDict):
    """A single message in the agent communication log."""
    agent: str
    content: str
    tool_calls: list[tuple[str, dict, str]]  # (name, args, result)
    turns: int
    model_used: str


class WorkflowState(TypedDict, total=False):
    """The full state that flows through the LangGraph workflow.

    Fields:
        initiative:       The original user request / business initiative.
        executive_brief:  CEO's strategic analysis output.
        approved:         Whether the human approved the brief (HITL).
        rejection_reason: If rejected, why.
        sprint_plan:      PM's task decomposition.
        research_dossier: Research agent's findings.
        code_files:       Dict of filename -> content written by SWE.
        test_report:      QA's test execution results.
        test_passed:      Whether all tests passed.
        reflection_count: How many QA->SWE fix cycles have occurred.
        documentation:    Tech Writer's output.
        sprint_report:    Final sprint summary.
        messages:         Ordered log of all agent communications.
        error:            If the workflow hit a fatal error.
        current_phase:    Which phase the workflow is in (for UI display).
    """
    initiative: str
    executive_brief: str
    approved: bool
    rejection_reason: str
    sprint_plan: str
    research_dossier: str
    code_files: dict[str, str]
    test_report: str
    test_passed: bool
    reflection_count: int
    documentation: str
    sprint_report: str
    messages: list[AgentMessage]
    error: str
    current_phase: str

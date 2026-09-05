"""LangGraph workflow definition.

Defines the multi-agent state graph with:
  - Linear pipeline: CEO → HITL → PM → Research → SWE → QA → TechWriter → Report
  - Conditional edges: QA → SWE (reflection loop on test failure, max 3 retries)
  - HITL interruption node after CEO analysis
  - SqliteSaver checkpointing for resumable execution
"""

from __future__ import annotations

import logging
import time
from typing import Any

from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.sqlite import SqliteSaver

from config import MAX_REFLECTION_RETRIES, CHECKPOINTS_DB, RATE_LIMIT_DELAY_SECONDS
from orchestration.state import WorkflowState, AgentMessage
from providers.groq_provider import GroqProvider
from agents import (
    CEOAgent, PMAgent, ResearchAgent,
    SWEAgent, QAAgent, TechWriterAgent,
)

# Ensure tools are registered before any agent runs
import tools  # noqa: F401


log = logging.getLogger("autonomops.graph")

# Track whether to delay (skip first node)
_first_node_done = False


def _rate_limit_pause(node_name: str):
    """Pause between nodes to respect Groq free-tier OTPM limits."""
    global _first_node_done
    if not _first_node_done:
        _first_node_done = True
        return
    if RATE_LIMIT_DELAY_SECONDS > 0:
        log.info(f"[{node_name}] Waiting {RATE_LIMIT_DELAY_SECONDS}s for rate limit cooldown...")
        time.sleep(RATE_LIMIT_DELAY_SECONDS)


def _make_provider() -> GroqProvider:
    return GroqProvider()


def _append_message(state: dict, agent: str, result: dict) -> list[AgentMessage]:
    """Append an agent's result to the message log."""
    msgs = list(state.get("messages") or [])
    msgs.append(AgentMessage(
        agent=agent,
        content=result.get("response", ""),
        tool_calls=result.get("tool_calls_made", []),
        turns=result.get("turns", 0),
        model_used=result.get("model_used", ""),
    ))
    return msgs


# ── Node functions ──────────────────────────────────────────────────────

def ceo_node(state: dict) -> dict:
    """CEO analyses the initiative and produces an executive brief."""
    _rate_limit_pause("ceo")
    log.info("[CEO] Starting analysis...")
    provider = _make_provider()
    agent = CEOAgent(provider)
    result = agent.run(
        task=f"Analyze this business initiative and produce an ExecutiveBrief:\n\n{state['initiative']}",
    )
    return {
        "executive_brief": result["response"],
        "messages": _append_message(state, "ceo", result),
        "current_phase": "ceo_complete",
    }


def hitl_node(state: dict) -> dict:
    """Human-in-the-loop approval checkpoint.

    This node auto-approves by default. The orchestrator can inject
    a rejection by setting approved=False and rejection_reason before
    resuming from the checkpoint.
    """
    return {
        "approved": state.get("approved", True),
        "current_phase": "awaiting_approval" if not state.get("approved", True) else "approved",
    }


def pm_node(state: dict) -> dict:
    """PM decomposes the brief into a sprint plan."""
    _rate_limit_pause("pm")
    log.info("[PM] Starting sprint planning...")
    provider = _make_provider()
    agent = PMAgent(provider)

    context = f"Executive Brief:\n{state['executive_brief']}"
    result = agent.run(
        task="Create a SprintPlan with actionable tasks from this executive brief.",
        context=context,
    )
    return {
        "sprint_plan": result["response"],
        "messages": _append_message(state, "pm", result),
        "current_phase": "pm_complete",
    }


def research_node(state: dict) -> dict:
    """Research agent investigates feasibility and best practices."""
    _rate_limit_pause("research")
    log.info("[Research] Starting research...")
    provider = _make_provider()
    agent = ResearchAgent(provider)

    context = (
        f"Sprint Plan:\n{state.get('sprint_plan', '')}\n\n"
        f"Initiative:\n{state['initiative']}"
    )
    result = agent.run(
        task="Research the technical feasibility and best approaches for this initiative. "
             "Identify recommended libraries, patterns, and potential pitfalls.",
        context=context,
    )
    return {
        "research_dossier": result["response"],
        "messages": _append_message(state, "researcher", result),
        "current_phase": "research_complete",
    }


def swe_node(state: dict) -> dict:
    """SWE implements the code based on the sprint plan and research."""
    _rate_limit_pause("swe")
    log.info("[SWE] Starting implementation...")
    provider = _make_provider()
    agent = SWEAgent(provider)

    # Build context from all preceding outputs
    context_parts = [
        f"Initiative: {state['initiative']}",
        f"Sprint Plan:\n{state.get('sprint_plan', 'N/A')}",
        f"Research:\n{state.get('research_dossier', 'N/A')}",
    ]

    # If this is a reflection cycle, include QA feedback
    if state.get("test_report") and not state.get("test_passed", True):
        context_parts.append(
            f"\n--- QA FEEDBACK (BUGS TO FIX) ---\n{state['test_report']}\n"
            f"Reflection cycle: {state.get('reflection_count', 0)}/{MAX_REFLECTION_RETRIES}\n"
            "Fix ONLY the identified bugs. Do not rewrite working code."
        )
        task = "Fix the bugs identified by QA. Read the failing test report and fix the root cause."
    else:
        task = (
            "Implement the code for this initiative. Write all source files to the workspace. "
            "Include a requirements comment at the top of the main file if any libraries are needed."
        )

    result = agent.run(task=task, context="\n\n".join(context_parts))

    # Collect files the SWE wrote (from tool calls)
    code_files = dict(state.get("code_files") or {})
    for tool_name, args, _ in result.get("tool_calls_made", []):
        if tool_name == "write_file" and "path" in args and "content" in args:
            code_files[args["path"]] = args["content"]

    return {
        "code_files": code_files,
        "messages": _append_message(state, "swe", result),
        "current_phase": "swe_complete",
    }


def qa_node(state: dict) -> dict:
    """QA reviews code, generates tests, runs them, and issues a verdict."""
    _rate_limit_pause("qa")
    log.info("[QA] Starting testing...")
    provider = _make_provider()
    agent = QAAgent(provider)

    context = (
        f"Sprint Plan:\n{state.get('sprint_plan', 'N/A')}\n\n"
        f"Code files in workspace:\n"
    )
    for fname in (state.get("code_files") or {}):
        context += f"  - {fname}\n"

    result = agent.run(
        task=(
            "Review and test the code in the workspace:\n"
            "1. Read the implementation files.\n"
            "2. Write pytest tests covering happy path, edge cases, and error handling.\n"
            "3. Execute the tests using run_code in 'pytest' mode.\n"
            "4. Report VERDICT: PASS or VERDICT: FAIL with detailed diagnostics."
        ),
        context=context,
    )

    response_text = result["response"]
    test_passed = "VERDICT: PASS" in response_text.upper()
    reflection_count = state.get("reflection_count", 0)
    if not test_passed:
        reflection_count += 1

    return {
        "test_report": response_text,
        "test_passed": test_passed,
        "reflection_count": reflection_count,
        "messages": _append_message(state, "qa", result),
        "current_phase": "qa_complete",
    }


def tech_writer_node(state: dict) -> dict:
    """Tech Writer generates documentation and release notes."""
    _rate_limit_pause("tech_writer")
    log.info("[Tech Writer] Starting documentation...")
    provider = _make_provider()
    agent = TechWriterAgent(provider)

    context = (
        f"Initiative: {state['initiative']}\n\n"
        f"Code files:\n"
    )
    for fname in (state.get("code_files") or {}):
        context += f"  - {fname}\n"
    context += f"\nTest Report:\n{state.get('test_report', 'N/A')}"

    result = agent.run(
        task=(
            "Generate comprehensive documentation for the completed project:\n"
            "1. Read all code files from the workspace.\n"
            "2. Write a README.md with overview, installation, usage, and API docs.\n"
            "3. Include a Limitations section.\n"
            "4. Save documentation files to the workspace."
        ),
        context=context,
    )
    return {
        "documentation": result["response"],
        "messages": _append_message(state, "tech_writer", result),
        "current_phase": "docs_complete",
    }


def sprint_report_node(state: dict) -> dict:
    """Generate the final sprint report summarizing all work."""
    # No LLM call needed — compile from state
    msgs = state.get("messages", [])
    total_turns = sum(m.get("turns", 0) for m in msgs)
    total_tool_calls = sum(len(m.get("tool_calls", [])) for m in msgs)
    agents_involved = [m["agent"] for m in msgs]
    reflection_count = state.get("reflection_count", 0)

    report = (
        "# Sprint Report\n\n"
        f"## Initiative\n{state['initiative']}\n\n"
        f"## Execution Summary\n"
        f"- Agents involved: {', '.join(agents_involved)}\n"
        f"- Total LLM turns: {total_turns}\n"
        f"- Total tool calls: {total_tool_calls}\n"
        f"- Reflection cycles (QA → SWE): {reflection_count}\n"
        f"- Tests passed: {'Yes' if state.get('test_passed') else 'No'}\n"
        f"- Files generated: {len(state.get('code_files', {}))}\n\n"
        f"## Executive Brief\n{state.get('executive_brief', 'N/A')}\n\n"
        f"## Sprint Plan\n{state.get('sprint_plan', 'N/A')}\n\n"
        f"## Test Report\n{state.get('test_report', 'N/A')}\n\n"
        f"## Documentation\n{state.get('documentation', 'N/A')}\n"
    )
    return {
        "sprint_report": report,
        "current_phase": "complete",
    }


# ── Conditional edges ───────────────────────────────────────────────────

def should_reflect(state: dict) -> str:
    """After QA: loop back to SWE if tests failed and retries remain."""
    if state.get("test_passed", False):
        return "tech_writer"
    if state.get("reflection_count", 0) >= MAX_REFLECTION_RETRIES:
        # Give up after max retries — proceed to docs anyway
        return "tech_writer"
    return "swe_revise"


def check_approval(state: dict) -> str:
    """After HITL: proceed if approved, otherwise end."""
    if state.get("approved", True):
        return "pm"
    return "rejected"


# ── Graph builder ───────────────────────────────────────────────────────

def build_graph() -> StateGraph:
    """Build and return the compiled LangGraph workflow."""
    graph = StateGraph(WorkflowState)

    # Add nodes
    graph.add_node("ceo", ceo_node)
    graph.add_node("hitl", hitl_node)
    graph.add_node("pm", pm_node)
    graph.add_node("research", research_node)
    graph.add_node("swe", swe_node)
    graph.add_node("qa", qa_node)
    graph.add_node("swe_revise", swe_node)  # Same function, different node name for the loop
    graph.add_node("tech_writer", tech_writer_node)
    graph.add_node("sprint_report", sprint_report_node)

    # Linear edges
    graph.add_edge(START, "ceo")
    graph.add_edge("ceo", "hitl")

    # HITL conditional
    graph.add_conditional_edges("hitl", check_approval, {
        "pm": "pm",
        "rejected": END,
    })

    graph.add_edge("pm", "research")
    graph.add_edge("research", "swe")
    graph.add_edge("swe", "qa")

    # Reflection loop
    graph.add_conditional_edges("qa", should_reflect, {
        "tech_writer": "tech_writer",
        "swe_revise": "swe_revise",
    })
    graph.add_edge("swe_revise", "qa")

    graph.add_edge("tech_writer", "sprint_report")
    graph.add_edge("sprint_report", END)

    return graph


def compile_graph(checkpointer: Any = None) -> Any:
    """Compile the graph with optional checkpointing."""
    graph = build_graph()
    if checkpointer:
        return graph.compile(checkpointer=checkpointer)
    return graph.compile()

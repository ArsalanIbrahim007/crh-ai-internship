"""Framework comparison: LangGraph vs CrewAI vs AutoGen.

Empirical and architectural comparison based on the requirements of this project.
This is an analytical document generator — it does not run the other frameworks,
but produces a grounded comparison based on documented capabilities.
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from rich.console import Console
from rich.table import Table
from config import EVAL_DIR

console = Console()


def generate_comparison():
    """Generate the framework comparison report."""

    comparison = Table(
        title="Multi-Agent Framework Comparison",
        show_lines=True,
        title_style="bold cyan",
    )

    comparison.add_column("Criterion", style="cyan", width=25)
    comparison.add_column("LangGraph\n(Selected)", style="green", width=28)
    comparison.add_column("CrewAI", style="yellow", width=28)
    comparison.add_column("AutoGen", style="magenta", width=28)

    rows = [
        (
            "State Management",
            "TypedDict state flows through\ngraph. Full control over\nwhat each node reads/writes.",
            "Implicit state sharing via\nshared memory and task context.\nLess granular control.",
            "Message-based state between\nagents. Conversation history\nis the primary state."
        ),
        (
            "Cyclic Workflows",
            "Native. Conditional edges\nsupport arbitrary cycles\n(QA ↔ SWE reflection loop).",
            "Sequential or hierarchical.\nCycles require workarounds\nor custom process classes.",
            "Supports via GroupChat\nmanager, but routing logic\nis less explicit."
        ),
        (
            "Checkpointing",
            "Built-in SqliteSaver.\nCheckpoints after every node.\nResume from any state.",
            "No built-in checkpointing.\nRequires custom persistence\nimplementation.",
            "No native checkpointing.\nConversation logs can be\nsaved/restored manually."
        ),
        (
            "Human-in-the-Loop",
            "First-class interrupt_before\nand interrupt_after nodes.\nCheckpoint preserves state.",
            "Supported via human_input\nflag on tasks. Less flexible\nplacement.",
            "Supported via human proxy\nagent. Well-established\npattern."
        ),
        (
            "Debugging",
            "Explicit graph structure.\nEach node is a pure function.\nEasy to unit test in isolation.",
            "Higher-level abstraction.\nDebugging requires tracing\nthrough crew/task internals.",
            "Message-level debugging.\nConversation logs are\nreadable but verbose."
        ),
        (
            "Tool Integration",
            "Standard OpenAI tool format.\nAny function can be a tool.\nRBAC at graph level.",
            "Uses @tool decorator.\nTools bound per agent.\nCustom tool classes.",
            "Function registration per\nagent. OpenAI format.\nFlexible but less structured."
        ),
        (
            "Provider Flexibility",
            "Provider-agnostic. Any LLM\nclient works. We use Groq\nwith custom fallback.",
            "Tight LangChain integration.\nLLM config via LangChain\nmodel wrappers.",
            "Native OpenAI client.\nCustom model clients via\nconfig_list."
        ),
        (
            "Learning Curve",
            "Moderate. Requires graph\nthinking. More boilerplate\nbut more control.",
            "Low. Declarative API.\nAgents + Tasks + Crew\nabstraction is intuitive.",
            "Moderate. Conversation\npatterns are natural but\nGroupChat config is complex."
        ),
        (
            "Production Readiness",
            "High. Used in LangChain\nproduction deployments.\nActive development.",
            "Growing. v0.x → v1.0\ntransition ongoing.\nBreaking changes possible.",
            "High. Microsoft-backed.\nEnterprise adoption.\nStable API."
        ),
    ]

    for criterion, lg, crew, auto in rows:
        comparison.add_row(criterion, lg, crew, auto)

    console.print("\n")
    console.print(comparison)

    # Rationale summary
    console.print("\n[bold cyan]═══ Selection Rationale ═══[/]\n")
    console.print("[bold]LangGraph was selected because this project requires:[/]\n")

    reasons = [
        ("Cyclic reflection loops", "QA ↔ SWE bug-fix cycles are a core requirement. LangGraph handles this natively via conditional edges."),
        ("Checkpointed resumability", "Long workflows must survive interruptions. SqliteSaver provides this out of the box."),
        ("HITL governance", "The CEO approval gate needs state preservation during human review. LangGraph's interrupt nodes handle this."),
        ("Testable node functions", "Each node is a pure function of state. This makes unit testing trivial without mocking entire frameworks."),
        ("Provider independence", "We use a custom Groq provider with fallback. LangGraph doesn't impose a provider, unlike CrewAI's LangChain dependency."),
    ]

    for title, detail in reasons:
        console.print(f"  [green]✓[/] [bold]{title}:[/] {detail}")

    console.print("\n[bold yellow]Trade-offs accepted:[/]\n")
    tradeoffs = [
        "More boilerplate than CrewAI's declarative API.",
        "No built-in agent memory (we implemented our own with SQLite + FTS5).",
        "Graph visualization requires external tools (LangSmith or custom UI).",
    ]
    for t in tradeoffs:
        console.print(f"  [yellow]△[/] {t}")

    # Save to file
    output_path = EVAL_DIR / "framework_comparison.md"
    with open(output_path, "w", encoding="utf-8") as f:
        f.write("# Multi-Agent Framework Comparison\n\n")
        f.write("## Criterion Matrix\n\n")
        f.write("| Criterion | LangGraph (Selected) | CrewAI | AutoGen |\n")
        f.write("|---|---|---|---|\n")
        for criterion, lg, crew, auto in rows:
            f.write(f"| {criterion} | {lg.replace(chr(10), ' ')} | {crew.replace(chr(10), ' ')} | {auto.replace(chr(10), ' ')} |\n")
        f.write("\n## Selection Rationale\n\n")
        for title, detail in reasons:
            f.write(f"- **{title}**: {detail}\n")
        f.write("\n## Trade-offs Accepted\n\n")
        for t in tradeoffs:
            f.write(f"- {t}\n")

    console.print(f"\n[dim]Report saved to {output_path}[/]\n")


if __name__ == "__main__":
    generate_comparison()

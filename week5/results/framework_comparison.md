# Multi-Agent Framework Comparison

## Criterion Matrix

| Criterion | LangGraph (Selected) | CrewAI | AutoGen |
|---|---|---|---|
| State Management | TypedDict state flows through graph. Full control over what each node reads/writes. | Implicit state sharing via shared memory and task context. Less granular control. | Message-based state between agents. Conversation history is the primary state. |
| Cyclic Workflows | Native. Conditional edges support arbitrary cycles (QA ↔ SWE reflection loop). | Sequential or hierarchical. Cycles require workarounds or custom process classes. | Supports via GroupChat manager, but routing logic is less explicit. |
| Checkpointing | Built-in SqliteSaver. Checkpoints after every node. Resume from any state. | No built-in checkpointing. Requires custom persistence implementation. | No native checkpointing. Conversation logs can be saved/restored manually. |
| Human-in-the-Loop | First-class interrupt_before and interrupt_after nodes. Checkpoint preserves state. | Supported via human_input flag on tasks. Less flexible placement. | Supported via human proxy agent. Well-established pattern. |
| Debugging | Explicit graph structure. Each node is a pure function. Easy to unit test in isolation. | Higher-level abstraction. Debugging requires tracing through crew/task internals. | Message-level debugging. Conversation logs are readable but verbose. |
| Tool Integration | Standard OpenAI tool format. Any function can be a tool. RBAC at graph level. | Uses @tool decorator. Tools bound per agent. Custom tool classes. | Function registration per agent. OpenAI format. Flexible but less structured. |
| Provider Flexibility | Provider-agnostic. Any LLM client works. We use Groq with custom fallback. | Tight LangChain integration. LLM config via LangChain model wrappers. | Native OpenAI client. Custom model clients via config_list. |
| Learning Curve | Moderate. Requires graph thinking. More boilerplate but more control. | Low. Declarative API. Agents + Tasks + Crew abstraction is intuitive. | Moderate. Conversation patterns are natural but GroupChat config is complex. |
| Production Readiness | High. Used in LangChain production deployments. Active development. | Growing. v0.x → v1.0 transition ongoing. Breaking changes possible. | High. Microsoft-backed. Enterprise adoption. Stable API. |

## Selection Rationale

- **Cyclic reflection loops**: QA ↔ SWE bug-fix cycles are a core requirement. LangGraph handles this natively via conditional edges.
- **Checkpointed resumability**: Long workflows must survive interruptions. SqliteSaver provides this out of the box.
- **HITL governance**: The CEO approval gate needs state preservation during human review. LangGraph's interrupt nodes handle this.
- **Testable node functions**: Each node is a pure function of state. This makes unit testing trivial without mocking entire frameworks.
- **Provider independence**: We use a custom Groq provider with fallback. LangGraph doesn't impose a provider, unlike CrewAI's LangChain dependency.

## Trade-offs Accepted

- More boilerplate than CrewAI's declarative API.
- No built-in agent memory (we implemented our own with SQLite + FTS5).
- Graph visualization requires external tools (LangSmith or custom UI).

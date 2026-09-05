from app.agents.supervisor import Supervisor


def test_general_chat_intents() -> None:
    supervisor = Supervisor()

    assert supervisor._classify_intent("Hello") == "general_chat"
    assert supervisor._classify_intent("What can you help me with?") == "general_chat"
    assert supervisor._classify_intent("Who are you?") == "general_chat"


def test_analytics_intents() -> None:
    supervisor = Supervisor()

    assert supervisor._classify_intent("Show me sales performance") == "analytics"
    assert supervisor._classify_intent("Analyze revenue for last month") == "analytics"


def test_document_search_intents() -> None:
    supervisor = Supervisor()

    assert supervisor._classify_intent("What does our policy document say?") == "document_search"
    assert supervisor._classify_intent("Review this contract") == "document_search"


def test_tool_action_intents() -> None:
    supervisor = Supervisor()

    assert supervisor._classify_intent("Schedule a meeting tomorrow") == "tool_action"
    assert supervisor._classify_intent("Send an email") == "tool_action"

"""Tests for agent instantiation, role assignment, and schema validation."""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from agents import (
    CEOAgent, PMAgent, ResearchAgent,
    SWEAgent, QAAgent, TechWriterAgent,
)
from security.guardrails import TOOL_PERMISSIONS


class FakeProvider:
    """Stub provider for testing agent construction without LLM calls."""
    name = "fake"
    def chat(self, **kwargs):
        from providers.base import Response
        return Response(text="Fake response")
    def close(self):
        pass


class TestAgentRoles:
    """Every agent must have the correct role, allowed tools, and system prompt."""

    AGENTS = [
        (CEOAgent, "ceo"),
        (PMAgent, "pm"),
        (ResearchAgent, "researcher"),
        (SWEAgent, "swe"),
        (QAAgent, "qa"),
        (TechWriterAgent, "tech_writer"),
    ]

    @pytest.mark.parametrize("agent_cls,expected_role", AGENTS)
    def test_role_matches(self, agent_cls, expected_role):
        agent = agent_cls(FakeProvider())
        assert agent.role == expected_role

    @pytest.mark.parametrize("agent_cls,expected_role", AGENTS)
    def test_has_system_prompt(self, agent_cls, expected_role):
        agent = agent_cls(FakeProvider())
        assert len(agent.system_prompt) > 50

    @pytest.mark.parametrize("agent_cls,expected_role", AGENTS)
    def test_allowed_tools_match_rbac(self, agent_cls, expected_role):
        """Agent's allowed_tools must be a subset of its RBAC permissions."""
        agent = agent_cls(FakeProvider())
        rbac_tools = TOOL_PERMISSIONS.get(expected_role, set())
        for tool in agent.allowed_tools:
            assert tool in rbac_tools, (
                f"{expected_role} agent lists tool '{tool}' but RBAC doesn't allow it"
            )


class TestAgentCount:
    def test_six_agents_exist(self):
        """The spec requires exactly 6 agents."""
        from agents import __all__
        assert len(__all__) == 6

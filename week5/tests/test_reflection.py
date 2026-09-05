"""Tests for the self-healing reflection loop and workflow graph structure."""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from orchestration.graph import build_graph, should_reflect, check_approval


class TestReflectionRouting:
    """The QA → SWE reflection loop must route correctly."""

    def test_pass_goes_to_tech_writer(self):
        state = {"test_passed": True, "reflection_count": 0}
        assert should_reflect(state) == "tech_writer"

    def test_fail_goes_to_swe(self):
        state = {"test_passed": False, "reflection_count": 0}
        assert should_reflect(state) == "swe_revise"

    def test_fail_at_max_retries_goes_to_tech_writer(self):
        """After MAX_REFLECTION_RETRIES failures, stop retrying."""
        from config import MAX_REFLECTION_RETRIES
        state = {"test_passed": False, "reflection_count": MAX_REFLECTION_RETRIES}
        assert should_reflect(state) == "tech_writer"

    def test_fail_below_max_continues(self):
        state = {"test_passed": False, "reflection_count": 1}
        assert should_reflect(state) == "swe_revise"


class TestHITLRouting:
    def test_approved_goes_to_pm(self):
        state = {"approved": True}
        assert check_approval(state) == "pm"

    def test_rejected_goes_to_end(self):
        state = {"approved": False}
        assert check_approval(state) == "rejected"

    def test_default_approved(self):
        """Missing 'approved' field defaults to True."""
        state = {}
        assert check_approval(state) == "pm"


class TestGraphStructure:
    def test_graph_builds_without_error(self):
        graph = build_graph()
        assert graph is not None

    def test_graph_has_all_nodes(self):
        graph = build_graph()
        expected_nodes = {"ceo", "hitl", "pm", "research", "swe", "qa", "swe_revise", "tech_writer", "sprint_report"}
        actual_nodes = set(graph.nodes.keys())
        assert expected_nodes.issubset(actual_nodes), f"Missing nodes: {expected_nodes - actual_nodes}"

    def test_graph_compiles(self):
        from orchestration.graph import compile_graph
        app = compile_graph()
        assert app is not None

"""RBAC and filter compilation.

These tests prove the security property that matters: a scope filter cannot be
widened by anything the caller passes, and every role produces a predicate the
store will actually enforce.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest

from auth import roles
from retrieval.filters import Filter, build_where


def test_every_role_resolves():
    for name in roles.ROLES:
        assert roles.get(name).name == name


def test_unknown_role_falls_back_to_default():
    assert roles.get("nonexistent").name == roles.DEFAULT_ROLE
    assert roles.get(None).name == roles.DEFAULT_ROLE


def test_executive_has_no_department_restriction():
    scope = roles.scope_for("executive")
    assert scope.departments == []


def test_contractor_is_most_restrictive():
    scope = roles.scope_for("contractor")
    assert scope.departments == ["General"]
    assert "restricted" not in scope.classifications


def test_trader_cannot_see_restricted():
    where = build_where(scope=roles.scope_for("trader"))
    assert "restricted" not in where
    assert "internal" in where


def test_scope_is_always_anded_in():
    scope = roles.scope_for("contractor")
    user = Filter(departments=["Legal", "Trading"])
    where = build_where(user_filter=user, scope=scope)
    # both predicates present, joined by AND — user cannot drop the scope
    assert "General" in where
    assert " AND " in where


def test_quote_injection_is_neutralised():
    evil = Filter(departments=["General' OR '1'='1"])
    where = build_where(user_filter=evil)
    assert "'1'='1" not in where
    assert where.count("'") % 2 == 0


def test_empty_filter_yields_no_predicate():
    assert build_where(Filter(), Filter()) is None


def test_year_bounds_compile_to_integers():
    where = build_where(Filter(year_from=2001, year_to=2002))
    assert "year >= 2001" in where
    assert "year <= 2002" in where


def test_merge_tightens_never_widens():
    a = Filter(departments=["Legal", "Trading"], year_from=2000)
    b = Filter(departments=["Trading"], year_from=2001)
    m = a.merge(b)
    assert m.departments == ["Trading"]
    assert m.year_from == 2001        # later bound wins
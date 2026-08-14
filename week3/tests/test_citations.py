"""Citation parsing, marker normalisation and verification."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest

from rag.citations import parse, split_sentences


def chunks(n: int) -> list[dict]:
    return [{
        "chunk_id": f"c{i}", "doc_id": f"d{i}", "text": f"source text {i}",
        "title": f"Doc {i}", "department": "General", "fmt": "email",
        "rerank_score": 0.9,
    } for i in range(1, n + 1)]


def test_ascii_markers_are_parsed():
    out = parse("Prices rose sharply [1]. Demand fell [2].", chunks(3))
    assert out["stats"]["cited_sentences"] == 2
    assert out["stats"]["sources_used"] == 2


def test_fullwidth_markers_are_normalised():
    out = parse("Prices rose\u30101\u3011. Demand fell\u30102\u3011.", chunks(3))
    assert out["stats"]["cited_sentences"] == 2


def test_invalid_markers_are_stripped():
    out = parse("A claim [9] with a bad marker.", chunks(3))
    assert 9 in out["stats"]["invalid_markers"]
    assert "[9]" not in out["answer"]


def test_multiple_citations_on_one_sentence():
    out = parse("Supported by several sources [1][3].", chunks(4))
    assert out["sentences"][0]["citations"] == [1, 3]


def test_uncited_sentence_is_marked():
    out = parse("This claim has no citation.", chunks(2))
    assert out["sentences"][0]["uncited"] is True
    assert out["stats"]["citation_coverage"] == 0.0


def test_coverage_is_fractional():
    out = parse("Cited claim [1]. Uncited claim.", chunks(2))
    assert out["stats"]["citation_coverage"] == 0.5


def test_only_used_sources_are_returned():
    out = parse("Only one source used [2].", chunks(5))
    assert [s["n"] for s in out["sources"]] == [2]
    assert out["stats"]["sources_offered"] == 5


def test_sentence_splitter_handles_abbreviations():
    parts = split_sentences("First sentence here. Second one follows.")
    assert len(parts) == 2


def test_empty_answer_does_not_crash():
    out = parse("", chunks(2))
    assert out["stats"]["sentences"] == 0
    assert out["stats"]["citation_coverage"] == 0.0
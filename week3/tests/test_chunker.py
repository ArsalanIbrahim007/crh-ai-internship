import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest

from config import CHUNK_TOKENS, MIN_CHUNK_CHARS
from ingest.chunker import chunk_document, _encoder
from ingest.loaders import Document


def make_doc(text: str, fmt: str = "email") -> Document:
    return Document(doc_id="d1", source="s", fmt=fmt, text=text)


def test_empty_document_yields_nothing():
    parents, chunks = chunk_document(make_doc("   \n\n  "))
    assert parents == [] and chunks == []


def test_short_document_is_one_chunk():
    _, chunks = chunk_document(make_doc("Quarterly gas position review. " * 8))
    assert len(chunks) == 1
    assert chunks[0].chunk_id == "d1:c0"


def test_chunks_respect_token_budget():
    body = "\n\n".join(f"Paragraph {i}. " + "word " * 90 for i in range(30))
    _, chunks = chunk_document(make_doc(body))
    enc = _encoder()
    assert len(chunks) > 1
    for c in chunks:
        assert len(enc.encode(c.text)) <= CHUNK_TOKENS + 8


def test_oversized_single_paragraph_is_split():
    body = "token " * 4000
    _, chunks = chunk_document(make_doc(body))
    assert len(chunks) > 3


def test_every_chunk_links_to_a_real_parent():
    body = "\n\n".join(f"Section {i}. " + "content " * 120 for i in range(20))
    parents, chunks = chunk_document(make_doc(body))
    pids = {p.parent_id for p in parents}
    assert chunks
    assert all(c.parent_id in pids for c in chunks)


def test_ordinals_are_contiguous():
    body = "\n\n".join(f"Item {i}. " + "text " * 100 for i in range(15))
    _, chunks = chunk_document(make_doc(body))
    assert [c.ordinal for c in chunks] == list(range(len(chunks)))


def test_page_anchors_are_stripped_but_recorded():
    body = "[[page:1]]\nOpening statement here with enough text to survive.\n\n" \
           "[[page:2]]\nSecond page body with sufficient length to be kept."
    _, chunks = chunk_document(make_doc(body, fmt="pdf"))
    assert all("[[page:" not in c.text for c in chunks)
    assert {c.page for c in chunks} <= {1, 2}


def test_tiny_fragments_are_dropped():
    body = "ok\n\n" + "Substantive paragraph content here. " * 20
    _, chunks = chunk_document(make_doc(body))
    assert all(len(c.text) >= MIN_CHUNK_CHARS for c in chunks)
"""LanceDB schema and connection.

One store holds vectors, full-text index and metadata predicates, so hybrid
retrieval is a single engine rather than a fan-out and a manual join. Parents
live in a separate table — they are fetched by id at generation time, never
searched.
"""
from __future__ import annotations

from functools import lru_cache

import pyarrow as pa

from config import CHUNK_TABLE, EMBED_DIM, LANCE_URI, PARENT_TABLE

CHUNK_SCHEMA = pa.schema([
    pa.field("chunk_id", pa.string(), nullable=False),
    pa.field("doc_id", pa.string(), nullable=False),
    pa.field("parent_id", pa.string(), nullable=False),
    pa.field("ordinal", pa.int32()),
    pa.field("text", pa.string(), nullable=False),
    pa.field("vector", pa.list_(pa.float32(), EMBED_DIM), nullable=False),
    # --- metadata: every field here is filterable at query time -------
    pa.field("title", pa.string()),
    pa.field("author", pa.string()),
    pa.field("department", pa.string()),
    pa.field("classification", pa.string()),
    pa.field("fmt", pa.string()),
    pa.field("source", pa.string()),
    pa.field("created_at", pa.string()),
    pa.field("year", pa.int32()),
    pa.field("page", pa.int32()),
    pa.field("custodian", pa.string()),
    pa.field("thread_key", pa.string()),
    pa.field("recipients", pa.string()),
])

PARENT_SCHEMA = pa.schema([
    pa.field("parent_id", pa.string(), nullable=False),
    pa.field("doc_id", pa.string(), nullable=False),
    pa.field("ordinal", pa.int32()),
    pa.field("text", pa.string(), nullable=False),
])


@lru_cache(maxsize=1)
def connect():
    import lancedb
    return lancedb.connect(LANCE_URI)


def open_or_create(name: str, schema: pa.Schema):
    db = connect()
    if name in db.table_names():
        return db.open_table(name)
    return db.create_table(name, schema=schema)


def chunks_table():
    return open_or_create(CHUNK_TABLE, CHUNK_SCHEMA)


def parents_table():
    return open_or_create(PARENT_TABLE, PARENT_SCHEMA)


def table_exists(name: str) -> bool:
    return name in connect().table_names()


def counts() -> dict[str, int]:
    db = connect()
    out = {}
    for name in (CHUNK_TABLE, PARENT_TABLE):
        out[name] = db.open_table(name).count_rows() if name in db.table_names() else 0
    return out


def build_indices(num_partitions: int | None = None) -> None:
    """Build ANN and full-text indices. Run once after ingest completes —
    building incrementally during ingest is far slower."""
    import math

    tbl = chunks_table()
    n = tbl.count_rows()
    if n == 0:
        raise RuntimeError("no chunks indexed")

    # IVF_PQ below the flat-search threshold is a pessimisation.
    if n >= 50_000:
        parts = num_partitions or max(1, int(math.sqrt(n)))
        tbl.create_index(
            metric="cosine",
            vector_column_name="vector",
            index_type="IVF_PQ",
            num_partitions=parts,
            num_sub_vectors=48,          # 384 dims / 48 = 8 dims per subvector
            replace=True,
        )
        built = f"IVF_PQ({parts} partitions)"
    else:
        built = "flat (corpus below ANN threshold)"

    tbl.create_fts_index("text", replace=True, use_tantivy=False)
    print(f"vector index: {built}")
    print(f"fts index:    tantivy over `text`")
    print(f"rows:         {n:,}")


def drop_all() -> None:
    db = connect()
    for name in (CHUNK_TABLE, PARENT_TABLE):
        if name in db.table_names():
            db.drop_table(name)
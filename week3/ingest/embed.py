"""Embedding with the asymmetric bge contract.

bge models are trained asymmetrically: queries get an instruction prefix,
passages do not. Getting this backwards costs several points of recall and
is invisible until you measure it — which is why encode_query and
encode_passages are separate functions rather than one with a flag.
"""
from __future__ import annotations

import gc
from functools import lru_cache
from typing import Sequence

import numpy as np

from config import DEVICE, EMBED_BATCH, EMBED_MODEL, QUERY_PREFIX


@lru_cache(maxsize=1)
def get_model():
    import torch
    from sentence_transformers import SentenceTransformer

    device = DEVICE if torch.cuda.is_available() else "cpu"
    model = SentenceTransformer(EMBED_MODEL, device=device)
    model.max_seq_length = 512
    if device == "cuda":
        model = model.half()          # fp16: ~2x throughput, no measurable
    model.eval()                      # recall loss on bge-small
    return model


def encode_passages(texts: Sequence[str], batch_size: int = EMBED_BATCH,
                    show_progress: bool = False) -> np.ndarray:
    """No prefix. Normalised for cosine-as-dot-product."""
    if not texts:
        return np.zeros((0, 384), dtype=np.float32)
    model = get_model()
    vecs = model.encode(
        list(texts),
        batch_size=batch_size,
        normalize_embeddings=True,
        convert_to_numpy=True,
        show_progress_bar=show_progress,
    )
    return vecs.astype(np.float32)


def encode_query(query: str) -> np.ndarray:
    """Instruction prefix applied. Query side only."""
    model = get_model()
    vec = model.encode(
        [QUERY_PREFIX + query],
        normalize_embeddings=True,
        convert_to_numpy=True,
    )
    return vec.astype(np.float32)[0]


def encode_queries(queries: Sequence[str],
                   batch_size: int = EMBED_BATCH) -> np.ndarray:
    if not queries:
        return np.zeros((0, 384), dtype=np.float32)
    model = get_model()
    vecs = model.encode(
        [QUERY_PREFIX + q for q in queries],
        batch_size=batch_size,
        normalize_embeddings=True,
        convert_to_numpy=True,
    )
    return vecs.astype(np.float32)


def release() -> None:
    """Free VRAM so the reranker can load in the same process."""
    import torch

    get_model.cache_clear()
    gc.collect()
    if torch.cuda.is_available():
        torch.cuda.empty_cache()
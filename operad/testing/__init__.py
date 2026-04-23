"""Testing helpers for operad.

Temporary home for the shared hashing helpers and the cassette-based
record/replay layer. When the ``feature-operad-output`` stream lands, the
hashing helpers move onto ``OperadOutput``; this package then keeps only
the cassette layer.
"""

from __future__ import annotations

from .cassette import CassetteMiss, cassette_context
from .hashing import hash_input, hash_model, hash_prompt

__all__ = [
    "CassetteMiss",
    "cassette_context",
    "hash_input",
    "hash_model",
    "hash_prompt",
]

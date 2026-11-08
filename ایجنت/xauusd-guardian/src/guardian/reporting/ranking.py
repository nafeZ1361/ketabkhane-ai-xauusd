"""Rendering helpers for ranked symbol lists.

Kept out of ``scripts/preflight.py`` so the name/score ordering is testable
without running the gate (regression for the D-003 audit finding 1).
"""

from __future__ import annotations

from typing import Iterable

from guardian.contracts.schemas import RankedSymbol


def format_ranked(ranked: Iterable[RankedSymbol], *, limit: int = 4) -> str:
    """Render ``[(score, name), ...]`` as ``"name:score, ..."``.

    The input order is fixed by ``contracts.schemas.RankedSymbol``; callers must
    not assume ``(name, score)``.
    """
    items = list(ranked)[:limit]
    return ", ".join(f"{name}:{score}" for score, name in items)

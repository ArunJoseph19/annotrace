"""Turning a file of traces into annotation units.

An adapter knows one trace format. Everything above it -- the labeler, the
viewer, the prompt builder -- works on Trace and Unit and never sees the
source JSON. Adding a format means adding an adapter, not editing the pages.

Adapters register themselves in a plain dict. Entry-point discovery would add
a moving part for no gain at this size.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from core.units import Trace


@runtime_checkable
class TraceAdapter(Protocol):
    id: str
    name: str
    patterns: list[str]            # globs this adapter can usually read

    def sniff(self, path: str) -> float:
        """How strongly this adapter claims the file, in [0,1].

        Only the ordering is meaningful: it decides which adapter wins when
        several can read a file, so a format-specific reader beats the generic
        chat one. The value is never shown, because it ranks rather than
        measures and reading it as a probability would be wrong.
        """

    def load(self, path: str) -> list[Trace]:
        ...


_REGISTRY: dict[str, TraceAdapter] = {}


def register(adapter: TraceAdapter) -> TraceAdapter:
    _REGISTRY[adapter.id] = adapter
    return adapter


def get(adapter_id: str) -> TraceAdapter | None:
    return _REGISTRY.get(adapter_id)


def available() -> dict[str, TraceAdapter]:
    return dict(_REGISTRY)


def detect(path: str) -> tuple[TraceAdapter | None, float]:
    """Best adapter for a file, with its confidence.

    Returns (None, 0.0) when nothing recognises it, so the caller can ask the
    annotator to choose rather than loading garbage.
    """
    best, score = None, 0.0
    for a in _REGISTRY.values():
        try:
            s = a.sniff(path)
        except Exception:
            s = 0.0            # a broken adapter must not block the others
        if s > score:
            best, score = a, s
    return best, score


def load_all():
    """Import the bundled adapters so they register themselves."""
    from adapters import (chat_messages, coordinator, langfuse,      # noqa: F401
                          langsmith, otel_genai, who_and_when)

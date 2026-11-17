"""LangSmith runs: a flat array nested by parent_run_id.

Inputs and outputs are open dicts whose useful key varies by run_type, and
message lists arrive doubly nested.
"""

from __future__ import annotations

import json
import os

from adapters._tree import order_and_nest, readable
from core.adapter import register
from core.units import Field, Trace, Unit


def _flatten_once(value):
    """LangSmith wraps message lists and generations one level deeper."""
    if isinstance(value, list) and value and isinstance(value[0], list):
        return [x for inner in value for x in inner]
    return value


def _useful(d: dict) -> str:
    if not isinstance(d, dict):
        return readable(d)
    for k in ("messages", "generations", "input", "output", "query",
              "question", "text", "content"):
        if k in d:
            return readable(_flatten_once(d[k]))
    return json.dumps(d, ensure_ascii=False)[:2000] if d else ""


class LangSmithAdapter:
    id = "langsmith"
    name = "LangSmith runs"
    patterns = ["*.json", "*.jsonl"]

    def sniff(self, path: str) -> float:
        try:
            with open(path, encoding="utf-8") as f:
                doc = json.load(f)
        except (OSError, json.JSONDecodeError):
            return 0.0
        rows = doc if isinstance(doc, list) else doc.get("runs")
        if not isinstance(rows, list) or not rows or not isinstance(rows[0], dict):
            return 0.0
        return 0.98 if {"run_type", "dotted_order"} <= set(rows[0]) else 0.0

    def load(self, path: str) -> list[Trace]:
        with open(path, encoding="utf-8") as f:
            doc = json.load(f)
        rows = doc if isinstance(doc, list) else doc.get("runs", [])

        by_trace: dict = {}
        for r in rows:
            by_trace.setdefault(r.get("trace_id") or r.get("id"), []).append(r)

        out = []
        for tid, runs in by_trace.items():
            root = next((r for r in runs if not r.get("parent_run_id")), runs[0])
            fields = []
            if root.get("inputs"):
                fields.append(Field("input", "Trace input", _useful(root["inputs"]), "quote"))
            if root.get("outputs"):
                fields.append(Field("output", "Trace output", _useful(root["outputs"]), "quote"))
            out.append(Trace(id=f"{os.path.basename(path)}#{tid}",
                             title=str(root.get("name") or tid),
                             units=self._units(runs),
                             fields=fields,
                             meta={"Runs": len(runs)}, raw=root))
        return out

    def _units(self, runs) -> list[Unit]:
        units = []
        for i, (r, depth) in enumerate(order_and_nest(
                runs, "id", "parent_run_id", "dotted_order")):
            f = []
            if r.get("inputs"):
                f.append(Field("input", "Input", _useful(r["inputs"]), "quote"))
            if r.get("outputs"):
                f.append(Field("output", "Output", _useful(r["outputs"]), "quote"))
            if r.get("error"):
                f.append(Field("error", "Error", str(r["error"]), "code"))
            model = ((r.get("extra") or {}).get("invocation_params") or {}).get("model")
            if model:
                f.append(Field("model", "Model", str(model), "muted", "category"))
            if r.get("events"):
                f.append(Field("events", "Events",
                               ", ".join(e.get("name", "") for e in r["events"]
                                         if isinstance(e, dict)), "muted", "category"))

            units.append(Unit(key=str(r.get("id") or f"run_{i}"),
                              kind=str(r.get("run_type", "chain")),
                              title=str(r.get("name") or r.get("run_type") or "run"),
                              fields=f, actor=str(r.get("name") or ""),
                              badge=str(r.get("run_type", "")), depth=depth,
                              meta={"run_id": r.get("id")}))
        return units


register(LangSmithAdapter())

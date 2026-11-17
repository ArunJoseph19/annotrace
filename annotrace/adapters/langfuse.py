"""Langfuse export: a traces file and an observations file.

Observations are flat rows joined into a tree by parent_observation_id, and
input/output are strings that often hold JSON.
"""

from __future__ import annotations

import json
import os

from adapters._tree import order_and_nest, readable
from core.adapter import register
from core.units import Field, Trace, Unit


class LangfuseAdapter:
    id = "langfuse"
    name = "Langfuse export"
    patterns = ["*.json", "*.jsonl"]

    def sniff(self, path: str) -> float:
        try:
            with open(path, encoding="utf-8") as f:
                doc = json.load(f)
        except (OSError, json.JSONDecodeError):
            return 0.0
        obs = doc.get("observations") if isinstance(doc, dict) else None
        if not isinstance(obs, list) or not obs:
            return 0.0
        keys = set(obs[0])
        return 0.98 if {"parent_observation_id", "trace_id"} <= keys else 0.0

    def load(self, path: str) -> list[Trace]:
        with open(path, encoding="utf-8") as f:
            doc = json.load(f)
        by_trace: dict = {}
        for o in doc.get("observations", []):
            by_trace.setdefault(o.get("trace_id"), []).append(o)

        out = []
        for t in doc.get("traces", []) or [{"id": k} for k in by_trace]:
            tid = t.get("id")
            meta = {k: t[k] for k in ("name", "environment", "user_id", "session_id")
                    if t.get(k)}
            fields = []
            if t.get("input"):
                fields.append(Field("input", "Trace input", readable(t["input"]), "quote"))
            if t.get("output"):
                fields.append(Field("output", "Trace output", readable(t["output"]), "quote"))
            out.append(Trace(id=f"{os.path.basename(path)}#{tid}",
                             title=str(t.get("name") or t.get("input") or tid),
                             units=self._units(by_trace.get(tid, [])),
                             fields=fields, meta=meta, raw=t))
        return out

    def _units(self, obs) -> list[Unit]:
        units = []
        for i, (o, depth) in enumerate(order_and_nest(
                obs, "id", "parent_observation_id", "start_time")):
            f = []
            if o.get("input") is not None:
                f.append(Field("input", "Input", readable(o["input"]), "quote"))
            if o.get("output") is not None:
                f.append(Field("output", "Output", readable(o["output"]), "quote"))
            if o.get("level") and o["level"] != "DEFAULT":
                f.append(Field("level", "Level", str(o["level"]), "muted", "category"))
            if o.get("status_message"):
                f.append(Field("error", "Status message", str(o["status_message"]), "code"))
            if o.get("provided_model_name"):
                f.append(Field("model", "Model", str(o["provided_model_name"]),
                               "muted", "category"))
            names = o.get("tool_call_names") or []
            if names:
                f.append(Field("tools", "Tools called", ", ".join(names), "muted", "category"))
            if o.get("latency") is not None:
                f.append(Field("latency", "Latency (s)", str(o["latency"]), "muted", "number"))

            units.append(Unit(key=str(o.get("id") or f"obs_{i}"),
                              kind=str(o.get("type", "SPAN")).lower(),
                              title=str(o.get("name") or o.get("type") or "observation"),
                              fields=f, actor=str(o.get("name") or ""),
                              badge=str(o.get("type", "")).lower(), depth=depth,
                              meta={"observation_id": o.get("id")}))
        return units


register(LangfuseAdapter())

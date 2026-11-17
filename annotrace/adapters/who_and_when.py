"""Who&When failure-attribution records.

One JSON object per case: a question, a ground truth, a flat conversation
history, and annotations that belong to the run rather than to any one step --
mistake_agent, mistake_step and mistake_reason. Those become trace-level
fields, which is why the platform annotates at both scopes.
"""

from __future__ import annotations

import json
import os

from core.adapter import register
from core.units import Field, Trace, Unit

HISTORY_KEYS = ("history", "conversation", "messages", "trajectory", "steps")


def history_of(rec: dict):
    for k in HISTORY_KEYS:
        if isinstance(rec.get(k), list):
            return rec[k]
    return []


class WhoAndWhenAdapter:
    id = "who_and_when"
    name = "Who&When failure cases"
    patterns = ["*.json", "*.jsonl"]

    def sniff(self, path: str) -> float:
        try:
            with open(path, encoding="utf-8") as f:
                text = f.read()
            doc = json.loads(text)
        except (OSError, json.JSONDecodeError):
            return 0.0
        recs = doc if isinstance(doc, list) else [doc]
        if not recs or not isinstance(recs[0], dict):
            return 0.0
        keys = set(recs[0])
        if {"mistake_agent", "mistake_step"} <= keys:
            return 0.98
        # the trajectory shape without the labels, e.g. an unannotated case or a
        # Magentic-One log such as AgentRx, which carries no question field
        has_truth = bool({"ground_truth", "groundtruth"} & keys)
        return 0.55 if has_truth and history_of(recs[0]) else 0.0

    def load(self, path: str) -> list[Trace]:
        with open(path, encoding="utf-8") as f:
            doc = json.load(f)
        recs = doc if isinstance(doc, list) else [doc]
        return [self._trace(r, i, path) for i, r in enumerate(recs)
                if isinstance(r, dict) and history_of(r)]

    def _trace(self, rec: dict, idx: int, path: str) -> Trace:
        fields = []
        if rec.get("question"):
            fields.append(Field("question", "Question", str(rec["question"]), "quote"))
        # the released dataset spells it groundtruth; earlier samples ground_truth
        truth = rec.get("ground_truth", rec.get("groundtruth"))
        if truth is not None:
            fields.append(Field("ground_truth", "Ground truth", str(truth), "muted"))
        # the existing annotations: shown so an annotator can agree or disagree
        for key, label in (("mistake_agent", "Blamed agent"),
                           ("mistake_step", "Blamed step"),
                           ("mistake_reason", "Stated reason")):
            if rec.get(key) is not None:
                fields.append(Field(key, label, str(rec[key]),
                                    "muted" if key != "mistake_reason" else "quote",
                                    "category" if key == "mistake_agent" else "text"))

        meta = {k: rec[k] for k in ("question_ID", "level") if rec.get(k)}
        first = next((h for h in history_of(rec) if isinstance(h, dict)), {})
        return Trace(id=f"{os.path.basename(path)}#{rec.get('question_ID', idx)}",
                     title=str(rec.get("question") or first.get("content") or
                               f"case {idx + 1}")[:160],
                     units=self._units(rec), fields=fields, meta=meta, raw=rec)

    def _units(self, rec: dict) -> list[Unit]:
        units = []
        for i, h in enumerate(history_of(rec), start=1):
            if not isinstance(h, dict):
                h = {"content": str(h)}
            actor = str(h.get("agent") or h.get("name") or h.get("role") or "agent")
            body = h.get("content") or h.get("message") or ""
            f = [Field("content", "Said", str(body), "quote")]
            units.append(Unit(key=f"step_{i}", kind="message",
                              title=f"{i}. {actor}", fields=f, actor=actor,
                              badge=actor, meta={"index": i}))
        return units


register(WhoAndWhenAdapter())

"""Answers, autosave and export.

One record per step: the labels chosen, the reason, and whether a person or the
model produced it. A step nobody could judge is simply left unanswered.

Exports carry the questions that produced them, so a file reopens against the
right ones.
"""

from __future__ import annotations

import json
import os
import re
from datetime import datetime

from core.schema import Schema

FORMAT_VERSION = 4


def blank() -> dict:
    return {"labels": {}, "reason": "", "source": "human"}


def answered(rec: dict) -> bool:
    return bool((rec or {}).get("labels"))


def uid(name: str) -> str:
    return re.sub(r"[^a-z0-9]", "_", (name or "anon").lower())[:48]


def steps_to_do(trace, schema: Schema, kinds) -> list:
    """The units the user chose to annotate."""
    return [u for u in trace.units if (not kinds or u.kind in kinds)
            and schema.for_kind(u.kind)]


def trace_done(trace, schema: Schema, kinds, records: dict) -> bool:
    todo = steps_to_do(trace, schema, kinds)
    return bool(todo) and all(answered(records.get(u.key)) for u in todo)


def progress(traces, schema: Schema, kinds, annotations: dict) -> tuple[int, int]:
    done = sum(1 for t in traces
               if trace_done(t, schema, kinds, annotations.get(t.id) or {}))
    return done, len(traces)


def next_unanswered(traces, schema: Schema, kinds, annotations: dict, start: int) -> int:
    """Index of the next trace with work left, wrapping once."""
    n = len(traces)
    for offset in range(1, n + 1):
        i = (start + offset) % n
        if not trace_done(traces[i], schema, kinds, annotations.get(traces[i].id) or {}):
            return i
    return start


def tallies(schema: Schema, annotations: dict) -> dict[str, int]:
    """How often each label was chosen."""
    out: dict[str, int] = {}
    for records in annotations.values():
        for rec in records.values():
            for value in (rec.get("labels") or {}).values():
                if value:
                    out[str(value)] = out.get(str(value), 0) + 1
    return out


def sources(annotations: dict) -> dict[str, int]:
    out: dict[str, int] = {}
    for records in annotations.values():
        for rec in records.values():
            if answered(rec):
                key = rec.get("source", "human")
                out[key] = out.get(key, 0) + 1
    return out


def unknown_labels(schema: Schema, annotations: dict) -> dict[str, int]:
    """Answers whose label is no longer in the schema.

    They are reported and kept. The earlier build silently discarded them when
    a label was renamed, which destroyed work with no message.
    """
    known = {l for q in schema.questions for l in q.labels}
    out: dict[str, int] = {}
    for records in annotations.values():
        for rec in records.values():
            for value in (rec.get("labels") or {}).values():
                if value and value not in known:
                    out[str(value)] = out.get(str(value), 0) + 1
    return out


# ── export and import ─────────────────────────────────────────────────────

def build_payload(schema: Schema, adapter_id: str, source_file: str, kinds,
                  traces, annotations: dict, extra: dict | None = None) -> dict:
    out = []
    for t in traces:
        records = annotations.get(t.id) or {}
        steps = [{"unit_key": u.key, "kind": u.kind, **records[u.key]}
                 for u in t.units if answered(records.get(u.key))]
        if steps:
            out.append({"trace_id": t.id, "title": t.title, "steps": steps})

    payload = {"format_version": FORMAT_VERSION,
               "schema": schema.to_dict(),
               "adapter": adapter_id,
               "kinds": list(kinds or []),
               "source_file": os.path.basename(source_file or ""),
               "exported_at": datetime.now().isoformat(timespec="seconds"),
               "traces": out}
    payload.update(extra or {})
    return payload


def read_payload(payload: dict) -> dict:
    """Export -> {trace_id: {unit_key: record}}."""
    out: dict = {}
    for t in payload.get("traces", []):
        records = {}
        for s in t.get("steps", []):
            key = s.get("unit_key") or s.get("step_key")
            if not key:
                continue
            records[key] = {"labels": dict(s.get("labels") or {}),
                            "reason": s.get("reason", ""),
                            "source": s.get("source", "human")}
        if records:
            out[t.get("trace_id")] = records
    return out


def to_csv(schema: Schema, traces, annotations: dict) -> str:
    import csv
    import io
    buf = io.StringIO()
    cols = ["trace_id", "trace_title", "unit_key", "kind"] \
        + [q.id for q in schema.questions] + ["reason", "source"]
    w = csv.writer(buf)
    w.writerow(cols)
    for t in traces:
        for u in t.units:
            rec = (annotations.get(t.id) or {}).get(u.key)
            if not answered(rec):
                continue
            labels = rec.get("labels") or {}
            w.writerow([t.id, t.title, u.key, u.kind]
                       + [labels.get(q.id, "") for q in schema.questions]
                       + [rec.get("reason", ""), rec.get("source", "human")])
    return buf.getvalue()


# ── files ─────────────────────────────────────────────────────────────────

def session_path(data_dir: str, who: str) -> str:
    return os.path.join(data_dir, f"session_{uid(who)}.json")


def save_session(path: str, payload: dict) -> None:
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2)
        os.replace(tmp, path)       # atomic, so a crash cannot truncate the file
    except OSError:
        pass                        # never block the annotator


def load_session(path: str) -> dict | None:
    """Read a saved session back. The earlier build wrote this file on every
    rerun and never read it, so closing the browser lost the work."""
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return None

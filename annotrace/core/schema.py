"""What the annotator is asked.

A schema is a list of questions. Each has a prompt, a list of labels the user
typed, the step kinds it applies to, and optionally a condition on an earlier
answer. Nothing else.

The labels are the user's. Anything in schemas/ is an example to start from or
delete, never a default the tool assumes.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass

SCHEMA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                          "schemas")

# Assigned in order to whatever the user types, so a label always has a colour
# without anyone being asked to pick one.
PALETTE = ["#6b7280", "#0e7490", "#a16207", "#b45309", "#b91c1c", "#7c1d6f",
           "#15803d", "#1d4ed8"]


class SchemaError(ValueError):
    """A schema is malformed. Raised rather than defaulted, because a silent
    fallback is how the original hard-coded copies drifted apart."""


def colour_of(label: str, index: int) -> str:
    return PALETTE[index % len(PALETTE)]


def css_class(label: str) -> str:
    return "opt-" + "".join(c if c.isalnum() else "-" for c in str(label).lower())


@dataclass(frozen=True)
class Question:
    id: str
    prompt: str
    labels: tuple[str, ...] = ()
    applies_to: tuple[str, ...] = ()      # step kinds; empty means every kind
    ask_if: dict | None = None            # {"question": id, "equals": label}

    def applies(self, kind: str) -> bool:
        return not self.applies_to or kind in self.applies_to

    def visible(self, answers: dict) -> bool:
        """A follow-up stays hidden until its trigger is answered."""
        if not self.ask_if:
            return True
        got = (answers or {}).get(self.ask_if.get("question"))
        want = self.ask_if.get("equals")
        return got in want if isinstance(want, list) else got == want

    def colour(self, label: str) -> str:
        return colour_of(label, self.labels.index(label)) if label in self.labels \
            else "#9ca3af"


@dataclass(frozen=True)
class Schema:
    id: str
    name: str
    questions: tuple[Question, ...] = ()
    description: str = ""
    ask_reason: bool = True        # a free-text "why?" beside every step

    def for_kind(self, kind: str) -> list[Question]:
        return [q for q in self.questions if q.applies(kind)]

    def question(self, qid: str) -> Question | None:
        return next((q for q in self.questions if q.id == qid), None)

    def label_colour(self, label: str) -> str:
        for q in self.questions:
            if label in q.labels:
                return q.colour(label)
        return "#9ca3af"

    def css(self) -> str:
        """Label colours, generated so a new label cannot be missed."""
        seen, out = set(), []
        for q in self.questions:
            for i, label in enumerate(q.labels):
                cls = css_class(label)
                if cls in seen:
                    continue
                seen.add(cls)
                c = colour_of(label, i)
                out.append(f".{cls}{{background:{c}1a;color:{c};border:1px solid {c}40}}")
                out.append(f".sev-{cls}{{background:{c}}}")
        out.append(".opt-none{background:#f3f4f6;color:#9ca3af;border:1px solid #e5e7eb}")
        out.append(".sev-opt-none{background:#e5e7eb}")
        return "\n".join(out)

    def to_dict(self) -> dict:
        return {"id": self.id, "name": self.name, "description": self.description,
                "ask_reason": self.ask_reason,
                "questions": [{"id": q.id, "prompt": q.prompt,
                               "labels": list(q.labels),
                               "applies_to": list(q.applies_to),
                               "ask_if": q.ask_if} for q in self.questions]}


def parse(d: dict) -> Schema:
    raw = d.get("questions")
    if not raw:
        raise SchemaError("a schema needs at least one question")

    questions = []
    for i, q in enumerate(raw):
        if not q.get("id"):
            raise SchemaError(f"question {i + 1} has no id")
        if not q.get("prompt"):
            raise SchemaError(f"question {i + 1} has no prompt")
        labels = [str(o) if isinstance(o, str) else str(o.get("value", ""))
                  for o in (q.get("labels") or q.get("options") or [])]
        labels = [x for x in labels if x]
        if len(labels) < 2:
            raise SchemaError(f"{q['prompt']!r} needs at least two labels")
        if len(set(labels)) != len(labels):
            raise SchemaError(f"{q['prompt']!r} has a repeated label")
        cond = q.get("ask_if")
        if cond is not None and (not isinstance(cond, dict) or not cond.get("question")):
            raise SchemaError(f"{q['prompt']!r} has a malformed condition")
        questions.append(Question(id=q["id"], prompt=q["prompt"],
                                  labels=tuple(labels),
                                  applies_to=tuple(q.get("applies_to") or ()),
                                  ask_if=cond))

    ids = [q.id for q in questions]
    if len(set(ids)) != len(ids):
        raise SchemaError("two questions share an id")
    for q in questions:
        if q.ask_if and q.ask_if["question"] not in ids:
            raise SchemaError(f"{q.prompt!r} depends on a question that is not there")

    return Schema(id=d.get("id", "custom"), name=d.get("name", "My questions"),
                  questions=tuple(questions), description=d.get("description", ""),
                  ask_reason=bool(d.get("ask_reason", True)))


def load(path: str) -> Schema:
    with open(path, encoding="utf-8") as f:
        return parse(json.load(f))


LIBRARY_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                           "questions")


def library() -> list[tuple[str, str]]:
    """(name, path) for every saved question set, newest first.

    A visible folder inside the app, so "open a saved set" has somewhere
    obvious to open from rather than depending on a browser download folder.
    """
    if not os.path.isdir(LIBRARY_DIR):
        return []
    out = []
    for fn in os.listdir(LIBRARY_DIR):
        if not fn.endswith(".json"):
            continue
        path = os.path.join(LIBRARY_DIR, fn)
        try:
            with open(path, encoding="utf-8") as f:
                name = json.load(f).get("name") or fn[:-5]
        except (OSError, json.JSONDecodeError):
            continue
        out.append((name, path))
    return sorted(out, key=lambda kv: -os.path.getmtime(kv[1]))


def save_to_library(name: str, payload: dict) -> str:
    """Write a question set into the library and return its path."""
    os.makedirs(LIBRARY_DIR, exist_ok=True)
    stem = "".join(c if c.isalnum() else "_" for c in (name or "questions").lower())[:40]
    path = os.path.join(LIBRARY_DIR, f"{stem or 'questions'}.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)
    return path


def examples() -> dict[str, str]:
    """Example id -> path. Examples only; the tool assumes none of them."""
    out = {}
    if not os.path.isdir(SCHEMA_DIR):
        return out
    for fn in sorted(os.listdir(SCHEMA_DIR)):
        if fn.endswith(".json"):
            path = os.path.join(SCHEMA_DIR, fn)
            try:
                out[load(path).id] = path
            except (SchemaError, ValueError, OSError):
                continue
    return out

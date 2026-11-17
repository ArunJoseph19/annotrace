"""A conversation as a list of chat messages.

The common denominator: most frameworks can emit role/content messages with
tool calls. Accepts a bare list, or a wrapper holding one under messages,
conversation, trace, steps, history or traj (tau-bench).
"""

from __future__ import annotations

import json
import os

from core.adapter import register
from core.units import Field, Trace, Unit

ROLES = {"system", "user", "assistant", "tool", "function", "developer"}
LIST_KEYS = ("messages", "conversation", "trace", "steps", "history", "traj")


def messages_of(obj):
    if isinstance(obj, list):
        return obj
    if isinstance(obj, dict):
        for k in LIST_KEYS:
            if isinstance(obj.get(k), list):
                return obj[k]
    return None


def looks_like_messages(msgs) -> bool:
    if not isinstance(msgs, list) or not msgs:
        return False
    head = [m for m in msgs[:8] if isinstance(m, dict)]
    # multi-agent logs (Magentic-One, AgentRx) use agent names as roles, so a
    # role-and-content shape counts as well as the standard role names
    return bool(head) and sum(1 for m in head if m.get("role") in ROLES
                              or ("role" in m and "content" in m)) >= len(head) / 2


def records(path: str):
    with open(path, encoding="utf-8") as f:
        text = f.read()
    try:
        doc = json.loads(text)
    except json.JSONDecodeError:
        for line in text.splitlines():
            if line.strip():
                try:
                    yield json.loads(line)
                except json.JSONDecodeError:
                    continue
        return
    if isinstance(doc, list) and looks_like_messages(doc):
        yield doc                      # a bare message list is one trace
    elif isinstance(doc, list):
        yield from doc
    else:
        yield doc


def text_of(content) -> str:
    if isinstance(content, list):      # multimodal parts
        return "\n".join(p.get("text", "") or p.get("content", "")
                         for p in content if isinstance(p, dict))
    return "" if content is None else str(content)


class ChatMessagesAdapter:
    id = "chat_messages"
    name = "Chat messages (role / content)"
    patterns = ["*.json", "*.jsonl"]

    def sniff(self, path: str) -> float:
        if not path.endswith((".json", ".jsonl")):
            return 0.0
        try:
            for rec in records(path):
                # lower than a named format, so a specific adapter wins
                return 0.7 if looks_like_messages(messages_of(rec)) else 0.0
        except OSError:
            return 0.0
        return 0.0

    def load(self, path: str) -> list[Trace]:
        out = []
        for i, rec in enumerate(records(path)):
            msgs = messages_of(rec)
            if looks_like_messages(msgs):
                out.append(self._trace(rec, msgs, i, path))
        return out

    def _trace(self, rec, msgs, idx: int, path: str) -> Trace:
        meta = {}
        if isinstance(rec, dict):
            for k, display in (("id", "Id"), ("model", "Model"),
                               ("session_id", "Session"), ("user", "User")):
                if k in rec and not isinstance(rec[k], (dict, list)):
                    meta[display] = rec[k]
        first = next((m for m in msgs if isinstance(m, dict) and m.get("role") == "user"), {})
        return Trace(id=f"{os.path.basename(path)}#{idx}",
                     title=text_of(first.get("content"))[:160] or f"conversation {idx + 1}",
                     units=self._units(msgs), meta=meta,
                     raw=rec if isinstance(rec, dict) else {"messages": msgs})

    def _units(self, msgs) -> list[Unit]:
        units, n = [], 0
        for m in msgs:
            if not isinstance(m, dict) or m.get("role") == "system":
                continue                    # instructions, not a step to annotate
            n += 1
            role = m.get("role", "?")
            f = []
            body = text_of(m.get("content"))
            if body:
                f.append(Field("content", "Content", body, "quote"))

            calls = m.get("tool_calls") or ([m["function_call"]] if m.get("function_call") else [])
            for i, c in enumerate(calls):
                fn = (c.get("function") or c) if isinstance(c, dict) else {}
                suffix = "" if i == 0 else f"_{i + 1}"
                f.append(Field(f"tool_name{suffix}", "Tool called",
                               str(fn.get("name", "")), "muted", "category"))
                f.append(Field(f"tool_args{suffix}", "Arguments",
                               str(fn.get("arguments", "")), "code"))

            kind = ("tool_call" if calls else
                    "tool_result" if role in ("tool", "function") else
                    "message" if role == "user" else "response")
            units.append(Unit(key=f"msg_{n}", kind=kind,
                              title=f"{role.title()} message {n}", fields=f,
                              actor=role, badge=role, meta={"role": role}))
        return units


register(ChatMessagesAdapter())

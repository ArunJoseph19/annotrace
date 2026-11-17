"""Shared helpers for the observability formats.

Langfuse, LangSmith and OTel all store a flat row set and rebuild the tree from
a parent pointer. That part is genuinely common, so it lives here. What is
inside a row is not common at all, so each adapter extracts its own fields.
"""

from __future__ import annotations

import json


def order_and_nest(rows, id_key, parent_key, sort_key):
    """Sort rows, then work out each row's depth from its parent pointer.

    Returns [(row, depth)]. A parent that is missing from the file leaves its
    children at depth 0 rather than dropping them.
    """
    rows = sorted(rows, key=lambda r: str(r.get(sort_key) or ""))
    depth, out = {}, []
    for r in rows:
        parent = r.get(parent_key)
        d = depth.get(parent, -1) + 1 if parent else 0
        depth[r.get(id_key)] = d
        out.append((r, d))
    return out


def maybe_json(value):
    """Several of these formats store JSON inside a string field."""
    if not isinstance(value, str):
        return value
    s = value.strip()
    if not s or s[0] not in "[{":
        return value
    try:
        return json.loads(s)
    except json.JSONDecodeError:
        return value


def readable(value) -> str:
    """Turn a message list, a dict, or a scalar into something a person reads."""
    value = maybe_json(value)
    if isinstance(value, list):
        parts = []
        for item in value:
            if isinstance(item, dict):
                # OTel puts the text under `parts`; chat formats use `content`
                body = item.get("content", item.get("text", item.get("parts", "")))
                if isinstance(body, list):
                    body = " ".join(str(p.get("content", p.get("text", "")))
                                    for p in body if isinstance(p, dict))
                role = item.get("role")
                parts.append(f"{role}: {body}" if role and body else str(body or item))
            else:
                parts.append(str(item))
        return "\n".join(p for p in parts if p)
    if isinstance(value, dict):
        for k in ("content", "text", "output", "input", "answer", "result"):
            if k in value and not isinstance(value[k], (dict, list)):
                return str(value[k])
        return json.dumps(value, ensure_ascii=False)[:2000]
    return "" if value is None else str(value)

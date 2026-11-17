"""The LLM is asked the questions the human is asked.

Instructions, output shape and the reply parser all come from the same schema
object, so they cannot drift apart. The earlier build kept a hand-typed prompt
beside a separate config and the two disagreed within weeks.
"""

from __future__ import annotations

import json
import re

from core.schema import Schema
from core.units import Trace

DEFAULT_TASK = ("You are helping a human annotator. Answer the questions below "
                "about each step of an agent run.")


def system_prompt(schema: Schema, task: str = "", guidance: str = "") -> str:
    out = [task.strip() or DEFAULT_TASK, "", "## Questions", ""]
    for q in schema.questions:
        line = f"- **{q.id}**: {q.prompt}"
        if q.applies_to:
            line += f" (only on steps of kind: {', '.join(q.applies_to)})"
        if q.ask_if:
            want = q.ask_if.get("equals")
            want = " or ".join(want) if isinstance(want, list) else want
            line += f" -- only when {q.ask_if['question']} is {want}"
        out.append(line)
        out.append(f"    one of: {', '.join(q.labels)}")
    out.append("")
    if schema.ask_reason:
        out.append("Also give a short reason for every step.")
        out.append("")
    out += ["## Output", "",
            "Reply with JSON only, no commentary:", "", "```json"]
    example = {"<step key>": {q.id: q.labels[0] for q in schema.questions[:2]}}
    if schema.ask_reason:
        example["<step key>"]["reason"] = "one short sentence"
    out += [json.dumps({"steps": example}, indent=2), "```", ""]
    out.append("Use the step keys exactly as given. Leave a question out when it "
               "does not apply, rather than inventing a value.")
    if guidance.strip():
        out += ["", "## Extra guidance", "", guidance.strip()]
    return "\n".join(out)


def user_prompt(trace: Trace, keys=None, max_chars: int = 1400) -> str:
    out = []
    for f in trace.fields:
        if not f.is_empty:
            out.append(f"{f.label.upper()}: {f.value}")
    for display, value in (trace.meta or {}).items():
        out.append(f"{display.upper()}: {value}")

    units = [u for u in trace.units if keys is None or u.key in keys]
    out += ["", f"STEPS ({len(units)}):", ""]
    for u in units:
        out.append(f"[{u.key}]  kind={u.kind}" + (f"  actor={u.actor}" if u.actor else ""))
        for f in u.fields:
            if f.is_empty:
                continue
            body = f.value if len(f.value) <= max_chars else f.value[:max_chars] + " ..."
            out.append(f"  {f.name}: {body}")
        out.append("")
    out.append("Answer for these step keys: " + ", ".join(u.key for u in units))
    return "\n".join(out)


def parse(reply: str, schema: Schema, trace: Trace) -> dict:
    """Model reply -> {unit_key: {"labels": {...}, "reason": str}}.

    A label the schema does not offer is dropped rather than snapped to the
    nearest one. The earlier build snapped, which produced a confident wrong
    answer where a gap would have been visible.
    """
    blob = reply.strip()
    m = re.search(r"```(?:json)?\s*(.*?)```", blob, re.S)
    if m:
        blob = m.group(1).strip()
    start = blob.find("{")
    if start > 0:
        blob = blob[start:]
    try:
        # raw_decode: some models add a sentence after the JSON object
        doc, _ = json.JSONDecoder().raw_decode(blob)
    except json.JSONDecodeError:
        return {}

    steps = doc.get("steps") if isinstance(doc, dict) else None
    if not isinstance(steps, dict):
        steps = doc if isinstance(doc, dict) else {}

    kinds = {u.key: u.kind for u in trace.units}
    out: dict = {}
    for key, given in steps.items():
        if key not in kinds or not isinstance(given, dict):
            continue
        labels = {}
        for q in schema.for_kind(kinds[key]):
            raw = given.get(q.id)
            if raw is None:
                continue
            got = str(raw).strip()
            match = next((l for l in q.labels if l.lower() == got.lower()), None)
            if match:
                labels[q.id] = match
        reason = str(given.get("reason") or given.get("why") or "").strip()
        if labels or reason:
            out[key] = {"labels": labels, "reason": reason}
    return out

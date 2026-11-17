"""Ask a model to propose annotation labels for a loaded file.

The model reads a few real steps and proposes the plainest labels it can. It
is a starting point, not an answer: it sees the trace but not the question the
annotator is trying to settle, so the labels it proposes are generic by
nature. The user edits them.
"""

from __future__ import annotations

import json
import random
import re

from core import llm

SYSTEM = """You propose annotation labels for someone about to review an AI \
agent's execution steps by hand.

Look at the example steps and propose the SIMPLEST useful way to label them.

Rules:
- Decide how many questions are needed. One is usually enough. Add a second or
  a third only when it asks something the earlier ones cannot, for example
  because a different kind of step needs a different question. Never more than
  three.
- Two to four labels per question. Never more than four.
- Plain words a stranger understands with no explanation. No jargon, no \
invented terminology, no severity scales unless the steps really call for one.
- The labels of one question must be mutually exclusive and cover the cases.
- A second question is worth adding only when it asks something the first \
cannot. Do not make it conditional: the annotator decides for themselves when \
a question should depend on an earlier answer.
- Name what a person can see in the step, not a hidden intention.
- Judge the step. Never propose a question that only describes or classifies it: the kind of step is already recorded, so "what kind of step is this?" is wasted. A good question asks whether the step was right, useful, or where it went wrong.

Also write the house rules that go with the labels. Keep them SHORT: at most \
four lines, one sentence each. Only write a rule that is not obvious from the \
label itself -- when to pick a borderline one, and the case people get wrong. \
Never restate what a label plainly means.

Reply with JSON only, nothing else:

{
  "questions": [
    {"id": "short_id", "prompt": "A question ending in a question mark?",
     "labels": ["Label one", "Label two"]},
    {"id": "second_id", "prompt": "A second question?", "labels": ["A", "B"]}
  ],
  "rules": "Short lines, one per line, on how to apply these labels.",
  "why": "One sentence on what these labels separate."
}"""


def sample_steps(traces, kinds=None, sample_traces: int = 10, per_kind: int = 4,
                 max_chars: int = 600) -> str:
    """Steps from up to ten traces picked at random, as evidence for the model.

    Random rather than the first few: the head of a file is often the easiest
    cases, and labels proposed from those miss what the rest contains. The
    sample is seeded, so the same file proposes the same labels twice.
    """
    pool = list(traces)
    if len(pool) > sample_traces:
        pool = random.Random(len(traces)).sample(pool, sample_traces)

    by_kind: dict = {}
    for t in pool:
        for u in t.units:
            if kinds and u.kind not in kinds:
                continue
            got = by_kind.setdefault(u.kind, [])
            if len(got) < per_kind and any(not f.is_empty for f in u.fields):
                got.append(u)

    out = [f"These steps come from {len(pool)} runs picked at random out of "
           f"{len(traces)}. There are {len(by_kind)} kinds of step: "
           f"{', '.join(by_kind)}.", ""]
    first = pool[0] if pool else None
    if first is not None and first.fields:
        out.append("ABOUT THE RUN AS A WHOLE:")
        for f in first.fields:
            if not f.is_empty:
                out.append(f"  {f.label}: {f.value[:240]}")
        out.append("")
    for kind, units in by_kind.items():
        out.append(f"STEPS OF KIND '{kind}':")
        for u in units:
            out.append(f"  --- {u.title}")
            for f in u.fields:
                if f.is_empty:
                    continue
                body = f.value if len(f.value) <= max_chars else f.value[:max_chars] + " ..."
                out.append(f"    {f.name}: {body}")
        out.append("")
    return "\n".join(out)


def parse(reply: str) -> tuple[list[dict], str, str]:
    """Model reply -> (questions, rules, why). Raises LLMError when unusable."""
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
    except json.JSONDecodeError as e:
        raise llm.LLMError("The model did not return usable JSON.") from e

    raw = doc.get("questions") if isinstance(doc, dict) else None
    if not isinstance(raw, list) or not raw:
        raise llm.LLMError("The model proposed no questions.")

    out = []
    for i, q in enumerate(raw[:3]):                 # three questions at most
        labels = [str(x).strip() for x in (q.get("labels") or []) if str(x).strip()]
        labels = list(dict.fromkeys(labels))[:4]    # four labels at most, no repeats
        if len(labels) < 2 or not q.get("prompt"):
            continue
        qid = re.sub(r"[^a-z0-9_]", "_", str(q.get("id") or f"q{i + 1}").lower())[:24]
        # conditions are the annotator's to add: a proposal that carried one
        # broke as soon as the labels it named were re-proposed
        out.append({"id": qid or f"q{i + 1}", "prompt": str(q["prompt"]).strip(),
                    "labels": labels, "applies_to": [], "ask_if": None})

    if not out:
        raise llm.LLMError("The model's proposal had no usable question.")

    return out, str(doc.get("rules", "")).strip(), str(doc.get("why", "")).strip()


def propose(traces, kinds, model: str = "", api_key: str = "",
            goal: str = "") -> tuple[list[dict], str, str]:
    """`goal` is the annotator's own line about what they are looking for.

    Without it the model sees the trace but not the question being settled, so
    its labels are generic. One line from the user closes most of that gap.
    """
    body = sample_steps(traces, kinds)
    if goal.strip():
        body = f"WHAT THE ANNOTATOR IS LOOKING FOR:\n  {goal.strip()}\n\n{body}"
    return parse(llm.complete(SYSTEM, body, model, api_key, 1500))

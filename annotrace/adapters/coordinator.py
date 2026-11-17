"""Our own traces: a coordinator delegating to domain workers.

One JSON object per line. `full_conversation` holds turns of type
coordinator_thinking, expert_call, expert_response and final_answer, each
tagged with a round number.
"""

from __future__ import annotations

import ast
import json
import os
import re

from core.adapter import register
from core.units import Field, Trace, Unit


# A worker's reasoning_trace is a run of <think> <search> <information> <answer>
# tags. Grouped into Thinking-Action-Response cycles they are the finest unit
# this format offers, and the level the earlier annotation work used.
TAR_TAG = re.compile(r"<(think|search|information|answer)>(.*?)</\1>", re.DOTALL)


def tar_cycles(trace: str) -> list[dict]:
    """Split a reasoning trace into Thinking-Action-Response cycles.

    A cycle closes on an answer, on a second search, or when a new think starts
    after something has been recorded.
    """
    cycles: list[dict] = []
    cur = {"think": "", "search": "", "information": "", "answer": ""}
    filled = False

    def flush():
        nonlocal cur, filled
        if filled:
            cycles.append(dict(cur))
        cur = {"think": "", "search": "", "information": "", "answer": ""}
        filled = False

    for m in TAR_TAG.finditer(trace or ""):
        tag, content = m.group(1), m.group(2).strip()
        if tag == "think":
            if filled:
                flush()
            cur["think"] = content
        elif tag == "search":
            if cur["search"]:
                flush()
            cur["search"] = content
        elif tag == "information":
            cur["information"] = content
        else:
            cur["answer"] = content
            filled = True
            flush()
            continue
        filled = True
    flush()
    return cycles


def _golden(value) -> str:
    if not isinstance(value, list):
        return str(value)
    flat = []
    for g in value:
        s = str(g)
        if s.startswith("[") and s.endswith("]"):        # sometimes a stringified list
            try:
                inner = ast.literal_eval(s)
                flat += [str(x) for x in inner] if isinstance(inner, list) else [s]
                continue
            except (ValueError, SyntaxError):
                pass
        flat.append(s)
    return " | ".join(flat)


class CoordinatorAdapter:
    id = "coordinator"
    name = "Coordinator and workers (JSONL)"
    patterns = ["*.jsonl"]

    def sniff(self, path: str) -> float:
        if not path.endswith(".jsonl"):
            return 0.0
        try:
            with open(path, encoding="utf-8") as f:
                rec = next((json.loads(l) for l in f if l.strip()), None)
        except (OSError, json.JSONDecodeError):
            return 0.0
        if not isinstance(rec, dict) or not isinstance(rec.get("full_conversation"), list):
            return 0.0
        types = {t.get("type") for t in rec["full_conversation"] if isinstance(t, dict)}
        return 0.98 if {"expert_call", "expert_response"} & types else 0.5

    def load(self, path: str) -> list[Trace]:
        out = []
        with open(path, encoding="utf-8") as f:
            for i, line in enumerate(f):
                if line.strip():
                    try:
                        out.append(self._trace(json.loads(line), i, path))
                    except json.JSONDecodeError:
                        continue
        return out

    def _trace(self, rec: dict, idx: int, path: str) -> Trace:
        meta = {}
        for key, display in (("data_source", "Source"), ("is_correct", "Outcome"),
                             ("num_expert_calls", "Worker calls")):
            if key in rec:
                meta[display] = rec[key]

        fields = []
        if rec.get("question"):
            fields.append(Field("question", "Question", str(rec["question"]), "quote"))
        if rec.get("golden_answers") is not None:
            fields.append(Field("expected", "Expected answer",
                                _golden(rec["golden_answers"]), "muted"))
        if rec.get("final_answer") is not None:
            fields.append(Field("final_answer", "Final answer",
                                str(rec["final_answer"]), "quote"))

        return Trace(id=f"{os.path.basename(path)}#{idx}",
                     title=str(rec.get("question") or f"trace {idx + 1}"),
                     units=self._units(rec), fields=fields, meta=meta, raw=rec)

    def _units(self, rec: dict) -> list[Unit]:
        # reasoning traces are filed separately from the conversation, so index
        # them by round to slot each reply's cycles in beneath it
        by_round: dict = {}
        for et in rec.get("expert_trajectories") or []:
            by_round.setdefault(et.get("round"), []).append(et)

        rounds: dict = {}
        order: list = []
        for t in rec.get("full_conversation") or []:
            kind, rnd = t.get("type"), t.get("round")
            if kind == "final_answer":
                continue
            if rnd not in rounds and kind in ("coordinator_thinking", "expert_call",
                                              "expert_response"):
                # calls and replies are lists: keeping one of each silently lost
                # the first when a round delegated more than once
                rounds[rnd] = {"reasoning": "", "calls": [], "replies": []}
                order.append(rnd)
            if kind == "coordinator_thinking":
                r = rounds[rnd]
                part = t.get("content") or ""
                r["reasoning"] = (r["reasoning"] + "\n\n" + part) if r["reasoning"] else part
            elif kind == "expert_call":
                rounds[rnd]["calls"].append({"to": t.get("expert_id"),
                                             "question": t.get("question") or ""})
            elif kind == "expert_response" and rnd in rounds:
                rounds[rnd]["replies"].append({"from": t.get("expert_id"),
                                               "answer": t.get("answer") or "",
                                               "error": t.get("error")})

        units: list[Unit] = []
        for rnd in order:
            r = rounds[rnd]
            f = []
            if r["reasoning"]:
                f.append(Field("reasoning", "Reasoning", r["reasoning"], "quote"))
            for i, c in enumerate(r["calls"]):
                suffix = "" if i == 0 else f"_{i + 1}"
                f.append(Field(f"asked{suffix}", "Sub-question asked", c["question"]))
                f.append(Field(f"delegated_to{suffix}", "Delegated to",
                               self._who(c["to"]), "muted", "category"))
            units.append(Unit(key=f"coord_r{rnd}", kind="decision",
                              title=f"Coordinator, round {rnd}", fields=f,
                              actor="coordinator", badge=f"round {rnd}",
                              meta={"round": rnd}))

            for i, rep in enumerate(r["replies"]):
                who = rep["from"] if rep["from"] is not None else (
                    r["calls"][i]["to"] if i < len(r["calls"]) else None)
                f = []
                if i < len(r["calls"]):
                    f.append(Field("asked", "Was asked", r["calls"][i]["question"], "muted"))
                f.append(Field("reply", "Reply", rep["answer"], "quote"))
                if rep.get("error"):
                    f.append(Field("error", "Error", str(rep["error"]), "code"))
                key = f"expert_r{rnd}" if i == 0 else f"expert_r{rnd}_{i + 1}"
                # a reply holds its TAR cycles, so annotating both is the same
                # work twice; the Set up page leaves this kind off when cycles
                # are present
                cycles = self._cycles(by_round.get(rnd, []), i)
                units.append(Unit(key=key, kind="reply",
                                  title=f"{self._who(who)} replied", fields=f,
                                  actor=self._who(who), badge=f"round {rnd}",
                                  depth=1,
                                  meta={"round": rnd,
                                        **({"contains": "cycle"} if cycles else {})}))
                units += cycles

        final = next((t for t in (rec.get("full_conversation") or [])
                      if t.get("type") == "final_answer"), None)
        content = (final or {}).get("content") or rec.get("final_answer", "")
        units.append(Unit(key="final_answer", kind="output", title="Final answer",
                          actor="coordinator",
                          fields=[Field("answer", "Answer", str(content), "quote")]))
        return units

    def _cycles(self, trajectories, index: int) -> list[Unit]:
        """One unit per TAR cycle, when the file carries reasoning traces."""
        out: list[Unit] = []
        for et in trajectories[index:index + 1] or trajectories[:1]:
            call = et.get("call_index")
            if call is None:
                call = et.get("round", 0)
            for k, c in enumerate(tar_cycles(et.get("reasoning_trace", ""))):
                f = []
                if c["think"]:
                    f.append(Field("thinking", "Thinking", c["think"], "quote"))
                if c["search"]:
                    f.append(Field("action", "Action: searched for", c["search"], "code"))
                if c["information"]:
                    f.append(Field("retrieved", "Response: retrieved",
                                   c["information"], "muted"))
                if c["answer"]:
                    f.append(Field("answer", "Response: answered", c["answer"], "quote"))
                if not f:
                    continue
                who = self._who(et.get("expert_id"))
                out.append(Unit(key=f"expert_ci{call}_cycle{k}", kind="cycle",
                                title=f"{who}, cycle {k + 1}", fields=f, actor=who,
                                badge=f"call {call}", depth=2,
                                meta={"call_index": call, "cycle": k,
                                      "sub_question": et.get("sub_question", "")}))
        return out

    @staticmethod
    def _who(actor) -> str:
        return f"e{actor}" if actor is not None else "worker"


register(CoordinatorAdapter())

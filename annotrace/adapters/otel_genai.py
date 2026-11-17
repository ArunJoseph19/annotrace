"""OpenTelemetry spans from agent frameworks.

Two layouts reach us. OTLP JSON (resourceSpans) with the GenAI semantic
conventions keeps attributes as a list of {key, value:{stringValue|...}}, so
every field is looked up by key. Exports from OpenInference-based tools
(Arize Phoenix, Patronus; the TRAIL benchmark) keep a span tree under
child_spans with plain attribute dicts and their own keys: input.value,
output.value, openinference.span.kind. Each layout is read explicitly.
"""

from __future__ import annotations

import json
import os

from adapters._tree import order_and_nest, readable
from core.adapter import register
from core.units import Field, Trace, Unit


def attrs(span: dict) -> dict:
    """The attribute list, flattened to {key: value}."""
    out = {}
    for a in span.get("attributes") or []:
        if not isinstance(a, dict):
            continue
        v = a.get("value")
        out[a.get("key")] = next(iter(v.values()), "") if isinstance(v, dict) else v
    return out


def spans_of(doc: dict):
    for rs in doc.get("resourceSpans") or []:
        for ss in rs.get("scopeSpans") or rs.get("instrumentationLibrarySpans") or []:
            yield from ss.get("spans") or []


class OtelGenAIAdapter:
    id = "otel_genai"
    name = "OpenTelemetry GenAI spans"
    patterns = ["*.json"]

    def sniff(self, path: str) -> float:
        try:
            with open(path, encoding="utf-8") as f:
                doc = json.load(f)
        except (OSError, json.JSONDecodeError):
            return 0.0
        if nested_spans(doc):
            return 0.95
        if not isinstance(doc, dict) or "resourceSpans" not in doc:
            return 0.0
        for s in spans_of(doc):
            if any(str(k).startswith("gen_ai.") for k in attrs(s)):
                return 0.98
        return 0.6          # spans, but not GenAI ones

    def load(self, path: str) -> list[Trace]:
        with open(path, encoding="utf-8") as f:
            doc = json.load(f)
        if nested_spans(doc):
            return self._load_nested(doc, path)
        by_trace: dict = {}
        for s in spans_of(doc):
            by_trace.setdefault(s.get("traceId"), []).append(s)

        out = []
        for tid, spans in by_trace.items():
            root = next((s for s in spans if not s.get("parentSpanId")), spans[0])
            a = attrs(root)
            meta = {k: v for k, v in (("Agent", a.get("gen_ai.agent.name")),
                                      ("Provider", a.get("gen_ai.provider.name"))) if v}
            out.append(Trace(id=f"{os.path.basename(path)}#{tid}",
                             title=str(root.get("name") or tid),
                             units=self._units(spans), meta=meta, raw=root))
        return out

    def _units(self, spans) -> list[Unit]:
        units = []
        for i, (s, depth) in enumerate(order_and_nest(
                spans, "spanId", "parentSpanId", "startTimeUnixNano")):
            a = attrs(s)
            f = []
            inp = a.get("gen_ai.input.messages") or a.get("gen_ai.tool.call.arguments")
            outp = a.get("gen_ai.output.messages") or a.get("gen_ai.tool.call.result")
            if inp:
                f.append(Field("input", "Input", readable(inp), "quote"))
            if outp:
                f.append(Field("output", "Output", readable(outp), "quote"))
            if a.get("gen_ai.tool.name"):
                f.append(Field("tool", "Tool", str(a["gen_ai.tool.name"]),
                               "muted", "category"))
            if a.get("gen_ai.request.model"):
                f.append(Field("model", "Model", str(a["gen_ai.request.model"]),
                               "muted", "category"))
            if a.get("gen_ai.agent.name"):
                f.append(Field("agent", "Agent", str(a["gen_ai.agent.name"]),
                               "muted", "category"))
            status = s.get("status") or {}
            if status.get("message") or status.get("code", "").endswith("ERROR"):
                f.append(Field("error", "Status",
                               str(status.get("message") or status.get("code")), "code"))

            op = str(a.get("gen_ai.operation.name", "span"))
            units.append(Unit(key=str(s.get("spanId") or f"span_{i}"), kind=op,
                              title=str(s.get("name") or op), fields=f,
                              actor=str(a.get("gen_ai.agent.name")
                                        or a.get("gen_ai.tool.name") or ""),
                              badge=op, depth=depth,
                              meta={"span_id": s.get("spanId")}))
        return units


    def _load_nested(self, doc: dict, path: str) -> list[Trace]:
        roots = nested_spans(doc)
        units: list[Unit] = []

        def walk(span: dict, depth: int) -> None:
            a = span.get("span_attributes") or {}
            kind = str(a.get("openinference.span.kind") or "span").lower()
            f = []
            if a.get("input.value"):
                f.append(Field("input", "Input", readable(a["input.value"]), "quote"))
            if a.get("output.value"):
                f.append(Field("output", "Output", readable(a["output.value"]), "quote"))
            if a.get("tool.name"):
                f.append(Field("tool", "Tool", str(a["tool.name"]), "muted", "category"))
            if a.get("llm.model_name"):
                f.append(Field("model", "Model", str(a["llm.model_name"]), "muted", "category"))
            if str(span.get("status_code", "")).lower() == "error" or span.get("status_message"):
                f.append(Field("error", "Status", str(span.get("status_message")
                                                      or span.get("status_code")), "code"))
            units.append(Unit(key=str(span.get("span_id") or f"span_{len(units)}"),
                              kind=kind, title=str(span.get("span_name") or kind),
                              fields=f, actor=str(a.get("tool.name") or ""),
                              badge=kind, depth=depth,
                              meta={"span_id": span.get("span_id")}))
            for child in sorted(span.get("child_spans") or [],
                                key=lambda c: str(c.get("timestamp") or "")):
                walk(child, depth + 1)

        for r in roots:
            walk(r, 0)
        tid = doc.get("trace_id") or roots[0].get("trace_id")
        return [Trace(id=f"{os.path.basename(path)}#{tid}",
                      title=str(roots[0].get("span_name") or tid), units=units,
                      meta={"Service": roots[0].get("service_name") or ""}, raw=doc)]


def nested_spans(doc) -> list:
    """Root spans of an OpenInference-style export, or [] if this is not one."""
    spans = doc.get("spans") if isinstance(doc, dict) else None
    if not isinstance(spans, list) or not spans or not isinstance(spans[0], dict):
        return []
    head = spans[0]
    return spans if {"span_id", "span_attributes"} <= set(head) else []


register(OtelGenAIAdapter())

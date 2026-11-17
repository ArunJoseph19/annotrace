"""Shared rendering.

Cards are driven by a step's fields and label colours come from the schema, so
a new trace format or a new label needs no change here.
"""

from __future__ import annotations

import html

import streamlit as st

from core.schema import css_class

BASE_CSS = """
<style>
  .unit { border:1px solid #e6e4dd; border-radius:9px; background:#fff;
          margin:0 0 10px 0; overflow:hidden; display:flex; }
  .unit-open { box-shadow:0 1px 3px rgba(20,20,10,.05); }
  .unit-body { flex:1; min-width:0; }
  .unit-head { display:flex; align-items:center; gap:10px; padding:10px 15px; }
  .unit-open .unit-head { border-bottom:1px solid #f0eee8; background:#fcfcfb; }
  .unit-title { font-weight:640; font-size:.92rem; color:#111; }
  /* One colour per kind of step, so a decision, a reply and a cycle are told
     apart at a glance. The left bar carries the label once one is chosen. */
  .unit-kind { font-size:.66rem; letter-spacing:.04em; text-transform:uppercase;
               border-radius:4px; padding:2px 7px; }
  .unit-key { font-family:ui-monospace,Menlo,monospace; font-size:.7rem;
              color:#a09e95; margin-left:auto; }
  .unit-why { font-size:.78rem; color:#8b8981; font-style:italic; }
  .sev { width:4px; flex:0 0 4px; }
  .slot { padding:8px 15px 0 15px; }
  .slot:last-child { padding-bottom:10px; }
  .slot-label { font-size:.66rem; letter-spacing:.05em; text-transform:uppercase;
                color:#8b8981; margin-bottom:2px; }
  .slot-body { font-size:.85rem; color:#23221f; white-space:pre-wrap; line-height:1.5; }
  .slot-quote .slot-body { border-left:2px solid #e0ded6; padding-left:10px; }
  .slot-code .slot-body { font-family:ui-monospace,Menlo,monospace; font-size:.78rem;
                          background:#f7f6f2; padding:7px 9px; border-radius:5px; }
  .slot-muted .slot-body { color:#7a7870; font-size:.8rem; }
  .pill { display:inline-block; font-size:.7rem; font-weight:600;
          border-radius:11px; padding:2px 10px; }
  .done { opacity:.62; }
  .meta-row { display:flex; flex-wrap:wrap; gap:22px; background:#f4f6fb;
              border:1px solid #dbe4f2; border-radius:8px; padding:10px 15px;
              margin-bottom:12px; }
  /* The sidebar copy of the run's question and answer, which stays in view
     while the steps scroll. A sticky element cannot do this: Streamlit wraps
     each element in a box of its own height, so it has no distance to travel. */
  .pin-k { font-size:.62rem; letter-spacing:.06em; text-transform:uppercase;
           color:#7d7a72; font-weight:700; margin-top:7px; }
  .pin-v { font-size:.79rem; color:#23221f; line-height:1.4; }
  .pin-box { background:#fff; border:1px solid #e0ded6; border-radius:7px;
             padding:8px 11px; margin-bottom:4px; }
  .meta-k { font-size:.64rem; letter-spacing:.05em; text-transform:uppercase;
            color:#6a7891; font-weight:600; }
  .meta-v { font-size:.83rem; color:#33415c; }
  .src { font-size:.68rem; border-radius:4px; padding:1px 7px; font-weight:600; }
  .src-llm { color:#2a78d6; background:#eaf1fb; border:1px solid #c8ddf5; }
  .src-human { color:#15803d; background:#eaf6ee; border:1px solid #bfe3cb; }
  /* the model's result shows on the button, not as a line that moves the page */
  [class*="st-key-askbox-ok"] button { background:#15803d !important;
      border-color:#15803d !important; }
  [class*="st-key-askbox-ok"] button:hover { background:#116632 !important; }
  [class*="st-key-askbox-error"] button { background:#b91c1c !important;
      border-color:#b91c1c !important; }

  .todo { font-size:.7rem; font-weight:700; letter-spacing:.03em;
          border-radius:999px; padding:2px 10px; background:#fff6e8;
          color:#8a5a1f; border:1px dashed #e0cba0; }

  /* A disagreement row. The run, the step, then one line per side, so the
     two answers and their reasons sit next to each other. */
  .cmp-run { font-size:.74rem; color:#7d7a72; margin-bottom:3px; }
  .cmp-head { display:flex; align-items:center; gap:9px; flex-wrap:wrap;
              margin-bottom:7px; }
  .cmp-step { font-size:.88rem; font-weight:650; color:#23221f; }
  .cmp-q { font-size:.76rem; color:#55534d; }
  .cmp-side { display:flex; align-items:baseline; gap:9px; padding:3px 0; }
  .cmp-tag { font-size:.68rem; font-weight:700; color:#fff; background:#8b8981;
             border-radius:3px; padding:1px 6px; min-width:15px; text-align:center; }
  .cmp-src { font-size:.74rem; color:#7d7a72; min-width:96px; }
  .cmp-why { font-size:.78rem; color:#55534d; }

  .warnbox { background:#fffaf0; border:1px solid #f0dfc0; color:#8a5a1f;
             border-radius:8px; padding:9px 14px; font-size:.83rem; margin-bottom:8px; }

  /* The step being answered keeps its controls in view while its evidence is
     read, so a long step does not force a scroll back up to answer it. */
  [class*="st-key-answerbar-"] {
      background:#f1efe8; border:1px solid #e0ded6;
      border-radius:8px; padding:9px 14px 3px 14px; margin-bottom:10px;
  }
  [class*="st-key-answerbar-"] label p { font-weight:600; color:#3d3b36; }
  /* The reason box sits on the panel's own beige, so without a ground of its
     own it does not read as a field you can type in. */
  [class*="st-key-answerbar-"] textarea {
      background:#fff !important; border:1px solid #d9d6ce !important;
      border-radius:6px !important; color:#23221f !important; }
  [class*="st-key-answerbar-"] textarea:focus {
      border-color:#9db4d6 !important; box-shadow:0 0 0 2px rgba(42,120,214,.12) !important; }
  [class*="st-key-answerbar-"] [data-baseweb="textarea"] { background:#fff !important; }
  /* line the answer panel up with the card it belongs to */
  [class*="st-key-answerbar-d1-"] { margin-left: 22px; }
  [class*="st-key-answerbar-d2-"] { margin-left: 44px; }
  [class*="st-key-answerbar-d3-"] { margin-left: 66px; }


  /* Review: one readable row per step. */
  .rv { display:flex; border:1px solid #e6e4dd; border-radius:9px; background:#fff;
        margin-bottom:8px; overflow:hidden; }
  .rv-bar { width:5px; flex:0 0 5px; }
  .rv-body { flex:1; min-width:0; padding:10px 15px; }
  .rv-top { display:flex; align-items:center; gap:9px; flex-wrap:wrap; }
  .rv-title { font-size:.9rem; font-weight:650; color:#1b1a18; }
  .rv-why { font-size:.83rem; color:#4b4a45; margin-top:4px; line-height:1.45; }
  .rv-src { font-size:.66rem; font-weight:700; border-radius:4px; padding:1px 7px;
            margin-left:auto; }
  .rv-none { color:#a09e95; font-style:italic; font-size:.82rem; }

  /* Nesting is shown by indent alone; rails added lines without adding meaning. */
  .nest { display:flex; }
  .rail { flex:0 0 22px; }
</style>
"""


def brand() -> None:
    """The tool's name, above the page list in the sidebar."""
    st.sidebar.markdown(
        '<div style="font-size:1.05rem;font-weight:700;letter-spacing:-0.01em;'
        'color:#23221f;padding:2px 0 10px 0">Annotrace</div>'
        '<div style="font-size:.72rem;color:#8b8981;margin-top:-8px;'
        'padding-bottom:10px">Label agent traces, step by step.</div>',
        unsafe_allow_html=True)


def inject_css(schema=None, labels=None, kinds=None) -> None:
    """Base styles, plus a colour rule per label.

    `labels` covers the page where a schema does not exist yet: without it the
    label pills on Set up rendered as unstyled text, because their colours are
    generated and nothing had generated them.
    """
    st.markdown(BASE_CSS, unsafe_allow_html=True)
    rules = []
    if schema is not None:
        rules.append(schema.css())
    if labels:
        rules.append(label_css(labels))
    if kinds:
        rules.append(kind_css(kinds))
    if rules:
        st.markdown("<style>" + "\n".join(rules) + "</style>", unsafe_allow_html=True)


def label_css(labels) -> str:
    """Colour rules for a flat list of labels, in the order they were typed."""
    from core.schema import colour_of
    seen, out = set(), []
    for i, label in enumerate(labels):
        cls = css_class(label)
        if cls in seen:
            continue
        seen.add(cls)
        c = colour_of(label, i)
        out.append(f".{cls}{{background:{c}1a;color:{c};border:1px solid {c}40}}")
        out.append(f".sev-{cls}{{background:{c}}}")
    return "\n".join(out)


KIND_COLOURS = ["#2a6fb5", "#8a5a1f", "#5b6a2e", "#7a4a86", "#1f6b62", "#9c4a4a"]


def kind_class(kind) -> str:
    return "kind-" + "".join(c if c.isalnum() else "-" for c in str(kind).lower())


def kind_css(kinds) -> str:
    """One colour per kind of step, assigned in a stable order, so a decision,
    a reply and a cycle are told apart without reading the word."""
    out = []
    for i, kind in enumerate(sorted(set(kinds))):
        c = KIND_COLOURS[i % len(KIND_COLOURS)]
        cls = kind_class(kind)
        out.append("." + cls + "{background:" + c + "14;color:" + c
                   + ";border:1px solid " + c + "33}")
        out.append(".bar-" + cls + "{background:" + c + "55}")
    return "\n".join(out)


def esc(text) -> str:
    return html.escape(str(text if text is not None else ""))


def pill(label: str) -> str:
    return f'<span class="pill {css_class(label)}">{esc(label)}</span>'


def clip(value: str, limit: int) -> str:
    """A cut string ends in an ellipsis, so a cut is not read as a bug."""
    text = str(value)
    return text if len(text) <= limit else text[:limit].rstrip() + "\u2026"


def render_meta(trace) -> None:
    bits = []
    for f in trace.fields:
        if not f.is_empty:
            bits.append((f.label, f.value))
    for k, v in (trace.meta or {}).items():
        if v not in (None, ""):
            bits.append((k, v))
    if not bits:
        return
    cells = "".join(f'<div><div class="meta-k">{esc(k)}</div>'
                    f'<div class="meta-v">{esc(clip(v, 220))}</div></div>'
                    for k, v in bits)
    st.markdown(f'<div class="meta-row">{cells}</div>', unsafe_allow_html=True)


def pin_meta(trace, limit: int = 8) -> None:
    """The run's question and answer, in the sidebar, where they stay in view."""
    bits = [(f.label, f.value) for f in trace.fields if not f.is_empty]
    bits += [(k, v) for k, v in (trace.meta or {}).items() if v not in (None, "")]
    if not bits:
        return
    rows = "".join(f'<div class="pin-k">{esc(k)}</div>'
                   f'<div class="pin-v">{esc(clip(v, 150))}</div>'
                   for k, v in bits[:limit])
    st.sidebar.markdown(f'<div class="pin-box">{rows}</div>', unsafe_allow_html=True)


def _head(unit, rec, schema, open_: bool, wanted: bool = False) -> str:
    chips = []
    for value in (rec.get("labels") or {}).values():
        if value:
            chips.append(pill(str(value)))
    why = rec.get("reason", "")
    tail = (f'<span class="unit-why">{esc(clip(why, 90))}</span>'
            if why and not open_ and not wanted else "")
    src = ""
    if rec.get("source") == "llm" and any((rec.get("labels") or {}).values()):
        src = '<span class="src src-llm">LLM</span>'
    if not chips and wanted:
        chips = ['<span class="todo">needs an answer</span>']
    return (f'<div class="unit-head"><span class="unit-title">{esc(unit.title)}</span>'
            f'<span class="unit-kind {kind_class(unit.kind)}">{esc(unit.kind)}</span>'
            + "".join(chips) + src + tail
            + f'<span class="unit-key">{esc(unit.key)}</span></div>')


def indent(unit) -> str:
    """The rails drawn to the left of a nested step."""
    return '<div class="rail"></div>' * max(0, getattr(unit, "depth", 0))


def render_unit(unit, schema, rec: dict | None = None, open_: bool = True,
                wanted: bool = False) -> None:
    """One step. Answered steps collapse to a single line, so a long trace
    stays readable while the step in hand keeps its evidence."""
    rec = rec or {}
    first = next((v for v in (rec.get("labels") or {}).values() if v), None)
    bar = ("sev-" + css_class(str(first))) if first \
        else ("bar-" + kind_class(unit.kind))

    parts = [f'<div class="nest">{indent(unit)}',
             f'<div class="unit{"" if open_ else " done"}'
             f'{" unit-open" if open_ else ""}" style="flex:1;min-width:0">',
             f'<div class="sev {bar}"></div>', '<div class="unit-body">',
             _head(unit, rec, schema, open_, wanted)]
    if open_:
        for f in unit.fields:
            if f.is_empty:
                continue
            parts.append(f'<div class="slot slot-{esc(f.style)}">'
                         f'<div class="slot-label">{esc(f.label)}</div>'
                         f'<div class="slot-body">{esc(f.value)}</div></div>')
    parts.append("</div></div></div>")
    st.markdown("".join(parts), unsafe_allow_html=True)


def render_review_row(unit, schema, rec: dict) -> None:
    """One answered step, as a single readable row."""
    rec = rec or {}
    labels = [v for v in (rec.get("labels") or {}).values() if v]
    first = labels[0] if labels else None
    bar = ("sev-" + css_class(str(first))) if first \
        else ("bar-" + kind_class(unit.kind))

    chips = " ".join(pill(str(v)) for v in labels)
    if not chips:
        chips = '<span class="rv-none">not answered</span>'

    src = rec.get("source", "human")
    tag = (f'<span class="rv-src src-{"llm" if src == "llm" else "human"}">'
           f'{esc("model" if src == "llm" else "annotator")}</span>') if labels else ""
    why = f'<div class="rv-why">{esc(rec.get("reason", ""))}</div>' if rec.get("reason") else ""

    st.markdown(
        f'<div class="nest">{indent(unit)}'
        f'<div class="rv" style="flex:1;min-width:0">'
        f'<div class="rv-bar {bar}"></div><div class="rv-body">'
        f'<div class="rv-top"><span class="rv-title">{esc(unit.title)}</span>'
        f'<span class="unit-kind {kind_class(unit.kind)}">{esc(unit.kind)}</span>{chips}{tag}</div>'
        f'{why}</div></div></div>', unsafe_allow_html=True)


def reason_box(value: str, key: str, placeholder: str = "", container=None) -> str:
    """The free-text reason. Same rule as `ask`: once the key holds a value,
    passing a default as well makes Streamlit warn."""
    box = container if container is not None else st
    extra = {} if key in st.session_state else {"value": value}
    return box.text_area("Why?", key=key, placeholder=placeholder,
                         label_visibility="collapsed", height=70, **extra)


def ask(question, answers: dict, key: str, container=None):
    """One question as a radio. Returns the label, or None.

    A radio shows every option at once, which is one click per answer. The
    earlier build used a dropdown, which is two.

    An answer whose label the question no longer offers is shown as a kept
    option rather than dropped. Without this, renaming a label silently
    deleted every answer that used the old name.
    """
    box = container if container is not None else st
    current = (answers or {}).get(question.id)
    options = list(question.labels)
    if current and current not in options:
        options.append(str(current))

    # Streamlit warns when a widget is given both a default and a session-state
    # value, which happens the moment the model fills an answer in. Once the key
    # holds a value that value is the truth, so no default is passed.
    extra = {}
    if key not in st.session_state:
        extra["index"] = options.index(current) + 1 if current in options else 0

    got = box.radio(question.prompt, ["—"] + options, key=key, horizontal=True,
                    format_func=lambda v: (f"{v} (old)" if v not in question.labels
                                           and v != "—" else v),
                    **extra)
    return None if got == "—" else got

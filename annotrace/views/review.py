"""Read the work back, and export it.

Read-only until the reader opts in, so the link is safe to send to someone who
should look but not change anything.
"""

import json
import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import streamlit as st                              # noqa: E402

from core import adapter, schema, store, ui         # noqa: E402

adapter.load_all()

traces = st.session_state.get("traces") or []
raw_schema = st.session_state.get("schema")
if not traces or not raw_schema:
    ui.inject_css()
    st.title("Review")
    st.info("No traces loaded. Begin on the **Traces** page.")
    st.stop()

sch = schema.parse(raw_schema)
kinds = st.session_state.get("kinds") or []
ui.inject_css(sch, kinds={u.kind for t in traces for u in t.units})
st.session_state.setdefault("annotations", {})
ann = st.session_state["annotations"]

with st.sidebar:
    editable = st.toggle("Enable editing", value=False,
                         help="Disabled by default, so the page can be shared "
                              "safely.")
    done, total = store.progress(traces, sch, kinds, ann)
    st.progress(done / total if total else 0.0,
                text=f"{done} of {total} complete")

    for label, n in sorted(store.tallies(sch, ann).items(), key=lambda kv: -kv[1]):
        st.markdown(f"{ui.pill(label)} &nbsp;{n}", unsafe_allow_html=True)
    src = store.sources(ann)
    if src:
        st.caption(" · ".join(f"{k} {v}" for k, v in sorted(src.items())))

    st.divider()
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    payload = store.build_payload(sch, st.session_state.get("adapter_id", ""),
                                  st.session_state.get("trace_path", ""), kinds,
                                  traces, ann)
    st.download_button("Export JSON", json.dumps(payload, indent=2),
                       f"annotations_{stamp}.json", use_container_width=True)
    st.download_button("Export CSV", store.to_csv(sch, traces, ann),
                       f"annotations_{stamp}.csv", use_container_width=True)

    up = st.file_uploader("Open a saved file", type=["json"])
    if up is not None and st.button("Open", use_container_width=True):
        try:
            loaded = store.read_payload(json.load(up))
        except (json.JSONDecodeError, AttributeError) as e:
            st.error(f"This file could not be read: {e}")
            loaded = {}
        known = {t.id for t in traces}
        matched = {k: v for k, v in loaded.items() if k in known}
        ann.update(matched)
        st.success(f"Loaded {len(matched)} of {len(loaded)} traces.")

    only_done = st.checkbox("Only annotated traces", value=False)

shown = [t for t in traces if not only_done or ann.get(t.id)]
if not shown:
    st.info("No traces match that filter.")
    st.stop()

pos = min(st.session_state.get("review_pos", 0), len(shown) - 1)
c = st.columns([0.6, 6, 0.6])
if c[0].button("←", use_container_width=True, disabled=pos == 0):
    st.session_state["review_pos"] = pos - 1
    st.rerun()
pick = c[1].selectbox("Trace", range(len(shown)), index=pos,
                      format_func=lambda i: f"{i + 1}. {shown[i].title[:80]}",
                      label_visibility="collapsed")
if pick != pos:
    st.session_state["review_pos"] = pick
    st.rerun()
if c[2].button("→", use_container_width=True, disabled=pos >= len(shown) - 1):
    st.session_state["review_pos"] = pos + 1
    st.rerun()

trace = shown[pos]
records = ann.setdefault(trace.id, {})

unknown = store.unknown_labels(sch, ann)
if unknown:
    st.markdown('<div class="warnbox">These labels are from an earlier set and '
                'have been kept: '
                + ", ".join(f"<b>{ui.esc(k)}</b> ({v})" for k, v in unknown.items())
                + "</div>", unsafe_allow_html=True)

ui.render_meta(trace)

todo_keys = {u.key for u in store.steps_to_do(trace, sch, kinds)}
for unit in trace.units:
    rec = records.get(unit.key) or store.blank()

    if not editable:
        if unit.key in todo_keys:
            ui.render_review_row(unit, sch, rec)      # one readable row per step
        else:
            ui.render_unit(unit, sch, rec, open_=False)
        continue

    ui.render_unit(unit, sch, rec, open_=unit.key in todo_keys)
    if unit.key not in todo_keys:
        continue
    with st.container(key=f"answerbar-d{unit.depth}-{unit.key}"):
        labels = dict(rec.get("labels") or {})
        applicable = sch.for_kind(unit.kind)
        cols = st.columns(len(applicable))
        for i, q in enumerate(applicable):
            if not q.visible(labels):
                labels.pop(q.id, None)
                continue
            got = ui.ask(q, labels, f"r_{trace.id}_{unit.key}_{q.id}", cols[i])
            if got is None:
                labels.pop(q.id, None)
            else:
                labels[q.id] = got
        reason = rec.get("reason", "")
        if sch.ask_reason:
            reason = ui.reason_box(reason, f"rw_{trace.id}_{unit.key}")
        if (labels != (rec.get("labels") or {})
                or reason != rec.get("reason", "")):
            records[unit.key] = {"labels": labels, "reason": reason,
                                 "source": "human"}

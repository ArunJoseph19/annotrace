"""Load a file and look at what is in it.

Before any question is written, the annotator should see the shape of their own
data: how a run is broken into steps, what each kind of step carries, and how
those steps nest. Everything here is read-only.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import streamlit as st                      # noqa: E402

from core import adapter, ui                # noqa: E402

adapter.load_all()
ui.inject_css()
HERE = os.path.dirname(os.path.abspath(__file__))
UPLOAD_DIR = os.path.join(HERE, "..", "uploads")

st.title("Traces")

# ── load ──────────────────────────────────────────────────────────────────

tab_path, tab_upload = st.tabs(["From a path", "Upload a file"])
path = None
with tab_path:
    typed = st.text_input("Path to a trace file",
                          value=st.session_state.get("trace_path", ""),
                          placeholder="analysis/batches/batch_30/batch.jsonl")
    if typed:
        # a pasted path often carries a space, a newline, or shell quoting
        path = os.path.expanduser(typed.strip().strip("'\"").strip())
with tab_upload:
    up = st.file_uploader("Trace file", type=["json", "jsonl"])
    if up is not None:
        os.makedirs(UPLOAD_DIR, exist_ok=True)
        dest = os.path.join(UPLOAD_DIR, up.name)
        with open(dest, "wb") as f:
            f.write(up.getbuffer())
        path = dest

if path and path != st.session_state.get("trace_path"):
    if not os.path.exists(path):
        st.error(f"No such file: {path}")
        parent = os.path.dirname(path) or "."
        if os.path.isdir(parent):
            here = sorted(f for f in os.listdir(parent) if f.endswith((".json", ".jsonl")))
            st.caption(("Trace files in this folder: " + ", ".join(here[:12])) if here
                       else f"{parent} has no .json or .jsonl files.")
    else:
        reader, _ = adapter.detect(path)
        if reader is None:
            st.warning("No reader recognised this file.")
        else:
            try:
                loaded = reader.load(path)
            except Exception as e:              # a bad file must not crash the page
                st.error(f"This file could not be read: {e}")
                loaded = []
            if loaded:
                st.session_state.update(traces=loaded, trace_path=path,
                                        adapter_id=reader.id, pos=0, view=0)
                st.session_state.setdefault("annotations", {})
                st.rerun()
            else:
                st.error("No traces found in this file.")

traces = st.session_state.get("traces") or []
ui.inject_css(kinds={u.kind for t in traces for u in t.units})
if not traces:
    st.info("Select a trace file to see what is in it.")
    st.stop()

reader = adapter.get(st.session_state.get("adapter_id", ""))
kinds = sorted({u.kind for t in traces for u in t.units})
counts = {k: sum(1 for t in traces for u in t.units if u.kind == k) for k in kinds}

st.success(f"**{os.path.basename(st.session_state['trace_path'])}** read as "
           f"**{reader.name if reader else 'unknown'}**")

m = st.columns(2 + len(kinds))
m[0].metric("Runs", len(traces))
m[1].metric("Steps", sum(len(t.units) for t in traces))
for col, kind in zip(m[2:], kinds):
    col.metric(kind, counts[kind])

with st.expander("What each kind of step carries"):
    for kind in kinds:
        names, samples = [], {}
        for t in traces:
            for u in t.units:
                if u.kind != kind:
                    continue
                for f in u.fields:
                    if f.name not in names:
                        names.append(f.name)
                    if f.name not in samples and not f.is_empty:
                        samples[f.name] = f.value
        st.markdown(f"**`{kind}`** — {counts[kind]} steps")
        for n in names:
            st.caption(f"`{n}` — {ui.esc(samples.get(n, ''))[:150]}")
        st.write("")

st.divider()

# ── look at one ───────────────────────────────────────────────────────────

view = min(st.session_state.get("view", 0), len(traces) - 1)
c = st.columns([0.6, 7, 0.6])
if c[0].button("←", use_container_width=True, disabled=view == 0):
    st.session_state["view"] = view - 1
    st.rerun()
pick = c[1].selectbox("Run", range(len(traces)), index=view,
                      format_func=lambda i: f"{i + 1}. {traces[i].title[:90]}",
                      label_visibility="collapsed")
if pick != view:
    st.session_state["view"] = pick
    st.rerun()
if c[2].button("→", use_container_width=True, disabled=view >= len(traces) - 1):
    st.session_state["view"] = view + 1
    st.rerun()

trace = traces[view]
ui.render_meta(trace)
st.caption(f"{len(trace.units)} steps. Indented steps belong to the step above them.")
for u in trace.units:
    ui.render_unit(u, None, {}, open_=True)

st.divider()
left, right = st.columns([1, 3])
if left.button("Next: write the questions  →", type="primary",
               use_container_width=True):
    st.switch_page("views/questions.py")
right.caption("Nothing here is annotated yet. The next page is where you decide "
              "what to ask about these steps.")

"""Compare two sets of annotations of the same traces.

Raw agreement and Cohen's kappa per question, then the steps where the two
disagreed. Either side can be the work in this session, so a person can check
themselves against a colleague or against the model without exporting first.
"""

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import streamlit as st                              # noqa: E402

from core import adapter, compare, schema, store, ui  # noqa: E402

adapter.load_all()
ui.inject_css()

st.title("Compare")
st.caption("Two people annotating the same traces will not agree on everything. "
           "This says how far apart they are, and on exactly which steps.")

raw_schema = st.session_state.get("schema")
mine = st.session_state.get("annotations") or {}
sch = schema.parse(raw_schema) if raw_schema else None


def read_upload(f):
    try:
        doc = json.load(f)
    except (json.JSONDecodeError, AttributeError) as e:
        st.error(f"This file could not be read: {e}")
        return None, None
    return store.read_payload(doc), doc.get("schema")


left, right = st.columns(2)
sources: list = [None, None]
names = ["A", "B"]

for i, col in enumerate((left, right)):
    with col:
        st.subheader(names[i])
        use_mine = st.checkbox("Use the work in this session", key=f"mine_{i}",
                               value=(i == 0 and bool(mine)),
                               disabled=not mine)
        if use_mine:
            sources[i] = (mine, raw_schema, "this session")
        else:
            f = st.file_uploader("Annotation file", type=["json"], key=f"file_{i}")
            typed = st.text_input("or a path to one", key=f"path_{i}",
                                  placeholder="annotations/run_b.json")
            if f is not None:
                data, file_schema = read_upload(f)
                if data is not None:
                    sources[i] = (data, file_schema, f.name)
            elif typed.strip():
                # a pasted path often carries a space, a newline, or shell quoting
                path = os.path.expanduser(typed.strip().strip("'\"").strip())
                if not os.path.exists(path):
                    st.error(f"No such file: {path}")
                else:
                    with open(path, encoding="utf-8") as fh:
                        data, file_schema = read_upload(fh)
                    if data is not None:
                        sources[i] = (data, file_schema, os.path.basename(path))
        if sources[i]:
            data, _, label = sources[i]
            st.caption(f"**{label}** · {len(data)} traces · "
                       f"{sum(len(u) for u in data.values())} steps")

if not (sources[0] and sources[1]):
    st.info("Give two sets of annotations. Either can be the work in this session.")
    st.stop()

# the questions come from whichever side declares them, so a label is named
# rather than shown as a bare id. When neither side is this session, the
# session's own questions say nothing about these files, so the files' win.
if not any(label == "this session" for _, _, label in sources):
    sch = None
for _, file_schema, _ in sources:
    if sch is None and file_schema:
        sch = schema.parse(file_schema)
if sch is None:
    st.error("Neither file carries its questions, so there is nothing to compare "
             "them against.")
    st.stop()

ui.inject_css(sch)
report = compare.compare(sources[0][0], sources[1][0], sch.questions)

if not report.steps_both:
    st.warning("These two do not share a single step. They were probably made "
               "from different trace files.")
    st.stop()

st.divider()

m = st.columns(4)
m[0].metric("Steps in both", report.steps_both)
m[1].metric("Answers compared", report.answers_compared)
m[2].metric("Agreement", f"{report.overall_raw * 100:.0f}%")
m[3].metric("Disagreements", len(report.disagreements))

st.subheader("By question")
for q in report.questions:
    if not q.both:
        st.caption(f"**{q.prompt}** — not answered by both, nothing to compare.")
        continue
    c = st.columns([3, 1, 1, 3])
    c[0].markdown(f"**{q.prompt}**")
    c[1].metric("Agreement", f"{q.raw * 100:.0f}%")
    c[2].metric("Kappa", f"{q.kappa:.2f}")
    with c[3]:
        st.caption(f"{compare.strength(q.kappa)} · {q.same} of {q.both} answers match")
        for a, b, n in q.confusions[:4]:
            st.markdown(f"{ui.pill(a)} &rarr; {ui.pill(b)} &nbsp;{n}",
                        unsafe_allow_html=True)
    st.write("")

st.caption("Kappa takes out the agreement expected by chance. Two annotators who "
           "both answer the same label most of the time will agree often without "
           "agreeing meaningfully.")

st.divider()
st.subheader(f"Where they differ ({len(report.disagreements)})")
st.caption(f"**A** is {sources[0][2]}. **B** is {sources[1][2]}. "
           "Each row gives the run, the step, the question and what each side "
           "said, with the reason if one was written.")

if not report.disagreements:
    st.success("They agree on every answer they both gave.")
else:
    asked = [q.question_id for q in report.questions if q.both]
    by_q = st.multiselect("Questions", asked, default=asked)
    shown = [d for d in report.disagreements if d.question_id in by_q]
    st.caption(f"{len(shown)} shown")
    # A trace id and a unit key say nothing about what was disagreed over. The
    # loaded traces carry the run's question and each step's title, so they are
    # looked up when they are there.
    titles = {t.id: t.title for t in (st.session_state.get("traces") or [])}
    steps = {(t.id, u.key): u
             for t in (st.session_state.get("traces") or []) for u in t.units}
    prompts = {q.id: q.prompt for q in sch.questions}
    side_a, side_b = sources[0][2], sources[1][2]

    for d in shown[:200]:
        unit = steps.get((d.trace_id, d.unit_key))
        run = titles.get(d.trace_id, d.trace_id)
        head = unit.title if unit else d.unit_key
        kind = f'<span class="unit-kind {ui.kind_class(unit.kind)}">' \
               f'{ui.esc(unit.kind)}</span>' if unit else ""
        with st.container(border=True):
            st.markdown(
                f'<div class="cmp-run">{ui.esc(ui.clip(run, 110))}</div>'
                f'<div class="cmp-head"><span class="cmp-step">{ui.esc(head)}</span>'
                f'{kind}<span class="cmp-q">{ui.esc(prompts.get(d.question_id, d.question_id))}</span>'
                f'<span class="unit-key">{ui.esc(d.unit_key)}</span></div>',
                unsafe_allow_html=True)
            for name, label, value, recs in (
                    ("A", side_a, d.a, sources[0][0]),
                    ("B", side_b, d.b, sources[1][0])):
                why = (recs.get(d.trace_id, {}).get(d.unit_key, {}) or {}).get("reason", "")
                st.markdown(
                    f'<div class="cmp-side"><span class="cmp-tag">{name}</span>'
                    f'<span class="cmp-src">{ui.esc(label)}</span>'
                    f'{ui.pill(value)}'
                    f'<span class="cmp-why">{ui.esc(why) if why else "no reason given"}</span>'
                    f'</div>', unsafe_allow_html=True)
    if len(shown) > 200:
        st.caption(f"{len(shown) - 200} more not shown.")

    rows = ["trace_id,unit_key,question,a,b"]
    rows += [f'"{d.trace_id}","{d.unit_key}","{d.question_id}","{d.a}","{d.b}"'
             for d in shown]
    st.download_button("Export the disagreements", "\n".join(rows),
                       "disagreements.csv")

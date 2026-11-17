"""Read each step, pick a label, say why.

The whole trace stays in view. Answered steps collapse to one line, so the
earlier steps remain as context without filling the screen.
"""

import json
import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import streamlit as st                                    # noqa: E402

from core import adapter, llm, models, prompt, schema, store, ui  # noqa: E402

adapter.load_all()
DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data")

traces = st.session_state.get("traces") or []
raw_schema = st.session_state.get("schema")
if not traces or not raw_schema:
    ui.inject_css()
    st.title("Annotate")
    st.info("No traces loaded. Begin on the **Traces** page.")
    st.stop()

sch = schema.parse(raw_schema)
kinds = st.session_state.get("kinds") or []
ui.inject_css(sch, kinds={u.kind for t in traces for u in t.units})
st.session_state.setdefault("annotations", {})
ann = st.session_state["annotations"]

# A reload empties this page, and the answers are on disk. They are offered
# back, never loaded on their own: an earlier build restored them silently and
# a recording filled with answers nobody had given in that take.
# The test is "no answers yet", not "no entries": drawing a trace adds an empty
# entry for it, which would make this look like work in progress on the very
# next rerun and take the offer away before it could be clicked.
resume = None
if not any(store.answered(r) for recs in ann.values() for r in recs.values()):
    prior = store.load_session(store.session_path(
        DATA_DIR, st.session_state.get("user", "anon")))
    want = os.path.basename(st.session_state.get("trace_path", "") or "")
    if prior and prior.get("traces") and prior.get("source_file") == want:
        resume = prior
# answering one of these changes which follow-ups are shown
TRIGGERS = {q.ask_if["question"] for q in sch.questions if q.ask_if}


def save():
    payload = store.build_payload(sch, st.session_state.get("adapter_id", ""),
                                  st.session_state.get("trace_path", ""), kinds,
                                  traces, ann)
    store.save_session(store.session_path(DATA_DIR,
                                          st.session_state.get("user", "anon")), payload)


# ── sidebar ───────────────────────────────────────────────────────────────

pos = min(st.session_state.get("pos", 0), len(traces) - 1)
trace = traces[pos]
records = ann.setdefault(trace.id, {})

with st.sidebar:
    ui.pin_meta(trace)
    done, total = store.progress(traces, sch, kinds, ann)
    st.progress(done / total if total else 0.0,
                text=f"{done} of {total} traces complete")
    started = sum(1 for t in traces
                  if (ann.get(t.id) or {}) and not store.trace_done(t, sch, kinds,
                                                                    ann.get(t.id) or {}))
    if started:
        st.caption(f"{started} more started but unfinished. "
                   "Next unanswered goes to the first of them.")

    if resume:
        n = sum(len(t["steps"]) for t in resume["traces"])
        when = resume.get("exported_at", "")[:16].replace("T", " ")
        st.caption(f"{n} answers were saved on {when}.")
        if st.button("Load them", use_container_width=True, key="resume_load"):
            st.session_state["annotations"] = store.read_payload(resume)
            st.rerun()
        if st.button("Discard them", use_container_width=True, key="resume_drop"):
            store.save_session(store.session_path(
                DATA_DIR, st.session_state.get("user", "anon")),
                store.build_payload(sch, "", "", kinds, [], {}))
            st.rerun()

    st.divider()
    ids = models.ids()
    current = st.session_state.get("llm_model", models.DEFAULT)
    st.session_state["llm_model"] = st.selectbox(
        "Model", ids, index=ids.index(current) if current in ids else ids.index(models.DEFAULT),
        format_func=models.label,
        help="$ is cheapest, $$$ is dearest.")
    asked = st.session_state.get("_asked", "")
    with st.container(key=f"askbox-{asked or 'idle'}"):
        ask_llm = st.button("Ask the model", use_container_width=True,
                            type="primary")
    if asked == "empty":
        st.caption("Nothing usable came back for these questions.")

    note = st.session_state.pop("_note", "")
    if note.startswith("error:"):
        st.error(note[6:].strip())
    elif note:
        st.caption(note)

    unknown = store.unknown_labels(sch, ann)
    if unknown:
        st.warning("Kept from an earlier set of labels: "
                   + ", ".join(f"{k} ({v})" for k, v in unknown.items()))

    spend = llm.LAST_USAGE
    if spend.get("cost") is not None:
        left = spend.get("remaining")
        # a pair of dollar signs is read as LaTeX by Streamlit's markdown
        st.caption(f"\\${spend['cost']:.4f} spent"
                   + (f" · \\${left:.2f} left" if left is not None else ""))

    st.divider()
    st.text_input("Your name", key="user",
                  placeholder="keeps your saved work separate")
    src = store.sources(ann)
    if src:
        st.caption(" · ".join(
            f"{v} from the model" if k == "llm" else f"{v} from you"
            for k, v in sorted(src.items())))
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    payload = store.build_payload(sch, st.session_state.get("adapter_id", ""),
                                  st.session_state.get("trace_path", ""), kinds,
                                  traces, ann)
    st.download_button("Export JSON", json.dumps(payload, indent=2),
                       f"annotations_{stamp}.json", use_container_width=True)
    st.download_button("Export CSV", store.to_csv(sch, traces, ann),
                       f"annotations_{stamp}.csv", use_container_width=True)

    with st.popover("Clear all answers", use_container_width=True):
        n = sum(1 for recs in ann.values() for r in recs.values()
                if store.answered(r))
        st.caption(f"This removes {n} answers across {len(ann)} traces. "
                   "Export first if you want to keep them.")
        if st.button("Yes, clear them", type="primary", use_container_width=True):
            # the controls hold their own values, so the records alone are not
            # enough: the widgets have to go too
            for key in [k for k in list(st.session_state) if isinstance(k, str)
                        and k.startswith(("a_", "w_"))]:
                del st.session_state[key]
            st.session_state["annotations"] = {}
            st.session_state.pop("_asked", None)
            save()
            st.rerun()

def goto(where: int) -> None:
    st.session_state["pos"] = where
    st.session_state.pop("_asked", None)
    st.rerun()


# ── header ────────────────────────────────────────────────────────────────

c = st.columns([0.6, 6, 0.6, 1.8])
if c[0].button("←", use_container_width=True, disabled=pos == 0, key="prev_top"):
    goto(pos - 1)
# the count is written after the steps are drawn, so it reflects the answer
# just given rather than the one before it
header = c[1].empty()
if c[2].button("→", use_container_width=True, disabled=pos >= len(traces) - 1,
               key="next_top"):
    goto(pos + 1)
if c[3].button("Next unanswered", use_container_width=True, key="unans_top"):
    goto(store.next_unanswered(traces, sch, kinds, ann, pos))

todo = store.steps_to_do(trace, sch, kinds)

if ask_llm:
    try:
        system = (st.session_state.get("prompt_override")
                  or prompt.system_prompt(sch, "",
                                          st.session_state.get("llm_guidance", "")))
        reply = llm.complete(system,
                             prompt.user_prompt(trace, {u.key for u in todo}),
                             st.session_state.get("llm_model", models.DEFAULT),
                             "", 3000)
        got = prompt.parse(reply, sch, trace)
        n = 0
        for key, suggestion in got.items():
            rec = records.get(key)
            # a suggestion never overwrites a decision a person made
            if rec and rec.get("source") == "human" and store.answered(rec):
                continue
            records[key] = {"labels": suggestion["labels"],
                            "reason": suggestion["reason"],
                            "source": "llm"}
            n += 1
        # A widget keeps its own value across a rerun, so writing the record
        # alone left every control showing what it showed before. Clearing the
        # key is not enough either: the browser sends the old value straight
        # back. The controls are set to the answers instead.
        kinds_by_key = {u.key: u.kind for u in trace.units}
        for key, suggestion in got.items():
            if records.get(key, {}).get("source") != "llm":
                continue                       # a person's answer was left alone
            for q in sch.for_kind(kinds_by_key.get(key, "")):
                st.session_state[f"a_{trace.id}_{key}_{q.id}"] = \
                    suggestion["labels"].get(q.id, "—")
            if sch.ask_reason:
                st.session_state[f"w_{trace.id}_{key}"] = suggestion.get("reason", "")
        st.session_state["_asked"] = "ok" if n else "empty"
        save()
    except llm.LLMError as e:
        st.session_state["_asked"] = "error"
        st.session_state["_note"] = f"error: {e}"
    st.rerun()

# ── the steps ─────────────────────────────────────────────────────────────

todo_keys = {u.key for u in todo}
for unit in trace.units:
    rec = records.get(unit.key) or store.blank()
    if unit.key not in todo_keys:
        ui.render_unit(unit, sch, rec, open_=False)      # context, not asked about
        continue

    # the card is drawn into a slot reserved above the controls, and filled once
    # the answers are known, so its colour follows the choice on the same pass
    slot = st.container()
    # A step collapses once a person decides it, not once it has any answer.
    # The model answers every step at once, and its answer is the thing that
    # most needs reading, so collapsing on that hid the evidence to check it.
    open_ = not (store.answered(rec) and rec.get("source") == "human")

    with st.container(key=f"answerbar-d{unit.depth}-{unit.key}"):
        # answers are gathered as the questions are drawn, so a follow-up sees
        # the choice just made and appears in the same pass. Re-running the page
        # to reveal it made every click reload the screen.
        labels = dict(rec.get("labels") or {})
        applicable = sch.for_kind(unit.kind)
        cols = st.columns(len(applicable))
        for i, q in enumerate(applicable):
            if not q.visible(labels):
                labels.pop(q.id, None)
                continue
            got = ui.ask(q, labels, f"a_{trace.id}_{unit.key}_{q.id}", cols[i])
            if got is None:
                labels.pop(q.id, None)
            else:
                labels[q.id] = got

        reason = rec.get("reason", "")
        if sch.ask_reason:
            reason = ui.reason_box(reason, f"w_{trace.id}_{unit.key}",
                                   "Reason for this label (optional)")

        if (labels != (rec.get("labels") or {})
                or reason != rec.get("reason", "")):
            records[unit.key] = {"labels": labels, "reason": reason,
                                 "source": "human"}
            save()

    shown = {"labels": labels, "reason": reason, "source": rec.get("source", "human")}
    with slot:
        ui.render_unit(unit, sch, shown, open_=open_, wanted=True)
    st.write("")

wanted_steps = store.steps_to_do(trace, sch, kinds)
missing = [u for u in wanted_steps if not store.answered(records.get(u.key))]
header.markdown(
    f"**Trace {pos + 1} of {len(traces)}** &nbsp;·&nbsp; "
    f"{len(wanted_steps) - len(missing)} of {len(wanted_steps)} steps answered"
    f" &nbsp;·&nbsp; {ui.esc(ui.clip(trace.title, 58))}")
if missing:
    st.markdown('<div class="warnbox">' + str(len(missing))
                + ' step' + ('s' if len(missing) > 1 else '')
                + ' on this trace have no answer: '
                + ", ".join(f"<b>{ui.esc(u.key)}</b>" for u in missing[:8])
                + ("" if len(missing) <= 8 else " and more")
                + "</div>", unsafe_allow_html=True)

# ── footer ────────────────────────────────────────────────────────────────

st.divider()
f = st.columns([1.4, 4.4, 1.8, 1.4])
if f[0].button("← Previous", use_container_width=True, disabled=pos == 0,
               key="prev_end"):
    goto(pos - 1)
if f[2].button("Next unanswered", use_container_width=True, key="unans_end"):
    goto(store.next_unanswered(traces, sch, kinds, ann, pos))
if f[3].button("Next →", use_container_width=True, type="primary",
               disabled=pos >= len(traces) - 1, key="next_end"):
    goto(pos + 1)

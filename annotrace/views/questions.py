"""Load a file, decide what to ask, then annotate.

Three sections and a button. Which steps get annotated is not asked separately:
each question already says which kinds of step it applies to, so asking twice
was asking the same thing twice.
"""

import json
import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import streamlit as st                                            # noqa: E402

from core import (adapter, llm, models, prompt, schema, store,   # noqa: E402
                  suggest, ui)

adapter.load_all()

HERE = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(HERE, "..", "data")

TEMPLATE = [
    {"id": "correct", "prompt": "Was this step correct?",
     "labels": ["Yes", "No"], "applies_to": [], "ask_if": None},
]

def set_questions(new, rules=None):
    """Replace the questions and clear the widgets that showed the old ones.

    A Streamlit text box with a fixed key keeps its own value, so replacing the
    questions behind it left the boxes showing one set of labels and the pills
    another.
    """
    st.session_state["questions"] = new
    if rules is not None:
        st.session_state["llm_guidance"] = rules
    for key in [k for k in st.session_state
                if k.startswith(("qp_", "ql_", "qk_", "qc_", "qt_", "qv_"))]:
        del st.session_state[key]
    st.session_state.pop("prompt_override", None)
    st.session_state.pop("prompt_box", None)


st.session_state.setdefault("questions", [dict(q) for q in TEMPLATE])
questions = st.session_state["questions"]
ui.inject_css(labels=[l for q in questions for l in (q.get("labels") or [])],
              kinds={u.kind for t in (st.session_state.get("traces") or [])
                     for u in t.units})

st.title("Questions")

traces = st.session_state.get("traces") or []
if not traces:
    st.info("No traces loaded. Start on the **Traces** page.")
    st.stop()

kinds_present = sorted({u.kind for t in traces for u in t.units})
counts = {k: sum(1 for t in traces for u in t.units if u.kind == k) for k in kinds_present}

# a step that contains finer steps would be annotated twice over
contained = {u.meta.get("contains") for t in traces for u in t.units
             if u.meta.get("contains")}
coarse = sorted({u.kind for t in traces for u in t.units
                 if u.meta.get("contains") in kinds_present})
if coarse:
    st.caption("Each **" + "**, **".join(coarse) + "** contains finer steps ("
               + ", ".join(sorted(contained)) + "), so it is left unticked below. "
               "Tick it instead to annotate at the coarser level.")

# ── the questions ──────────────────────────────────────────────────────

st.subheader("1 · Your questions")
st.caption("Define your own labels, or ask the model to propose labels based "
           "on your traces.")

with st.container(border=True):
    g = st.columns([4, 1.2, 1.3], vertical_alignment="bottom")
    goal = g[0].text_input("What are you trying to identify? (optional)",
                           st.session_state.get("goal", ""),
                           placeholder="which step caused the run to give a wrong answer")
    st.session_state["goal"] = goal
    ids = models.ids()
    chosen_model = g[1].selectbox(
        "Model", ids, index=ids.index(models.DEFAULT),
        format_func=models.label,
        help="$ is cheapest, $$$ is dearest. The same model answers here and "
             "when annotating.")
    st.session_state["llm_model"] = chosen_model
    if g[2].button("Propose labels", use_container_width=True):
        try:
            got, rules, why = suggest.propose(traces, None, chosen_model, "", goal)
            set_questions(got, rules)
            st.session_state["_why"] = why
            st.rerun()
        except llm.LLMError as e:
            st.error(str(e))
    st.caption("The model reads a sample of your steps. It cannot know your "
               "purpose unless you state it, so this line changes the result "
               "significantly.")

why = st.session_state.pop("_why", "")
if why:
    st.info(f"Labels proposed. {why} The instructions below were written to "
            "match them. Edit as required.")

questions = st.session_state["questions"]

# labels change often -- a proposal, an edit -- and a condition naming one that
# has gone would silently never fire
stale = []
for i, q in enumerate(questions):
    cond = q.get("ask_if")
    if not cond:
        continue
    src = next((x for x in questions[:i] if x["id"] == cond.get("question")), None)
    want = cond.get("equals") or []
    want = want if isinstance(want, list) else [want]
    kept = [v for v in want if src and v in (src.get("labels") or [])]
    if src is None or not kept:
        stale.append(q.get("prompt") or q["id"])
        q["ask_if"] = None
    elif kept != want:
        q["ask_if"] = {"question": cond["question"], "equals": kept}
if stale:
    st.warning("The labels changed, so the condition on **"
               + "**, **".join(stale) + "** no longer matched any answer. "
               "It has been cleared. Set it again below if required.")

for i, q in enumerate(questions):
    with st.container(border=True):
        top = st.columns([3, 2])
        q["prompt"] = top[0].text_input("Question", q.get("prompt", ""), key=f"qp_{i}")
        raw = top[1].text_area("Labels, one per line",
                               "\n".join(q.get("labels") or []), key=f"ql_{i}",
                               height=110)
        q["labels"] = [x.strip() for x in raw.splitlines() if x.strip()]
        if q["labels"]:
            st.markdown(" ".join(ui.pill(l) for l in q["labels"]),
                        unsafe_allow_html=True)

        st.markdown("<div style='font-size:.82rem;color:#8b8981;margin-top:6px'>"
                    "Apply this question to</div>", unsafe_allow_html=True)
        cur = q.get("applies_to") or []
        cols = st.columns(len(kinds_present))
        picked = []
        for j, kind in enumerate(kinds_present):
            # a coarse step whose finer steps are also present starts unticked
            default = kind not in coarse if not cur else kind in cur
            on = cols[j].checkbox(f"{kind} ({counts[kind]})", value=default,
                                  key=f"qk_{i}_{kind}")
            if on:
                picked.append(kind)
        # every kind ticked means "all", which also survives a new trace format
        q["applies_to"] = [] if len(picked) == len(kinds_present) else picked

        if i > 0:
            names = [x["id"] for x in questions[:i]]
            titles = {x["id"]: (x.get("prompt") or x["id"]) for x in questions[:i]}
            on = st.checkbox("Only ask this for certain answers to an earlier "
                             "question", key=f"qc_{i}",
                             value=bool(q.get("ask_if")),
                             help="Off means the question is asked on every step "
                                  "it applies to.")
            if on:
                cc = st.columns([3, 3])
                prior = (q.get("ask_if") or {}).get("question")
                trigger = cc[0].selectbox(
                    "Earlier question", names,
                    index=names.index(prior) if prior in names else 0,
                    format_func=lambda qid: titles.get(qid, qid), key=f"qt_{i}")
                src = next(x for x in questions if x["id"] == trigger)
                have = (q.get("ask_if") or {}).get("equals")
                have = have if isinstance(have, list) else [have]
                want = cc[1].multiselect(
                    "Answers that trigger it", src.get("labels") or [],
                    default=[v for v in have if v in (src.get("labels") or [])],
                    key=f"qv_{i}")
                q["ask_if"] = {"question": trigger, "equals": want} if want else None

                # the two controls read as fragments on their own, so the rule is
                # also written out as one sentence
                this_q = q.get("prompt") or "this question"
                if want:
                    joined = " or ".join(f"<b>{ui.esc(v)}</b>" for v in want)
                    st.markdown(
                        f'<div style="background:#f3f7ff;border:1px solid #c3d8f2;'
                        f'border-radius:7px;padding:9px 13px;font-size:.87rem;'
                        f'color:#1d3d6b;margin-top:4px">'
                        f'<b>{ui.esc(this_q)}</b> is asked only when '
                        f'<b>{ui.esc(titles.get(trigger, trigger))}</b> '
                        f'is answered {joined}.</div>', unsafe_allow_html=True)
                else:
                    st.caption(":red[Choose at least one answer, or the "
                               "condition has no effect.]")
            else:
                q["ask_if"] = None

        if len(questions) > 1 and st.button("Remove", key=f"qd_{i}"):
            questions.pop(i)
            st.rerun()

b = st.columns([1, 1, 1, 2])
if b[0].button("Add a question", use_container_width=True):
    questions.append({"id": f"q{len(questions) + 1}", "prompt": "", "labels": [],
                      "applies_to": [], "ask_if": None})
    st.rerun()
if b[1].button("Restore the default questions", use_container_width=True):
    set_questions([dict(q) for q in TEMPLATE], "")
    st.rerun()

built, problem = None, ""
try:
    built = schema.parse({"id": "custom",
                          "name": st.session_state.get("schema_name", "My questions"),
                          "ask_reason": st.session_state.get("ask_reason", True),
                          "questions": questions})
except schema.SchemaError as e:
    problem = str(e)

with b[2].popover("Saved question sets", use_container_width=True):
    st.markdown("**Saved question sets**")
    st.caption("Stored in `annotrace/questions/`. Every saved set appears in this list.")
    lib = schema.library()
    if not lib:
        st.caption("No saved sets.")
    for name, lib_path in lib:
        row = st.columns([3, 1])
        row[0].markdown(f"`{os.path.basename(lib_path)}` — {name}")
        if row[1].button("Open", key=f"lib_{lib_path}", use_container_width=True):
            try:
                with open(lib_path, encoding="utf-8") as fh:
                    doc = json.load(fh)
                schema.parse(doc)
                set_questions([
                    {"id": x["id"], "prompt": x["prompt"],
                     "labels": list(x.get("labels") or x.get("options") or []),
                     "applies_to": list(x.get("applies_to") or []),
                     "ask_if": x.get("ask_if")} for x in doc["questions"]],
                    doc.get("rules", ""))
                st.session_state["schema_name"] = doc.get("name", name)
                st.rerun()
            except (json.JSONDecodeError, schema.SchemaError, KeyError, TypeError) as e:
                st.error(f"This file could not be opened: {e}")

    st.divider()
    if built:
        save_name = st.text_input("Save the current questions as",
                                  st.session_state.get("schema_name", "My questions"))
        payload = {**built.to_dict(), "name": save_name,
                   "rules": st.session_state.get("llm_guidance", "")}
        if st.button("Save", type="primary", use_container_width=True):
            st.session_state["schema_name"] = save_name
            saved = schema.save_to_library(save_name, payload)
            st.success(f"Saved as `{os.path.basename(saved)}`")
            st.rerun()
        st.download_button("Download a copy", json.dumps(payload, indent=2),
                           f"questions_{datetime.now():%Y%m%d}.json",
                           use_container_width=True)
    f = st.file_uploader("Open a file from your computer", type=["json"], key="qfile")
    if f is not None and st.button("Open", use_container_width=True):
        try:
            doc = json.load(f)
            schema.parse(doc)                      # reject a bad file before using it
            set_questions([
                {"id": x["id"], "prompt": x["prompt"],
                 "labels": list(x.get("labels") or x.get("options") or []),
                 "applies_to": list(x.get("applies_to") or []),
                 "ask_if": x.get("ask_if")} for x in doc["questions"]],
                doc.get("rules", ""))
            st.rerun()
        except (json.JSONDecodeError, schema.SchemaError, KeyError, TypeError) as e:
            st.error(f"This is not a valid question set: {e}")

st.divider()

# ── 3. house rules ────────────────────────────────────────────────────────

st.subheader("2 · Instructions for the model")
st.session_state.setdefault("ask_reason", True)
st.checkbox("Ask for a reason on every step", key="ask_reason",
            help="Disable this to label faster. Enable it when the annotations "
                 "will be reviewed by someone else.")
st.caption("These instructions are followed exactly. State what the labels "
           "cannot: how to choose between similar labels, and the mistakes to "
           "avoid. Human annotators read them as well.")
st.session_state["llm_guidance"] = st.text_area(
    "Instructions", st.session_state.get("llm_guidance", ""), height=150,
    label_visibility="collapsed",
    placeholder="Choose 'Serious problem' only for the step where the failure "
                "begins, not for the steps that follow.")

if built:
    generated = prompt.system_prompt(built, "", st.session_state.get("llm_guidance", ""))
    with st.expander("Full instructions sent to the model", expanded=False):
        edited = st.text_area(
            "Generated from your questions and instructions. Edit it to "
            "override.", generated, height=340, key="prompt_box")
        if edited.strip() != generated.strip():
            st.session_state["prompt_override"] = edited
            st.caption(":orange[Edited. Your version will be used.]")
            if st.button("Restore the generated instructions"):
                st.session_state.pop("prompt_override", None)
                st.session_state.pop("prompt_box", None)
                st.rerun()
        else:
            st.session_state.pop("prompt_override", None)

st.divider()

# ── go ────────────────────────────────────────────────────────────────────

if problem:
    st.error(problem)
else:
    kinds = sorted({k for k in kinds_present if built.for_kind(k)})
    if not kinds:
        st.warning("No question applies to any kind of step. Select at least one above.")
    else:
        st.session_state["schema"] = built.to_dict()
        st.session_state["kinds"] = kinds
        todo = sum(len(store.steps_to_do(t, built, kinds)) for t in traces)
        left, right = st.columns([1, 3])
        if left.button("Start annotating  →", type="primary", use_container_width=True):
            st.switch_page("views/annotate.py")
        right.caption(f"{todo} steps to label across {len(traces)} traces "
                      f"({', '.join(kinds)}). The questions can be changed later.")

        prior = store.load_session(store.session_path(
            DATA_DIR, st.session_state.get("user", "anon")))
        if prior and prior.get("traces"):
            n = sum(len(t.get("steps", [])) for t in prior["traces"])
            if st.button(f"Resume an earlier session ({n} answers)"):
                st.session_state["annotations"] = store.read_payload(prior)
                st.switch_page("views/annotate.py")

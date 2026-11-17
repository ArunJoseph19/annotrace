"""Turn the revised-codebook (v4) reference and model labels into AnnoTrace
exports, then check AnnoTrace's own compare module reproduces the agreement."""
import json, os, sys
REPO, BATCH, OUT = sys.argv[1], sys.argv[2], sys.argv[3]
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(REPO, "annotrace"))
from core import adapter, compare, store, schema as sch  # noqa: E402
adapter.load_all()
traces = adapter.get("coordinator").load(BATCH)
tax = json.load(open(os.path.join(HERE, "taxonomy_v4.json")))
types = ["Informational"] + [c for cs in tax["themes"].values() for c in cs] + ["OTHER"]
SCHEMA = sch.parse({"id": "orchestrator_v4", "name": "Orchestrator errors (v4)", "questions": [
    {"id": "error_type", "prompt": "What error, if any, does this orchestrator step make?", "labels": types,
     "applies_to": ["decision", "output"]},
    {"id": "severity", "prompt": "How severe is it?", "labels": ["Critical", "Error", "Warning", "Informational"],
     "applies_to": ["decision", "output"]}]})
FAULT = sch.parse({"questions": [{"id": "severity", "prompt": "fault", "labels": ["fault", "ok"]}]})


def units(path):
    d = json.load(open(path))
    rows = d["units"] if "units" in d else [dict(u, traj_idx=t["traj_idx"]) for t in d["traces"] for u in t["units"]]
    return {(u["traj_idx"], u["step_key"]): u for u in rows}


def export(name, rows, source):
    ann = {}
    for (i, key), u in rows.items():
        ann.setdefault(traces[i].id, {})[key] = {"labels": {"error_type": u["label"], "severity": u["severity"]},
                                                 "reason": u.get("reason") or "", "source": source}
    payload = store.build_payload(SCHEMA, "coordinator", os.path.basename(BATCH), ["decision", "output"], traces, ann)
    path = os.path.join(OUT, name + ".json"); json.dump(payload, open(path, "w"), indent=1)
    return store.read_payload(json.load(open(path)))


ref = export("reference_v4", units(os.path.join(HERE, "reference_batch_30_v4.json")), "human")
for m in ("haiku", "sonnet"):
    got = export(f"model_{m}_v4", units(os.path.join(HERE, "runs", f"{m}_v4.json")), "llm")
    rep = compare.compare(ref, got, SCHEMA.questions)
    f = lambda d: {t: {k: {"labels": {"severity": "fault" if r["labels"]["severity"] in ("Error", "Critical") else "ok"}}
                       for k, r in us.items()} for t, us in d.items()}
    fq = compare.compare(f(ref), f(got), FAULT.questions).questions[0]
    print(m, " ".join(f"{q.question_id}: n={q.both} raw={q.raw:.2f} kappa={q.kappa:.2f}" for q in rep.questions),
          f"fault: raw={fq.raw:.2f} kappa={fq.kappa:.2f}")

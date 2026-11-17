"""Write the 40-run human labels and each model's answers as Annotrace exports,
so the Compare screen can open them, then check they read back to the same kappa."""
import glob, json, os, sys
AP, RUNS, OUT = sys.argv[1], sys.argv[2], sys.argv[3]
sys.path.insert(0, os.path.join(AP, "annotrace"))
from core import adapter, compare, store, schema as sch  # noqa: E402
adapter.load_all()
SRC = "subset_40_stratified.jsonl"
traces = adapter.get("coordinator").load(os.path.join(AP, "evaluation/data", SRC))
model_file = sorted(glob.glob(os.path.join(RUNS, "*.json")))[0]
SCHEMA = sch.parse(json.load(open(model_file))["schema"])


def write(name, by_trace, source):
    ann = {traces[i].id: {k: {"labels": v["labels"], "reason": v.get("reason", ""), "source": source}
                          for k, v in steps.items() if v.get("labels")}
           for i, steps in by_trace.items()}
    payload = store.build_payload(SCHEMA, "coordinator", SRC, ["decision", "cycle", "output"], traces, ann)
    path = os.path.join(OUT, name + ".json")
    json.dump(payload, open(path, "w"), indent=1)
    return path


g = json.load(open(os.path.join(AP, "evaluation/labels/human_labels_final.json")))
human = {t["traj_idx"]: {s["step_key"]: {"labels": {"severity": s["label"], **(
    {"critical_type": s["critical_type"]} if s["label"] == "Critical" and s.get("critical_type") else {})},
    "reason": s.get("reason", "")} for s in t["steps"]} for t in g["trajectories"]}
ref = write("human_labels_40_runs", human, "human")
for f in sorted(glob.glob(os.path.join(RUNS, "*.json"))):
    d = json.load(open(f))
    name = os.path.basename(f)[:-5]
    path = write("model_" + name, {int(i): r.get("steps", {}) for i, r in d["runs"].items()}, "llm")
    a = store.read_payload(json.load(open(ref))); b = store.read_payload(json.load(open(path)))
    q = compare.compare(a, b, SCHEMA.questions).questions[0]
    print(f"{name:50s} n={q.both} raw={q.raw:.3f} kappa={q.kappa:.3f}")

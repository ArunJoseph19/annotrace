"""Agreement numbers for the paper, all through Annotrace's own compare module."""
import json, os, sys, glob, itertools
AP, RUNS = sys.argv[1], sys.argv[2]
sys.path.insert(0, os.path.join(AP, "annotrace"))
from core import compare, schema as sch  # noqa: E402

Q = sch.parse({"questions": [{"id": "severity", "prompt": "severity",
                              "labels": ["Informational", "Warning", "Error", "Critical"]}]}).questions


def human(path):
    d = json.load(open(os.path.join(AP, "evaluation/labels", path)))
    return {t["traj_idx"]: {s["step_key"]: {"labels": {"severity": s["label"]}}
                            for s in t["steps"] if s.get("label") in Q[0].labels}
            for t in d["trajectories"]}


def model(path):
    d = json.load(open(path))
    return {int(i): r.get("steps", {}) for i, r in d["runs"].items()}


def collapse(a):  # error vs no error: Critical/Error -> fault, Info/Warning -> no fault
    m = {"Critical": "fault", "Error": "fault", "Warning": "ok", "Informational": "ok"}
    return {t: {k: {"labels": {"severity": m[v["labels"]["severity"]]}}
                for k, v in u.items() if v.get("labels", {}).get("severity") in m} for t, u in a.items()}


Q2 = sch.parse({"questions": [{"id": "severity", "prompt": "fault", "labels": ["fault", "ok"]}]}).questions


def row(name, a, b):
    r = compare.compare(a, b, Q).questions[0]
    r2 = compare.compare(collapse(a), collapse(b), Q2).questions[0]
    return f"{name:60s} n={r.both:4d}  4-way raw={r.raw:.3f} k={r.kappa:.3f}   fault/ok raw={r2.raw:.3f} k={r2.kappa:.3f}"


gold = human("human_labels_final.json")
a_pass = human("annotator_a_first_pass.json")
b_pass = human("annotator_b_first_pass.json")
print(row("annotator A vs annotator B (overlap)", a_pass, b_pass))
print(row("annotator A vs final labels", a_pass, gold))
print(row("annotator B vs final labels", b_pass, gold))
models = {os.path.basename(p)[:-5]: model(p) for p in sorted(glob.glob(os.path.join(RUNS, "*.json")))}
for n, m in models.items():
    print(row(f"{n} vs final", m, gold))
for (n1, m1), (n2, m2) in itertools.combinations(models.items(), 2):
    print(row(f"{n1[:28]} vs {n2[:28]}", m1, m2))

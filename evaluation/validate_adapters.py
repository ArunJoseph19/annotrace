"""Run every adapter over real public traces and check the steps it produces
against what the file itself contains."""
import glob, json, os, sys, collections
AP, D = sys.argv[1], sys.argv[2]
sys.path.insert(0, os.path.join(AP, "annotrace"))
from core import adapter  # noqa: E402
adapter.load_all()


def tree(spans):
    n, d = 0, 0
    def walk(s, depth):
        nonlocal n, d
        n += 1; d = max(d, depth)
        for c in s.get("child_spans") or []:
            walk(c, depth + 1)
    for s in spans:
        walk(s, 0)
    return n, d


SPAN_DEPTH = {}


def exp_trail(f):
    doc = json.load(open(f))
    def walk(sp, d):
        SPAN_DEPTH[str(sp.get("span_id"))] = d
        for c in sp.get("child_spans") or []:
            walk(c, d + 1)
    for sp in doc["spans"]:
        walk(sp, 0)
    return [tree(doc["spans"])]


def exp_history(key):
    def e(f):
        doc = json.load(open(f)); recs = doc if isinstance(doc, list) else [doc]
        return [(len(r[key]), 0) for r in recs]
    return e


def exp_tau(f):
    return [(sum(1 for m in r["traj"] if m.get("role") != "system"), 0) for r in json.load(open(f))]


def exp_list(f):
    d = json.load(open(f)); return [(len(d), 0)]


def exp_who(f):
    d = json.load(open(f)); return [(len(d.get("history") or d.get("trajectory")), 0)]


SETS = [
    ("TRAIL GAIA (OpenInference spans)", "otel_genai", glob.glob(f"{D}/trail/benchmarking/data/GAIA/*.json"), exp_trail),
    ("TRAIL SWE-bench (OpenInference spans)", "otel_genai", glob.glob(f"{D}/trail/benchmarking/data/SWE Bench/*.json"), exp_trail),
    ("tau-bench retail (chat + tool calls)", "chat_messages", glob.glob(f"{D}/agentrx/data/tau_retail/*.json"), exp_tau),
    ("Who&When Hand-Crafted", "who_and_when", glob.glob(f"{D}/ww/Hand-Crafted/*.json"), exp_who),
    ("Who&When Algorithm-Generated", "who_and_when", glob.glob(f"{D}/ww/Algorithm-Generated/*.json"), exp_who),
    ("AgentRx Magentic-One", "chat_messages", [f for f in glob.glob(f"{D}/agentrx/data/magentic_dataset/*.json")
                                                if not f.endswith("steps_by_id.json")], exp_list),
]

rows = []
for name, want, files, expect in SETS:
    s = collections.Counter(); bad = []
    for f in sorted(files):
        scores = {a.id: a.sniff(f) for a in adapter.available().values()}
        best, sc = adapter.detect(f)
        s["files"] += 1
        if not best or best.id != want:
            bad.append((os.path.basename(f), best.id if best else None)); continue
        s["detected"] += 1
        if sorted(scores.values())[-2] < sc:
            s["unique"] += 1
        traces = best.load(f)
        exp = expect(f)
        s["traces"] += len(traces); s["exp_traces"] += len(exp)
        for t, (n, d) in zip(traces, exp):
            s["units"] += len(t.units); s["exp_units"] += n
            s["empty"] += sum(1 for u in t.units if all(x.is_empty for x in u.fields))
            if len(t.units) == n:
                s["count_ok"] += 1
            if SPAN_DEPTH:
                if all(SPAN_DEPTH.get(u.key) == u.depth for u in t.units):
                    s["depth_ok"] += 1
                SPAN_DEPTH.clear()
            elif all(u.depth == 0 for u in t.units):   # flat formats: every step at depth 0
                s["depth_ok"] += 1
    rows.append((name, want, dict(s), bad[:3]))

for name, want, s, bad in rows:
    print(f"{name:40s} {want:13s} files={s.get('files',0):4d} detected={s.get('detected',0):4d} "
          f"unique={s.get('unique',0):4d} traces={s.get('traces',0)}/{s.get('exp_traces',0)} "
          f"steps={s.get('units',0)}/{s.get('exp_units',0)} count_ok={s.get('count_ok',0)} "
          f"depth_ok={s.get('depth_ok',0)} empty_steps={s.get('empty',0)} {bad}")

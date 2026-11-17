"""Annotate the 40-run corpus with several Bedrock models through Annotrace's own
prompt builder and reply parser, then save one Annotrace-style export per model.

The only part replaced is the transport: llm._call goes to the HAI endpoint, here
the same system + user text goes to Bedrock Converse.
"""
import json, os, sys, time, concurrent.futures as cf
import boto3
from botocore.config import Config

AP, OUT = sys.argv[1], sys.argv[2]
MODELS = sys.argv[3].split(",")
sys.path.insert(0, os.path.join(AP, "annotrace"))
from core import adapter, prompt, schema as sch  # noqa: E402

adapter.load_all()
traces = adapter.get("coordinator").load(
    os.path.join(AP, "evaluation/data/subset_40_stratified.jsonl"))
KINDS = ("decision", "cycle", "output")
SUBTYPES = ["Centralized Agent — Task decomposition", "Centralized Agent — Subtask Generation",
            "Centralized Agent — Expert Assignment", "Centralized Agent — Response Process",
            "Expert Agent — reasoning", "Expert Agent — interaction", "Expert Agent — communication"]
SCHEMA = sch.parse({"id": "severity", "name": "Severity", "questions": [
    {"id": "severity", "prompt": "Did this step cause or contribute to the run's failure?",
     "labels": ["Informational", "Warning", "Error", "Critical"], "applies_to": list(KINDS)},
    {"id": "critical_type", "prompt": "Which kind of critical failure?", "labels": SUBTYPES,
     "applies_to": list(KINDS), "ask_if": {"question": "severity", "equals": "Critical"}}]})
GUIDE = open(os.path.join(AP, "evaluation/annotation_handbook.md"), encoding="utf-8").read() + (
    "\n\nAnswer severity with the bare label only. When it is Critical, give the "
    "sub-type in critical_type, not inside the severity value.")
SYSTEM = prompt.system_prompt(SCHEMA, guidance=GUIDE)

client = boto3.client("bedrock-runtime", region_name="us-east-1",
                      config=Config(read_timeout=300, retries={"max_attempts": 6, "mode": "adaptive"}))


def one(model, i, t):
    keys = [u.key for u in t.units if u.kind in KINDS]
    user = prompt.user_prompt(t, keys=None)  # whole trace as context
    user += "\nLabel only these step keys: " + ", ".join(keys)
    t0 = time.time()
    cfg = {"maxTokens": 8000, "temperature": 0}
    for attempt in range(4):
        try:
            r = client.converse(modelId=model, system=[{"text": SYSTEM}],
                                messages=[{"role": "user", "content": [{"text": user}]}],
                                inferenceConfig=cfg)
            break
        except Exception as e:  # throttling or a transient fault
            if "temperature" in str(e) and "temperature" in cfg:
                cfg = {"maxTokens": 8000}  # newer models fix their own sampling
                continue
            if attempt == 3:
                return i, {"error": repr(e)[:300]}
            time.sleep(5 * (attempt + 1))
    text = "".join(c.get("text", "") for c in r["output"]["message"]["content"])
    parsed = prompt.parse(text, SCHEMA, t)
    parsed = {k: v for k, v in parsed.items() if k in keys}
    return i, {"steps": parsed, "usage": r.get("usage", {}), "seconds": round(time.time() - t0, 2),
               "expected": len(keys), "raw": text, "temperature": cfg.get("temperature")}


for model in MODELS:
    path = os.path.join(OUT, model.replace("/", "_").replace(":", "_") + ".json")
    if os.path.exists(path):
        continue
    res = {}
    with cf.ThreadPoolExecutor(6) as ex:
        for i, r in ex.map(lambda it: one(model, *it), list(enumerate(traces))):
            res[i] = r
    export = {"model": model, "schema": SCHEMA.to_dict(), "system_prompt": SYSTEM, "runs": res}
    with open(path, "w") as f:
        json.dump(export, f, indent=1)
    got = sum(len(r.get("steps", {})) for r in res.values())
    errs = sum(1 for r in res.values() if "error" in r)
    print(f"{model}: {got}/348 steps labelled, {errs} errors", flush=True)

"""How much does a proposed schema depend on which ten runs were sampled?

Runs Annotrace's own proposal prompt and parser (core.suggest) over five
different random samples per corpus and model. Only the sample seed and the
transport (Bedrock instead of the HAI endpoint) differ from the app.
"""
import json, os, random, sys, time
import boto3
AP, OUT = sys.argv[1], sys.argv[2]
sys.path.insert(0, os.path.join(AP, "annotrace"))
from core import adapter, suggest  # noqa: E402
adapter.load_all()
client = boto3.client("bedrock-runtime", region_name="us-east-1")
GOAL = "Which step caused the run to give a wrong answer, and what kind of mistake was it?"
CORPORA = {
    "coordinator_40": (adapter.get("coordinator"),
                       [os.path.join(AP, "evaluation/data/subset_40_stratified.jsonl")]),
    "whowhen_handcrafted": (adapter.get("who_and_when"),
                            sorted(__import__("glob").glob(sys.argv[3] + "/ww/Hand-Crafted/*.json"))),
}
MODELS = ["global.anthropic.claude-haiku-4-5-20251001-v1:0", "us.anthropic.claude-opus-5"]
SEEDS = [1, 2, 3, 4, 5]


def call(model, system, user):
    cfg = {"maxTokens": 1500, "temperature": 0}
    for _ in range(3):
        try:
            r = client.converse(modelId=model, system=[{"text": system}],
                                messages=[{"role": "user", "content": [{"text": user}]}],
                                inferenceConfig=cfg)
            return "".join(c.get("text", "") for c in r["output"]["message"]["content"])
        except Exception as e:
            if "temperature" in str(e):
                cfg = {"maxTokens": 1500}
                continue
            time.sleep(5)
    raise RuntimeError("call failed")


out = []
for cname, (ad, files) in CORPORA.items():
    traces = [t for f in files for t in ad.load(f)]
    for model in MODELS:
        for seed in SEEDS:
            real = random.Random
            random.Random = lambda _n, s=seed: real(s)  # vary only the sample
            try:
                body = suggest.sample_steps(traces)
            finally:
                random.Random = real
            body = f"WHAT THE ANNOTATOR IS LOOKING FOR:\n  {GOAL}\n\n{body}"
            reply = call(model, suggest.SYSTEM, body)
            try:
                qs, rules, why = suggest.parse(reply)
            except Exception as e:
                out.append({"corpus": cname, "model": model, "seed": seed, "error": str(e), "raw": reply})
                print(cname, model, seed, "PARSE FAILED", flush=True)
                continue
            out.append({"corpus": cname, "n_traces": len(traces), "model": model, "seed": seed,
                        "questions": qs, "rules": rules, "why": why})
            print(cname, model.split(".")[-1][:22], seed, [(q["prompt"], q["labels"]) for q in qs], flush=True)
json.dump(out, open(OUT, "w"), indent=1)

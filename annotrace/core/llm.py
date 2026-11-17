"""Calling a model.

Two back-ends behind one function, so a page never knows which is in use:

- Amazon Bedrock (default), with the caller's own AWS credentials and region
  (AWS_PROFILE / AWS_REGION, as for any boto3 client).
- A hosted gateway that accepts {"model", "max_tokens", "messages"} and returns
  {"text"} or {"content": [{"text"}]}, used when ANNOTRACE_GATEWAY_URL is set;
  its key is read from ANNOTRACE_API_KEY.

Settings are read from the environment, then from a .env file beside the
repository, so no key or private address lives in the code.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request


class LLMError(RuntimeError):
    pass


def _setting(name: str) -> str:
    if os.environ.get(name):
        return os.environ[name]
    root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    path = os.path.join(root, ".env")
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            for line in f:
                key, _, value = line.strip().partition("=")
                if key.strip() == name:
                    return value.strip().strip("'\"")
    return ""


# what the last call used, for the interface to show
LAST_USAGE: dict = {}


def complete(system: str, user: str, model: str = "", api_key: str = "",
             max_tokens: int = 4096) -> str:
    from core.models import DEFAULT
    model = model or DEFAULT
    gateway = _setting("ANNOTRACE_GATEWAY_URL")
    if gateway:
        key = api_key.strip() or _setting("ANNOTRACE_API_KEY")
        if not key:
            raise LLMError("ANNOTRACE_GATEWAY_URL is set but ANNOTRACE_API_KEY is not.")
        return _gateway(gateway, key, system, user, model, max_tokens)
    return _bedrock(system, user, model, max_tokens)


def _bedrock(system: str, user: str, model: str, max_tokens: int) -> str:
    try:
        import boto3
    except ImportError as e:
        raise LLMError("Install boto3 to call models on Amazon Bedrock, or set "
                       "ANNOTRACE_GATEWAY_URL.") from e
    region = _setting("AWS_REGION") or "us-east-1"
    try:
        client = boto3.client("bedrock-runtime", region_name=region)
        r = client.converse(modelId=model, system=[{"text": system}],
                            messages=[{"role": "user", "content": [{"text": user}]}],
                            inferenceConfig={"maxTokens": int(max_tokens)})
    except Exception as e:  # credentials, access to the model, throttling
        raise LLMError(f"The Bedrock call failed: {e}") from e
    usage = r.get("usage") or {}
    LAST_USAGE.clear()
    LAST_USAGE.update(model=model, input_tokens=usage.get("inputTokens"),
                      output_tokens=usage.get("outputTokens"), cost=None)
    text = "".join(c.get("text", "") for c in r["output"]["message"]["content"])
    if not text.strip():
        raise LLMError("The model returned an empty reply.")
    return text


def _gateway(url: str, key: str, system: str, user: str, model: str,
             max_tokens: int) -> str:
    # gateways of this shape take no system role, so the instructions lead
    body = json.dumps({"model": model, "max_tokens": int(max_tokens),
                       "messages": [{"role": "user",
                                     "content": f"{system}\n\n---\n\n{user}"}]}).encode()
    req = urllib.request.Request(url, data=body,
                                 headers={"X-Api-Key": key, "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=180) as resp:
            doc = json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        detail = e.read().decode()[:200] if hasattr(e, "read") else ""
        raise LLMError(f"The model call failed ({e.code}). {detail}") from e
    except (urllib.error.URLError, TimeoutError) as e:
        raise LLMError(f"Could not reach the model: {e}") from e
    except json.JSONDecodeError as e:
        raise LLMError("The model returned something that is not JSON.") from e

    usage = doc.get("usage") or {}
    quota = (doc.get("metadata") or {}).get("remaining_quota") or {}
    LAST_USAGE.clear()
    LAST_USAGE.update(model=model, input_tokens=usage.get("inputTokens"),
                      output_tokens=usage.get("outputTokens"), cost=usage.get("cost"),
                      remaining=quota.get("remaining_budget"),
                      budget=quota.get("budget_limit"))
    if isinstance(doc.get("text"), str) and doc["text"].strip():
        return doc["text"]
    parts = doc.get("content") or []
    text = "".join(p.get("text", "") for p in parts if isinstance(p, dict))
    if not text.strip():
        raise LLMError("The model returned an empty reply.")
    return text

"""The models this API key can reach.

Each entry is (id, name, input price per 1K tokens). The price becomes a tier
mark in the interface: $ cheap, $$ middling, $$$ expensive. Exact prices belong
on the provider's page, not in a dropdown.
"""

from __future__ import annotations

# (id, display name, USD per 1K input tokens)
MODELS: list[tuple[str, str, float]] = [
    # DeepSeek
    ("deepseek.v3.2", "DeepSeek V3.2", 0.0012),
    ("deepseek.v3-v1:0", "DeepSeek V3.1", 0.0011),
    # Anthropic
    ("global.anthropic.claude-haiku-4-5-20251001-v1:0", "Claude Haiku 4.5", 0.0014),
    ("eu.anthropic.claude-sonnet-5", "Claude Sonnet 5", 0.0027),
    ("eu.anthropic.claude-sonnet-4-6", "Claude Sonnet 4.6", 0.0041),
    ("eu.anthropic.claude-sonnet-4-5-20250929-v1:0", "Claude Sonnet 4.5", 0.0041),
    ("anthropic.claude-3-7-sonnet-20250219-v1:0", "Claude 3.7 Sonnet", 0.0041),
    ("eu.anthropic.claude-opus-5", "Claude Opus 5", 0.0069),
    ("eu.anthropic.claude-opus-4-8", "Claude Opus 4.8", 0.0069),
    ("eu.anthropic.claude-opus-4-7", "Claude Opus 4.7", 0.0069),
    ("eu.anthropic.claude-opus-4-6-v1", "Claude Opus 4.6", 0.0069),
    ("eu.anthropic.claude-opus-4-5-20251101-v1:0", "Claude Opus 4.5", 0.0069),
    ("global.anthropic.claude-fable-5-1", "Claude Fable 5.1", 0.0125),
    ("global.anthropic.claude-fable-5", "Claude Fable 5", 0.0125),
    # OpenAI
    ("global.openai.gpt-5.6-luna", "GPT-5.6 Luna", 0.0003),
    ("global.openai.gpt-5.6-terra", "GPT-5.6 Terra", 0.0025),
    ("global.openai.gpt-5.6-sol", "GPT-5.6 Sol", 0.0063),
    ("global.openai.gpt-6-astra", "GPT-6 Astra", 0.0125),
    ("openai.gpt-oss-120b-1:0", "GPT-OSS 120B", 0.0003),
    ("openai.gpt-oss-20b-1:0", "GPT-OSS 20B", 0.0001),
    # Google
    ("google.gemma-3-12b-it", "Gemma 3 12B", 0.0002),
    ("google.gemma-3-27b-it", "Gemma 3 27B", 0.0005),
    ("google.gemma-4-31b", "Gemma 4 31B", 0.0005),
    ("google.gemma-4-26b-a4b", "Gemma 4 26B", 0.0002),
    # Qwen
    ("qwen.qwen3-32b-v1:0", "Qwen3 32B", 0.0003),
    ("qwen.qwen3-next-80b-a3b", "Qwen3 Next 80B", 0.0003),
    ("qwen.qwen3-235b-a22b-2507-v1:0", "Qwen3 235B", 0.0004),
    # Z.AI
    ("zai.glm-4.7-flash", "GLM 4.7 Flash", 0.0001),
    ("zai.glm-4.7", "GLM 4.7", 0.0012),
    ("zai.glm-5", "GLM 5", 0.0019),
    # MiniMax
    ("minimax.minimax-m2.5", "MiniMax M2.5", 0.0006),
    ("minimax.minimax-m2.1", "MiniMax M2.1", 0.0006),
    # Moonshot
    ("moonshotai.kimi-k2.5", "Kimi K2.5", 0.0012),
    ("global.moonshotai.kimi-k3", "Kimi K3", 0.0125),
    # xAI
    ("global.xai.grok-4.6", "Grok 4.6", 0.0016),
    # Amazon
    ("amazon.nova-lite-v1:0", "Nova Lite", 0.0001),
    ("global.amazon.nova-2-lite-v1:0", "Nova 2 Lite", 0.0005),
    ("amazon.nova-pro-v1:0", "Nova Pro", 0.0014),
    # NVIDIA
    ("nvidia.nemotron-nano-3-30b", "Nemotron Nano 3 30B", 0.0001),
    ("nvidia.nemotron-nano-9b-v2", "Nemotron Nano 9B", 0.0001),
    # Mistral
    ("mistral.ministral-3-8b-instruct", "Ministral 3 8B", 0.0003),
    ("mistral.ministral-3-14b-instruct", "Ministral 14B", 0.0004),
    ("mistral.magistral-small-2509", "Magistral Small", 0.0010),
    ("mistral.mistral-large-2402-v1:0", "Mistral Large", 0.0065),
    # Meta
    ("meta.llama3-70b-instruct-v1:0", "Llama 3 70B", 0.0043),
    ("meta.llama3-8b-instruct-v1:0", "Llama 3 8B", 0.0005),
]

DEFAULT = "global.anthropic.claude-haiku-4-5-20251001-v1:0"

_BY_ID = {mid: (name, price) for mid, name, price in MODELS}


def tier(price: float) -> str:
    """$ to $$$, from the cheapest input price to the dearest."""
    if price < 0.001:
        return "$"
    if price < 0.005:
        return "$$"
    return "$$$"


def label(model_id: str) -> str:
    name, price = _BY_ID.get(model_id, (model_id, 0.0))
    return f"{name}  {tier(price)}"


def ids() -> list[str]:
    """Cheapest first, so the default choice is also the cheap one."""
    return [mid for mid, _, _ in sorted(MODELS, key=lambda m: (m[2], m[1]))]


def name(model_id: str) -> str:
    return _BY_ID.get(model_id, (model_id, 0.0))[0]

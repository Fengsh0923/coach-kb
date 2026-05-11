"""LLM + embedding clients. Main: DeepSeek (OpenAI compatible). Embed: DashScope."""
from __future__ import annotations
import os
import json
import httpx
from typing import AsyncGenerator
from contextvars import ContextVar

_endpoint_tag: ContextVar[str] = ContextVar("_endpoint_tag", default="unknown")


def set_endpoint(name: str):
    _endpoint_tag.set(name)


# ─── LLM: OpenAI-compatible (default DeepSeek) ─────────────────────────────
LLM_KEY = os.environ.get("DEEPSEEK_API_KEY") or os.environ.get("LLM_API_KEY", "")
LLM_BASE = os.environ.get("LLM_BASE_URL", "https://api.deepseek.com")
LLM_MODEL_FAST = os.environ.get("LLM_MODEL_FAST", "deepseek-v4-flash")    # qa 流式用
LLM_MODEL_REASON = os.environ.get("LLM_MODEL_REASON", "deepseek-v4-pro")  # eval 等批处理用
LLM_MODEL = os.environ.get("LLM_MODEL", LLM_MODEL_FAST)                   # backward compat

# ─── Embedding: DashScope ──────────────────────────────────────────────────
EMBED_KEY = os.environ.get("DASHSCOPE_API_KEY") or os.environ.get("QWEN_API_KEY", "")
EMBED_BASE = os.environ.get("EMBED_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1")
EMBED_MODEL = os.environ.get("EMBED_MODEL", "text-embedding-v3")

# Pricing (USD per 1M tokens)
PRICING = {
    "deepseek-chat": {"in": 0.27, "out": 1.10},     # V4 标准价（cache miss）
    "deepseek-v4-flash": {"in": 0.07, "out": 0.27}, # V4 flash 估值
    "deepseek-v4-pro": {"in": 0.55, "out": 2.20},   # V4 pro 估值
    "deepseek-reasoner": {"in": 0.55, "out": 2.20},
    "glm-4.6": {"in": 0.6, "out": 2.2},
    "text-embedding-v3": {"in": 0.05, "out": 0},
}


def _calc_cost(model: str, in_t: int, out_t: int) -> float:
    p = PRICING.get(model, {"in": 0.5, "out": 1.5})
    return (in_t * p["in"] + out_t * p["out"]) / 1_000_000


def _record(provider: str, model: str, in_t: int, out_t: int):
    try:
        from lib import db as _db
        _db.log_usage(endpoint=_endpoint_tag.get(), provider=provider, model=model,
                       input_tokens=in_t, output_tokens=out_t,
                       cost_usd=_calc_cost(model, in_t, out_t))
    except Exception:
        pass


async def embed(texts: list[str]) -> list[list[float]]:
    """DashScope OpenAI-compatible embedding (China-friendly, 1024 dim)."""
    if not EMBED_KEY:
        raise RuntimeError("DASHSCOPE_API_KEY / QWEN_API_KEY not set")
    async with httpx.AsyncClient(timeout=60) as client:
        r = await client.post(
            f"{EMBED_BASE}/embeddings",
            headers={"Authorization": f"Bearer {EMBED_KEY}", "Content-Type": "application/json"},
            json={"model": EMBED_MODEL, "input": texts, "dimensions": 1024,
                  "encoding_format": "float"},
        )
        r.raise_for_status()
        j = r.json()
        usage = j.get("usage", {})
        _record("dashscope", EMBED_MODEL,
                in_t=usage.get("prompt_tokens") or usage.get("total_tokens", 0),
                out_t=0)
        return [d["embedding"] for d in j["data"]]


async def chat_complete(*, system: str, user: str, max_tokens: int = 8192, model: str | None = None) -> str:
    """One-shot LLM call. Defaults to REASON model (DeepSeek V4 Pro) — eval/judge 用。
    max_tokens 默认 8192 给 reasoning 模型留思考空间。"""
    if not LLM_KEY:
        raise RuntimeError("DEEPSEEK_API_KEY / LLM_API_KEY not set")
    use_model = model or LLM_MODEL_REASON
    async with httpx.AsyncClient(timeout=120) as client:
        r = await client.post(
            f"{LLM_BASE}/chat/completions",
            headers={"Authorization": f"Bearer {LLM_KEY}", "Content-Type": "application/json"},
            json={
                "model": use_model,
                "max_tokens": max_tokens,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
            },
        )
        r.raise_for_status()
        data = r.json()
        usage = data.get("usage", {})
        # DeepSeek 返回真实使用的 model name（如 deepseek-v4-flash）
        actual_model = data.get("model", use_model)
        _record("deepseek", actual_model,
                in_t=usage.get("prompt_tokens", 0),
                out_t=usage.get("completion_tokens", 0))
        return data["choices"][0]["message"]["content"] or ""


async def chat_stream(*, system: str, user: str, max_tokens: int = 2048) -> AsyncGenerator[str, None]:
    """Streaming LLM call (OpenAI chat completions SSE). Yields text chunks."""
    if not LLM_KEY:
        raise RuntimeError("DEEPSEEK_API_KEY / LLM_API_KEY not set")
    async with httpx.AsyncClient(timeout=180) as client:
        async with client.stream(
            "POST",
            f"{LLM_BASE}/chat/completions",
            headers={"Authorization": f"Bearer {LLM_KEY}", "Content-Type": "application/json"},
            json={
                "model": LLM_MODEL_FAST,
                "max_tokens": max_tokens,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                "stream": True,
                "stream_options": {"include_usage": True},
            },
        ) as r:
            r.raise_for_status()
            in_t = 0; out_t = 0; actual_model = LLM_MODEL_FAST
            async for line in r.aiter_lines():
                if not line.startswith("data: "):
                    continue
                payload = line[6:]
                if payload == "[DONE]":
                    break
                try:
                    ev = json.loads(payload)
                except Exception:
                    continue
                if ev.get("model"):
                    actual_model = ev["model"]
                choices = ev.get("choices") or []
                if choices:
                    delta = choices[0].get("delta") or {}
                    content = delta.get("content")
                    if content:
                        yield content
                usage = ev.get("usage")
                if usage:
                    in_t = usage.get("prompt_tokens", in_t)
                    out_t = usage.get("completion_tokens", out_t)
            _record("deepseek", actual_model, in_t=in_t, out_t=out_t)

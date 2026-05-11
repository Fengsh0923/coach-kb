"""LLM + embedding clients. Main: GLM-4.6 via Anthropic Messages API. Embed: DashScope."""
from __future__ import annotations
import os
import json
import httpx
from typing import AsyncGenerator
from contextvars import ContextVar

# Allow caller to tag the endpoint via context var (best-effort, never required)
_endpoint_tag: ContextVar[str] = ContextVar("_endpoint_tag", default="unknown")


def set_endpoint(name: str):
    _endpoint_tag.set(name)


# Pricing (USD per 1M tokens) — adjust when providers change
PRICING = {
    "glm-4.6": {"in": 0.6, "out": 2.2},     # 智谱国际 Anthropic-compatible
    "glm-5.1": {"in": 0.6, "out": 2.2},
    "glm-4.5": {"in": 0.5, "out": 1.5},
    "text-embedding-v3": {"in": 0.05, "out": 0},   # DashScope 估值
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

GLM_KEY = os.environ.get("GLM_INTL_API_KEY", "")
GLM_BASE = os.environ.get("GLM_INTL_BASE_URL", "https://api.z.ai/api/anthropic")
GLM_MODEL = os.environ.get("GLM_MODEL", "glm-4.6")

EMBED_KEY = os.environ.get("DASHSCOPE_API_KEY") or os.environ.get("QWEN_API_KEY", "")
EMBED_BASE = os.environ.get("EMBED_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1")
EMBED_MODEL = os.environ.get("EMBED_MODEL", "text-embedding-v3")


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


async def chat_complete(*, system: str, user: str, max_tokens: int = 2048, model: str | None = None) -> str:
    """One-shot LLM call. Returns full text."""
    if not GLM_KEY:
        raise RuntimeError("GLM_INTL_API_KEY not set")
    async with httpx.AsyncClient(timeout=120) as client:
        r = await client.post(
            f"{GLM_BASE}/v1/messages",
            headers={"x-api-key": GLM_KEY, "anthropic-version": "2023-06-01", "Content-Type": "application/json"},
            json={
                "model": model or GLM_MODEL,
                "max_tokens": max_tokens,
                "system": system,
                "messages": [{"role": "user", "content": user}],
            },
        )
        r.raise_for_status()
        data = r.json()
        parts = data.get("content", [])
        usage = data.get("usage", {})
        _record("glm-intl", model or GLM_MODEL,
                in_t=usage.get("input_tokens", 0),
                out_t=usage.get("output_tokens", 0))
        return "".join(p.get("text", "") for p in parts if p.get("type") == "text")


async def chat_stream(*, system: str, user: str, max_tokens: int = 2048) -> AsyncGenerator[str, None]:
    """Streaming LLM call. Yields text chunks."""
    if not GLM_KEY:
        raise RuntimeError("GLM_INTL_API_KEY not set")
    async with httpx.AsyncClient(timeout=180) as client:
        async with client.stream(
            "POST",
            f"{GLM_BASE}/v1/messages",
            headers={"x-api-key": GLM_KEY, "anthropic-version": "2023-06-01", "Content-Type": "application/json"},
            json={
                "model": GLM_MODEL, "max_tokens": max_tokens,
                "system": system, "stream": True,
                "messages": [{"role": "user", "content": user}],
            },
        ) as r:
            r.raise_for_status()
            in_t = 0; out_t = 0
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
                t = ev.get("type")
                if t == "content_block_delta":
                    delta = ev.get("delta", {})
                    if delta.get("type") == "text_delta":
                        yield delta.get("text", "")
                elif t == "message_start":
                    usage = ev.get("message", {}).get("usage", {})
                    in_t = usage.get("input_tokens", in_t)
                    out_t = usage.get("output_tokens", out_t)
                elif t == "message_delta":
                    usage = ev.get("usage", {})
                    out_t = usage.get("output_tokens", out_t)
            _record("glm-intl", GLM_MODEL, in_t=in_t, out_t=out_t)

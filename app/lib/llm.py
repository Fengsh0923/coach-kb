"""LLM + embedding clients. Main: GLM-4.6 via Anthropic Messages API. Embed: OpenAI."""
from __future__ import annotations
import os
import json
import httpx
from typing import AsyncGenerator

GLM_KEY = os.environ.get("GLM_INTL_API_KEY", "")
GLM_BASE = os.environ.get("GLM_INTL_BASE_URL", "https://api.z.ai/api/anthropic")
GLM_MODEL = os.environ.get("GLM_MODEL", "glm-4.6")

OPENAI_KEY = os.environ.get("OPENAI_API_KEY", "")
OPENAI_EMBED_MODEL = "text-embedding-3-small"


async def embed(texts: list[str]) -> list[list[float]]:
    if not OPENAI_KEY:
        raise RuntimeError("OPENAI_API_KEY not set")
    async with httpx.AsyncClient(timeout=60) as client:
        r = await client.post(
            "https://api.openai.com/v1/embeddings",
            headers={"Authorization": f"Bearer {OPENAI_KEY}", "Content-Type": "application/json"},
            json={"model": OPENAI_EMBED_MODEL, "input": texts},
        )
        r.raise_for_status()
        return [d["embedding"] for d in r.json()["data"]]


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
                if ev.get("type") == "content_block_delta":
                    delta = ev.get("delta", {})
                    if delta.get("type") == "text_delta":
                        yield delta.get("text", "")

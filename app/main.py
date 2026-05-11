"""Coach KB v1 — FastAPI app.

Routes:
  GET  /                  — home page
  GET  /wiki/{slug}       — markdown wiki page
  GET  /qa                — Q&A page (HTML)
  POST /api/qa            — RAG Q&A streaming (SSE)
  GET  /api/search?q=…    — hybrid search (FTS + vec)
  GET  /api                — status JSON
  GET  /health            — health check
"""
from __future__ import annotations
import asyncio
import json
import os
from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse
from fastapi.templating import Jinja2Templates
import frontmatter
import markdown as md_lib

from lib import db, llm
import routes_eval

APP_DIR = Path(__file__).parent
CONTENT_DIR = APP_DIR / "content"

app = FastAPI(title="Coach KB v1")
templates = Jinja2Templates(directory=str(APP_DIR / "templates"))


def list_competencies():
    """Read from filesystem (cheap, no DB needed for nav)."""
    items = []
    for f in sorted(CONTENT_DIR.glob("competency_*.md")):
        try:
            post = frontmatter.load(f)
            items.append({
                "slug": f.stem,
                "icf_id": post.get("icf_competency"),
                "en": post.get("en_name"),
                "zh": post.get("zh_name"),
                "category": post.get("category"),
                "levels": post.get("levels", []),
            })
        except Exception:
            continue
    return items


@app.on_event("startup")
async def startup():
    try:
        db.init_schema()
    except Exception as e:
        print(f"[startup] db init failed (non-fatal): {e}")


@app.get("/", response_class=HTMLResponse)
def home(request: Request):
    return templates.TemplateResponse(request=request, name="index.html",
                                       context={"competencies": list_competencies()})


@app.get("/wiki/{slug}", response_class=HTMLResponse)
def wiki(request: Request, slug: str):
    f = CONTENT_DIR / f"{slug}.md"
    if not f.exists():
        raise HTTPException(404, "页面未找到")
    post = frontmatter.load(f)
    html = md_lib.markdown(post.content, extensions=["fenced_code", "tables", "toc"])
    return templates.TemplateResponse(request=request, name="wiki.html", context={
        "title": f"{post.get('zh_name')} · Coach KB",
        "zh_name": post.get("zh_name"),
        "en_name": post.get("en_name"),
        "category": post.get("category"),
        "icf_id": post.get("icf_competency"),
        "levels": post.get("levels", []),
        "html": html,
        "all": list_competencies(),
    })


@app.get("/qa", response_class=HTMLResponse)
def qa_page(request: Request):
    return templates.TemplateResponse(request=request, name="qa.html",
                                       context={"competencies": list_competencies()})


@app.get("/eval", response_class=HTMLResponse)
def eval_page(request: Request):
    return templates.TemplateResponse(request=request, name="eval.html",
                                       context={"competencies": list_competencies()})


@app.get("/api")
def api_info():
    return {"app": "Coach KB v1", "status": "live",
            "endpoints": ["/api/search", "/api/qa (POST)", "/api/eval (POST)"],
            "ts": datetime.now(timezone.utc).isoformat()}


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/api/search")
async def search(q: str = "", k: int = 10):
    """Hybrid search: FTS5 (trigram) + vec (semantic), RRF-fused."""
    q = (q or "").strip()
    if not q:
        return {"q": q, "results": []}
    try:
        with db.connect() as conn:
            fts = db.search_fts(conn, q, k=k * 2)
            vec_results = []
            try:
                emb = (await llm.embed([q]))[0]
                vec_results = db.search_vec(conn, emb, k=k * 2)
            except Exception as e:
                print(f"[search] vec failed: {e}")
            # RRF fusion
            scores: dict[str, float] = {}
            meta: dict[str, dict] = {}
            for rank, r in enumerate(fts):
                key = r["slug"]
                scores[key] = scores.get(key, 0) + 1.0 / (60 + rank)
                meta.setdefault(key, r)
            for rank, r in enumerate(vec_results):
                key = r["slug"]
                scores[key] = scores.get(key, 0) + 1.0 / (60 + rank)
                meta.setdefault(key, {"slug": key, "title": r["title"],
                                       "category": r["category"],
                                       "snippet": r["content_md"][:160]})
            ranked = sorted(scores.items(), key=lambda kv: -kv[1])[:k]
            return {"q": q, "results": [{
                "slug": s, "title": meta[s].get("title"),
                "category": meta[s].get("category"),
                "snippet": meta[s].get("snippet", ""),
                "score": round(sc, 4),
            } for s, sc in ranked]}
    except Exception as e:
        return JSONResponse({"q": q, "error": str(e), "results": []}, status_code=500)


@app.post("/api/qa")
async def qa(request: Request):
    body = await request.json()
    question = (body.get("q") or "").strip()
    if not question:
        return JSONResponse({"error": "q is required"}, status_code=400)

    # Retrieve top-K context
    citations = []
    context_blocks = []
    try:
        with db.connect() as conn:
            emb = (await llm.embed([question]))[0]
            hits = db.search_vec(conn, emb, k=4)
            for h in hits:
                citations.append({"slug": h["slug"], "title": h["title"]})
                context_blocks.append(f"## {h['title']}（slug={h['slug']}）\n\n{h['content_md']}")
    except Exception as e:
        return JSONResponse({"error": f"retrieval failed: {e}"}, status_code=500)

    system = (
        "你是「Coach KB」——专为 ICF ACC/PCC 备考学习者服务的中文教练知识助手。"
        "你必须严格基于下面提供的知识库片段回答用户问题，不要编造未提供的信息。"
        "用中文回答，语气专业且温暖。结尾必须用 footnote 风格列出引用源（slug）。"
        "如果知识库片段不足以回答，诚实说明并建议查看相关 wiki 页面。"
        f"\n\n## 知识库相关片段\n\n{chr(10).join(context_blocks)}"
    )

    async def gen():
        # First: emit citations event so frontend can render footnotes
        yield f"event: citations\ndata: {json.dumps(citations, ensure_ascii=False)}\n\n"
        full_text = ""
        try:
            async for chunk in llm.chat_stream(system=system, user=question, max_tokens=2048):
                full_text += chunk
                yield f"data: {json.dumps({'chunk': chunk}, ensure_ascii=False)}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'error': str(e)}, ensure_ascii=False)}\n\n"
        # Log
        try:
            with db.connect() as conn:
                conn.execute(
                    "INSERT INTO qa_log (question, answer_md, citations) VALUES (?, ?, ?)",
                    (question, full_text, json.dumps(citations, ensure_ascii=False)),
                )
                conn.commit()
        except Exception:
            pass
        yield "event: done\ndata: {}\n\n"

    return StreamingResponse(gen(), media_type="text/event-stream")


app.include_router(routes_eval.router)

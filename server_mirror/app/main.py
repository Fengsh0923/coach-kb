from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from datetime import datetime, timezone
from pathlib import Path
import frontmatter
import markdown as md_lib

APP_DIR = Path(__file__).parent
CONTENT_DIR = APP_DIR / "content"

app = FastAPI(title="Coach KB v1")
templates = Jinja2Templates(directory=str(APP_DIR / "templates"))

def list_competencies():
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

@app.get("/api")
def api_info():
    return {"app":"Coach KB v1","status":"scaffold-online",
            "endpoints_planned":["/api/search","/api/qa","/api/eval"],
            "ts":datetime.now(timezone.utc).isoformat()}

@app.get("/health")
def health(): return {"status":"ok"}

@app.get("/api/search")
def search(q: str = ""):
    if not q: return {"q":q,"results":[],"msg":"请输入关键词"}
    matches = []
    ql = q.lower()
    for f in sorted(CONTENT_DIR.glob("competency_*.md")):
        post = frontmatter.load(f)
        text = (post.get("zh_name","") + " " + post.content).lower()
        if ql in text:
            matches.append({"slug": f.stem, "title": post.get("zh_name"),
                            "snippet": post.content[:200]})
    return {"q":q, "results":matches, "msg":"v1 朴素 in-memory 搜索（明天 Codex 升级 FTS5+vec）"}

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from datetime import datetime, timezone
from pathlib import Path

app = FastAPI(title="Coach KB v1")
templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))

@app.get("/", response_class=HTMLResponse)
def home(request: Request):
    return templates.TemplateResponse(request=request, name="index.html")

@app.get("/api")
def api_info():
    return {
        "app": "Coach KB v1",
        "status": "scaffold-online",
        "endpoints_planned": ["/api/search", "/api/qa", "/api/eval"],
        "ts": datetime.now(timezone.utc).isoformat(),
    }

@app.get("/health")
def health():
    return {"status": "ok"}

@app.get("/api/search")
def search_placeholder(q: str = ""):
    return JSONResponse({"q": q, "results": [], "msg": "搜索功能由甜虾·Codex 明天实现"})

@app.get("/api/qa")
def qa_placeholder(q: str = ""):
    return JSONResponse({"q": q, "answer": "", "msg": "问答功能由甜虾·Codex 明天实现"})

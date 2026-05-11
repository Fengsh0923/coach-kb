"""FastAPI route for transcript replay evaluation."""
from __future__ import annotations

import hashlib
import json
import time
from collections import defaultdict, deque

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from lib import db
from lib.eval import evaluate

router = APIRouter()
_WINDOW_SECONDS = 60
_MAX_PER_WINDOW = 3
_hits: dict[str, deque[float]] = defaultdict(deque)


def _client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for", "")
    if forwarded:
        return forwarded.split(",", 1)[0].strip()
    return request.client.host if request.client else "unknown"


def _session_id(ip: str, ua: str) -> str:
    today = time.strftime("%Y-%m-%d", time.gmtime())
    seed = f"{today}|{ip}|{ua}"
    return hashlib.sha256(seed.encode("utf-8")).hexdigest()[:32]


def _limited(ip: str) -> bool:
    now = time.time()
    bucket = _hits[ip]
    while bucket and now - bucket[0] >= _WINDOW_SECONDS:
        bucket.popleft()
    if len(bucket) >= _MAX_PER_WINDOW:
        return True
    bucket.append(now)
    return False


def _ensure_eval_session_columns(conn) -> None:
    conn.execute(
        "CREATE TABLE IF NOT EXISTS eval_session ("
        "id INTEGER PRIMARY KEY AUTOINCREMENT, "
        "transcript TEXT, result_json TEXT, "
        "ts DATETIME DEFAULT CURRENT_TIMESTAMP)"
    )
    columns = {row["name"] for row in conn.execute("PRAGMA table_info(eval_session)").fetchall()}
    if "session_id" not in columns:
        conn.execute("ALTER TABLE eval_session ADD COLUMN session_id TEXT")
    conn.commit()


def _log_eval(conn, *, session_id: str, transcript: str, result: dict) -> None:
    _ensure_eval_session_columns(conn)
    conn.execute(
        "INSERT INTO eval_session (session_id, transcript, result_json) VALUES (?, ?, ?)",
        (session_id, transcript, json.dumps(result, ensure_ascii=False)),
    )
    conn.commit()


@router.post("/api/eval")
async def eval_endpoint(request: Request):
    ip = _client_ip(request)
    if _limited(ip):
        return JSONResponse({"error": "rate limit exceeded"}, status_code=429)

    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"error": "invalid JSON body"}, status_code=400)

    if body.get("consent") is not True:
        return JSONResponse({"error": "consent=true is required"}, status_code=403)

    transcript = (body.get("transcript") or "").strip()
    if not transcript:
        return JSONResponse({"error": "transcript is required"}, status_code=400)

    ua = request.headers.get("user-agent", "")
    sid = _session_id(ip, ua)
    try:
        with db.connect() as conn:
            result = await evaluate(transcript, conn)
            _log_eval(conn, session_id=sid, transcript=transcript, result=result)
        status = 500 if "error" in result else 200
        return JSONResponse(result, status_code=status)
    except Exception as exc:
        return JSONResponse({"error": str(exc)}, status_code=500)

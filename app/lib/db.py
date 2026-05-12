"""SQLite + sqlite-vec data layer for Coach KB v1."""
from __future__ import annotations
import sqlite3
import json
from pathlib import Path
import sqlite_vec

DB_PATH = Path("/data/coach.db")


def connect() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.enable_load_extension(True)
    sqlite_vec.load(conn)
    conn.enable_load_extension(False)
    conn.row_factory = sqlite3.Row
    return conn


SCHEMA = """
CREATE TABLE IF NOT EXISTS source (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  type TEXT, title TEXT NOT NULL, author TEXT, url TEXT, license TEXT,
  added_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS doc (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  source_id INTEGER REFERENCES source(id),
  slug TEXT UNIQUE NOT NULL,
  title TEXT NOT NULL,
  category TEXT,
  content_md TEXT NOT NULL,
  meta TEXT,
  updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
CREATE VIRTUAL TABLE IF NOT EXISTS doc_fts USING fts5(
  title, content_md, content='doc', content_rowid='id', tokenize='trigram'
);
CREATE VIRTUAL TABLE IF NOT EXISTS doc_vec USING vec0(
  doc_id INTEGER PRIMARY KEY,
  embedding FLOAT[1024]
);
CREATE TABLE IF NOT EXISTS qa_log (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  question TEXT, answer_md TEXT, citations TEXT,
  user_session TEXT, ts DATETIME DEFAULT CURRENT_TIMESTAMP,
  feedback_score INTEGER
);
CREATE TABLE IF NOT EXISTS eval_session (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  transcript TEXT, result_json TEXT,
  ts DATETIME DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS usage_log (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  endpoint TEXT,
  provider TEXT,
  model TEXT,
  input_tokens INTEGER DEFAULT 0,
  output_tokens INTEGER DEFAULT 0,
  cost_usd REAL DEFAULT 0,
  ts DATETIME DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_usage_ts ON usage_log(ts);
CREATE TABLE IF NOT EXISTS learning_module (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  slug TEXT UNIQUE NOT NULL,
  title TEXT NOT NULL,
  order_num INTEGER NOT NULL,
  est_hours INTEGER,
  content_md TEXT NOT NULL,
  related_wiki_slugs TEXT,
  practice_coachpro_client TEXT,
  updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS user_pseudo (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  pseudo_id TEXT UNIQUE NOT NULL,
  export_token TEXT UNIQUE NOT NULL,
  progress_json TEXT NOT NULL DEFAULT '{}',
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_pseudo_token ON user_pseudo(export_token);
"""


# ─── user_pseudo helpers（匿名 UUID 跨设备进度同步）──────────────────────

import secrets as _secrets


def _gen_pseudo_id() -> str:
    """16 字符 url-safe UUID"""
    return _secrets.token_urlsafe(12)[:16]


def _gen_export_token() -> str:
    """便于人工输入的 12 字符 token，格式 COACH-XXXX-XXXX"""
    alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"  # 去掉易混淆 I/O/0/1
    chunk1 = "".join(_secrets.choice(alphabet) for _ in range(4))
    chunk2 = "".join(_secrets.choice(alphabet) for _ in range(4))
    return f"COACH-{chunk1}-{chunk2}"


def create_pseudo_user(conn) -> dict:
    """创建一个新的匿名用户，返回 {pseudo_id, export_token}。"""
    # 重试最多 5 次防 token 碰撞（实际 32^8 = 1T 组合，碰撞极低）
    for _ in range(5):
        pid = _gen_pseudo_id()
        tok = _gen_export_token()
        try:
            conn.execute(
                "INSERT INTO user_pseudo (pseudo_id, export_token) VALUES (?, ?)",
                (pid, tok),
            )
            conn.commit()
            return {"pseudo_id": pid, "export_token": tok, "progress": {}}
        except Exception:
            continue
    raise RuntimeError("create_pseudo_user: 5 次重试后仍 token 碰撞")


def get_pseudo_progress(conn, pseudo_id: str) -> dict | None:
    row = conn.execute(
        "SELECT pseudo_id, export_token, progress_json FROM user_pseudo WHERE pseudo_id = ?",
        (pseudo_id,),
    ).fetchone()
    if not row:
        return None
    try:
        prog = json.loads(row["progress_json"] or "{}")
    except Exception:
        prog = {}
    return {"pseudo_id": row["pseudo_id"], "export_token": row["export_token"], "progress": prog}


def save_pseudo_progress(conn, pseudo_id: str, progress: dict) -> bool:
    res = conn.execute(
        "UPDATE user_pseudo SET progress_json = ?, updated_at = CURRENT_TIMESTAMP WHERE pseudo_id = ?",
        (json.dumps(progress, ensure_ascii=False), pseudo_id),
    )
    conn.commit()
    return res.rowcount > 0


def find_pseudo_by_token(conn, export_token: str) -> dict | None:
    """根据 export_token 查回 pseudo（用于跨设备导入）。"""
    row = conn.execute(
        "SELECT pseudo_id, export_token, progress_json FROM user_pseudo WHERE export_token = ?",
        (export_token,),
    ).fetchone()
    if not row:
        return None
    try:
        prog = json.loads(row["progress_json"] or "{}")
    except Exception:
        prog = {}
    return {"pseudo_id": row["pseudo_id"], "export_token": row["export_token"], "progress": prog}


def upsert_module(conn, *, slug, title, order_num, est_hours, content_md,
                   related_wiki_slugs=None, practice_coachpro_client=None):
    """Upsert a learning module record (idempotent on slug)."""
    import json as _json
    conn.execute(
        "INSERT INTO learning_module (slug, title, order_num, est_hours, content_md, "
        "related_wiki_slugs, practice_coachpro_client) VALUES (?, ?, ?, ?, ?, ?, ?) "
        "ON CONFLICT(slug) DO UPDATE SET title=excluded.title, order_num=excluded.order_num, "
        "est_hours=excluded.est_hours, content_md=excluded.content_md, "
        "related_wiki_slugs=excluded.related_wiki_slugs, "
        "practice_coachpro_client=excluded.practice_coachpro_client, "
        "updated_at=CURRENT_TIMESTAMP",
        (slug, title, order_num, est_hours, content_md,
         _json.dumps(related_wiki_slugs or [], ensure_ascii=False),
         practice_coachpro_client),
    )


def all_modules(conn) -> list[dict]:
    rows = conn.execute(
        "SELECT slug, title, order_num, est_hours, content_md, related_wiki_slugs, "
        "practice_coachpro_client FROM learning_module ORDER BY order_num"
    ).fetchall()
    import json as _json
    out = []
    for r in rows:
        d = dict(r)
        try:
            d["related_wiki_slugs"] = _json.loads(d["related_wiki_slugs"] or "[]")
        except Exception:
            d["related_wiki_slugs"] = []
        out.append(d)
    return out


def get_module(conn, slug: str) -> dict | None:
    row = conn.execute(
        "SELECT slug, title, order_num, est_hours, content_md, related_wiki_slugs, "
        "practice_coachpro_client FROM learning_module WHERE slug = ?",
        (slug,),
    ).fetchone()
    if not row:
        return None
    import json as _json
    d = dict(row)
    try:
        d["related_wiki_slugs"] = _json.loads(d["related_wiki_slugs"] or "[]")
    except Exception:
        d["related_wiki_slugs"] = []
    return d


def log_usage(*, endpoint: str, provider: str, model: str,
              input_tokens: int = 0, output_tokens: int = 0, cost_usd: float = 0.0):
    """Best-effort usage record—never raises."""
    try:
        with connect() as conn:
            conn.execute(
                "INSERT INTO usage_log (endpoint, provider, model, input_tokens, output_tokens, cost_usd) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (endpoint, provider, model, input_tokens, output_tokens, cost_usd),
            )
            conn.commit()
    except Exception as e:
        print(f"[usage_log] {e}")


def init_schema():
    with connect() as conn:
        conn.executescript(SCHEMA)


def upsert_doc(conn: sqlite3.Connection, *, slug: str, title: str,
               category: str, content_md: str, meta: dict,
               source_id: int | None = None) -> int:
    cur = conn.execute(
        "INSERT INTO doc (source_id, slug, title, category, content_md, meta) "
        "VALUES (?, ?, ?, ?, ?, ?) "
        "ON CONFLICT(slug) DO UPDATE SET title=excluded.title, "
        "category=excluded.category, content_md=excluded.content_md, "
        "meta=excluded.meta, updated_at=CURRENT_TIMESTAMP RETURNING id",
        (source_id, slug, title, category, content_md, json.dumps(meta, ensure_ascii=False)),
    )
    return cur.fetchone()["id"]


def rebuild_fts(conn: sqlite3.Connection):
    conn.execute("INSERT INTO doc_fts(doc_fts) VALUES('rebuild')")


def search_fts(conn: sqlite3.Connection, q: str, k: int = 10) -> list[dict]:
    rows = conn.execute(
        "SELECT d.id, d.slug, d.title, d.category, "
        "snippet(doc_fts, 1, '<mark>', '</mark>', '…', 32) AS snippet, "
        "bm25(doc_fts) AS score "
        "FROM doc_fts JOIN doc d ON d.id = doc_fts.rowid "
        "WHERE doc_fts MATCH ? ORDER BY score LIMIT ?",
        (q, k),
    ).fetchall()
    return [dict(r) for r in rows]


def search_vec(conn: sqlite3.Connection, embedding: list[float], k: int = 10) -> list[dict]:
    import struct
    blob = struct.pack(f"{len(embedding)}f", *embedding)
    rows = conn.execute(
        "SELECT d.id, d.slug, d.title, d.category, d.content_md, v.distance "
        "FROM doc_vec v JOIN doc d ON d.id = v.doc_id "
        "WHERE v.embedding MATCH ? AND k = ? ORDER BY distance",
        (blob, k),
    ).fetchall()
    return [dict(r) for r in rows]


def upsert_vec(conn: sqlite3.Connection, doc_id: int, embedding: list[float]):
    import struct
    blob = struct.pack(f"{len(embedding)}f", *embedding)
    conn.execute("DELETE FROM doc_vec WHERE doc_id = ?", (doc_id,))
    conn.execute("INSERT INTO doc_vec (doc_id, embedding) VALUES (?, ?)", (doc_id, blob))


def all_docs(conn: sqlite3.Connection) -> list[dict]:
    rows = conn.execute("SELECT id, slug, title, category, content_md, meta FROM doc ORDER BY id").fetchall()
    return [dict(r) for r in rows]


def get_doc(conn: sqlite3.Connection, slug: str) -> dict | None:
    row = conn.execute("SELECT * FROM doc WHERE slug = ?", (slug,)).fetchone()
    return dict(row) if row else None

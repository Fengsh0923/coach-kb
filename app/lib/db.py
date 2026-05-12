"""SQLite + sqlite-vec data layer for Coach KB v1."""
from __future__ import annotations
import sqlite3
import json
from pathlib import Path
from typing import Iterable
import frontmatter
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
"""


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

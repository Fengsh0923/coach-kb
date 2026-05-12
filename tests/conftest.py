"""Shared pytest fixtures for Coach KB v1 test suite.

设计原则：
- 不依赖 sqlite-vec（C 扩展，CI 上难装）→ mock
- 不调真 LLM/Embedding API → monkeypatch httpx
- 用 tempfile sqlite DB，跨测试隔离
- FastAPI TestClient 共享
"""
from __future__ import annotations

import os
import sys
import json
import struct
import tempfile
import types
from pathlib import Path

import pytest

# Ensure app is importable
APP_DIR = Path(__file__).resolve().parents[1] / "app"
sys.path.insert(0, str(APP_DIR))

# ─── sqlite_vec mock（C 扩展替身）──────────────────────────────────────────
# 真实 sqlite_vec.load(conn) 会注册 vec0 虚拟表 + MATCH 操作符。
# 测试里不真测向量检索精度，所以用 SQL UDF 替身让 vec0 表能 INSERT/SELECT。
def _install_sqlite_vec_stub():
    """Install minimal sqlite_vec replacement using regular Python tables.

    强制覆盖（不用 setdefault）—— test_eval.py 顶部用 setdefault 设了空 SimpleNamespace
    没有 load 方法，会让 db.py import 时崩。本 conftest 总是被 pytest 优先加载，
    所以这里 set 后其他 test 文件的 setdefault 就跳过。
    """
    fake = types.ModuleType("sqlite_vec")

    def load(conn):
        conn.create_function("__vec_distance", 2, lambda a, b: 0.0)
        return None

    fake.load = load
    sys.modules["sqlite_vec"] = fake  # 强制覆盖

_install_sqlite_vec_stub()


# ─── 现在可以 import db / llm ─────────────────────────────────────────────
from lib import db as _db_module  # noqa: E402
from lib import llm as _llm_module  # noqa: E402


# ─── DB fixtures ──────────────────────────────────────────────────────────
@pytest.fixture
def tmp_db_path(monkeypatch, tmp_path):
    """临时 sqlite db 路径，每测试隔离。"""
    p = tmp_path / "test_coach.db"
    monkeypatch.setattr(_db_module, "DB_PATH", p)
    yield p


@pytest.fixture
def db_conn(tmp_db_path):
    """已 init schema 的 db connection。"""
    # 因为 vec0 是 mock 的，CREATE VIRTUAL TABLE USING vec0 会失败
    # → 走简化 schema（去掉 vec0，保留其他）
    import sqlite3
    conn = sqlite3.connect(tmp_db_path)
    conn.row_factory = sqlite3.Row
    # 直接执行简化 schema（不含 vec0）
    simplified = """
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
    CREATE TABLE IF NOT EXISTS qa_log (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      question TEXT, answer_md TEXT, citations TEXT,
      user_session TEXT, ts DATETIME DEFAULT CURRENT_TIMESTAMP,
      feedback_score INTEGER
    );
    CREATE TABLE IF NOT EXISTS eval_session (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      transcript TEXT, result_json TEXT,
      ts DATETIME DEFAULT CURRENT_TIMESTAMP,
      session_id TEXT
    );
    CREATE TABLE IF NOT EXISTS usage_log (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      endpoint TEXT, provider TEXT, model TEXT,
      input_tokens INTEGER DEFAULT 0, output_tokens INTEGER DEFAULT 0,
      cost_usd REAL DEFAULT 0, ts DATETIME DEFAULT CURRENT_TIMESTAMP
    );
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
    """
    conn.executescript(simplified)
    yield conn
    conn.close()


@pytest.fixture
def patch_db_connect(monkeypatch, db_conn, tmp_db_path):
    """让 db.connect() 返回测试 conn（其实就是新建一个走同样路径）。"""
    import sqlite3

    def fake_connect():
        c = sqlite3.connect(tmp_db_path)
        c.row_factory = sqlite3.Row
        return c

    monkeypatch.setattr(_db_module, "connect", fake_connect)
    yield


@pytest.fixture
def seeded_docs(db_conn):
    """种入 8 篇 competency + 1 篇 tool + 1 篇 module（覆盖 eval 8 项需求）。"""
    db_conn.execute("INSERT INTO source (type, title) VALUES ('test', 'Test Source')")
    src_id = db_conn.execute("SELECT id FROM source LIMIT 1").fetchone()["id"]
    competency_zh = {
        1: "展现伦理实践", 2: "具备教练心态", 3: "建立与维护契约",
        4: "培育信任与安全", 5: "保持临在", 6: "主动倾听",
        7: "唤起觉察", 8: "促进客户成长",
    }
    docs = []
    for i in range(1, 9):
        zh = competency_zh[i]
        docs.append({
            "slug": f"competency_{i:02d}_test",
            "title": zh,
            "category": "Foundation",
            "content": (
                f"# {i}. {zh}\n\n## 一句话定义\n定义。\n\n"
                "## ACC 判定标准（\"做到了\"长什么样）\nACC 证据。\n\n"
                "## PCC 判定标准（比 ACC 更深的地方）\nPCC 深层证据。\n"
            ),
            "meta": {"icf_competency": i, "en_name": f"Competency {i}"},
        })
    # alias for backward compat tests
    docs.append({
        "slug": "competency_07_evokes_awareness",
        "title": "唤起觉察",
        "category": "Communicating",
        "content": "# 7. 唤起觉察\n\nPCC 级 evoking awareness 的判定核心是……",
        "meta": {"icf_competency": 7, "en_name": "Evokes Awareness"},
    })
    docs.append({
        "slug": "tool_grow_model_deep_dive",
        "title": "GROW 模型深度",
        "category": "Reference",
        "content": "# GROW 模型\n\nG-R-O-W 4 阶段……",
        "meta": {"levels": ["ACC", "PCC"]},
    })
    for d in docs:
        db_conn.execute(
            "INSERT INTO doc (source_id, slug, title, category, content_md, meta) "
            "VALUES (?,?,?,?,?,?)",
            (src_id, d["slug"], d["title"], d["category"], d["content"],
             json.dumps(d["meta"], ensure_ascii=False)),
        )
    db_conn.execute("INSERT INTO doc_fts(doc_fts) VALUES('rebuild')")

    # 1 个测试 module
    db_conn.execute(
        "INSERT INTO learning_module (slug, title, order_num, est_hours, content_md, related_wiki_slugs) "
        "VALUES (?,?,?,?,?,?)",
        ("module_99_test", "测试模块", 99, 5, "# 测试模块\n\n本模块用于测试。",
         json.dumps(["competency_07_evokes_awareness"])),
    )
    db_conn.commit()
    yield


# ─── Mock LLM / Embedding ─────────────────────────────────────────────────
@pytest.fixture
def mock_embed(monkeypatch):
    """让 llm.embed 返回固定 1024 维零向量，不调外网。"""
    async def fake_embed(texts):
        return [[0.0] * 1024 for _ in texts]
    monkeypatch.setattr(_llm_module, "embed", fake_embed)
    # 同时 mock db.search_vec —— 因为测试 schema 没有 vec0 虚表
    from lib import db as _db_module
    def fake_search_vec(conn, embedding, k=10):
        # 返回 doc 表里前 k 篇的 dict（模拟向量召回 top-K）
        rows = conn.execute(
            "SELECT id, slug, title, category, content_md FROM doc ORDER BY id LIMIT ?",
            (k,)
        ).fetchall()
        return [{"id": r["id"], "slug": r["slug"], "title": r["title"],
                 "category": r["category"], "content_md": r["content_md"],
                 "distance": 0.5} for r in rows]
    monkeypatch.setattr(_db_module, "search_vec", fake_search_vec)
    yield


@pytest.fixture
def mock_chat_complete(monkeypatch):
    """让 llm.chat_complete 返回可控 JSON。测试可改 fixture。"""
    response_holder = {"text": '{"ok": true}'}

    async def fake_chat_complete(**kwargs):
        return response_holder["text"]

    monkeypatch.setattr(_llm_module, "chat_complete", fake_chat_complete)
    yield response_holder  # 测试可改 .text 控制响应


@pytest.fixture
def mock_chat_stream(monkeypatch):
    """让 llm.chat_stream 返回固定流。"""
    chunks_holder = {"chunks": ["你好", "，", "世界"]}

    async def fake_stream(**kwargs):
        for c in chunks_holder["chunks"]:
            yield c

    monkeypatch.setattr(_llm_module, "chat_stream", fake_stream)
    yield chunks_holder


# ─── FastAPI TestClient ────────────────────────────────────────────────────
@pytest.fixture
def app_with_content(tmp_path, monkeypatch, patch_db_connect, seeded_docs,
                     mock_embed, mock_chat_complete, mock_chat_stream):
    """完整 FastAPI app（自带种子内容 + mock LLM）。"""
    # 准备 content/ 目录给 list_competencies / list_tools / wiki 路由用
    content_dir = tmp_path / "content"
    content_dir.mkdir()
    # 1 篇 competency
    (content_dir / "competency_07_evokes_awareness.md").write_text(
        "---\nicf_competency: 7\nen_name: Evokes Awareness\nzh_name: 唤起觉察\n"
        "category: Communicating\nlevels: [ACC, PCC]\n---\n\n# 7. 唤起觉察\n\n测试内容。\n",
        encoding="utf-8",
    )
    # 1 篇 tool
    (content_dir / "tool_grow_model_deep_dive.md").write_text(
        "---\ntitle: GROW 模型深度\ncategory: Reference\n---\n\n# GROW\n\n测试内容。\n",
        encoding="utf-8",
    )
    # resources_curated
    (content_dir / "resources_curated.md").write_text(
        "---\ntitle: 资源精选\n---\n\n# 资源\n\nXX。\n",
        encoding="utf-8",
    )
    # template 目录路径透传给 app
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-fake-key")
    monkeypatch.setenv("DASHSCOPE_API_KEY", "test-fake-key")

    # Patch main.py 的 CONTENT_DIR + APP_DIR/templates 用真实模板
    import main as main_mod  # noqa: E402
    monkeypatch.setattr(main_mod, "CONTENT_DIR", content_dir)

    # 重新初始化 templates （指向真实 templates 目录）
    from fastapi.templating import Jinja2Templates
    real_templates_dir = APP_DIR / "templates"
    monkeypatch.setattr(main_mod, "templates", Jinja2Templates(directory=str(real_templates_dir)))

    return main_mod.app


@pytest.fixture
def client(app_with_content, monkeypatch):
    """FastAPI TestClient（同步 HTTP 测试）。每个测试都重置限速桶。"""
    # 重置 routes_eval 模块级限速 dict
    import routes_eval  # noqa: E402
    routes_eval._hits.clear()
    # 重置 main 模块级 qa 限速桶
    import main  # noqa: E402
    if hasattr(main, "_qa_minute"):
        main._qa_minute.clear()
    if hasattr(main, "_qa_hour"):
        main._qa_hour.clear()
    from fastapi.testclient import TestClient
    return TestClient(app_with_content)

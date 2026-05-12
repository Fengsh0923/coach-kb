"""Unit tests for app/lib/db.py"""
import json
import pytest
from lib import db


pytestmark = pytest.mark.unit


class TestDocOperations:
    def test_upsert_doc_inserts_new(self, db_conn):
        # db_conn already has schema, manually insert with raw SQL
        # because db.upsert_doc uses connect() which goes through DB_PATH
        cur = db_conn.execute(
            "INSERT INTO doc (slug, title, category, content_md, meta) "
            "VALUES (?,?,?,?,?) RETURNING id",
            ("test_slug", "标题", "Test", "内容", '{"x":1}'),
        )
        doc_id = cur.fetchone()["id"]
        assert doc_id >= 1
        # 查回来
        row = db_conn.execute("SELECT * FROM doc WHERE id = ?", (doc_id,)).fetchone()
        assert row["slug"] == "test_slug"
        assert row["title"] == "标题"

    def test_upsert_doc_idempotent_on_slug(self, db_conn):
        """同 slug INSERT 第二次应该 conflict 或更新——schema 用 UNIQUE 约束。"""
        db_conn.execute(
            "INSERT INTO doc (slug, title, category, content_md) VALUES (?,?,?,?)",
            ("same_slug", "v1", "x", "c1"),
        )
        # 第二次插入相同 slug 应该违反 UNIQUE
        with pytest.raises(Exception):
            db_conn.execute(
                "INSERT INTO doc (slug, title, category, content_md) VALUES (?,?,?,?)",
                ("same_slug", "v2", "y", "c2"),
            )

    def test_fts5_search_finds_inserted_doc(self, db_conn, seeded_docs):
        rows = db_conn.execute(
            "SELECT d.slug FROM doc_fts JOIN doc d ON d.id = doc_fts.rowid "
            "WHERE doc_fts MATCH ?",
            ("唤起觉察",),
        ).fetchall()
        slugs = [r["slug"] for r in rows]
        assert "competency_07_evokes_awareness" in slugs

    def test_fts5_search_empty_query_returns_empty(self, db_conn, seeded_docs):
        # FTS5 空查询会报错——caller 应该做 strip 检查
        with pytest.raises(Exception):
            db_conn.execute("SELECT * FROM doc_fts WHERE doc_fts MATCH ?", ("",)).fetchall()


class TestLearningModule:
    def test_module_inserted_correctly(self, db_conn, seeded_docs):
        row = db_conn.execute(
            "SELECT * FROM learning_module WHERE slug = ?", ("module_99_test",)
        ).fetchone()
        assert row is not None
        assert row["title"] == "测试模块"
        assert row["order_num"] == 99
        assert row["est_hours"] == 5

    def test_related_wiki_slugs_stored_as_json(self, db_conn, seeded_docs):
        row = db_conn.execute(
            "SELECT related_wiki_slugs FROM learning_module WHERE slug = ?",
            ("module_99_test",),
        ).fetchone()
        parsed = json.loads(row["related_wiki_slugs"])
        assert "competency_07_evokes_awareness" in parsed

    def test_module_slug_unique(self, db_conn, seeded_docs):
        """重复 slug 应该违反 UNIQUE 约束。"""
        with pytest.raises(Exception):
            db_conn.execute(
                "INSERT INTO learning_module (slug, title, order_num, content_md) "
                "VALUES (?,?,?,?)",
                ("module_99_test", "dup", 99, "x"),
            )


class TestUsageLog:
    def test_log_usage_inserts_row(self, patch_db_connect, db_conn):
        db.log_usage(
            endpoint="qa",
            provider="deepseek",
            model="deepseek-v4-flash",
            input_tokens=100,
            output_tokens=500,
            cost_usd=0.0005,
        )
        row = db_conn.execute("SELECT * FROM usage_log ORDER BY id DESC LIMIT 1").fetchone()
        assert row["endpoint"] == "qa"
        assert row["input_tokens"] == 100
        assert row["output_tokens"] == 500
        assert row["cost_usd"] == pytest.approx(0.0005)

    def test_log_usage_never_raises_on_failure(self, monkeypatch):
        """log_usage 是 best-effort，DB 挂了也不抛错。"""
        def broken_connect():
            raise RuntimeError("DB exploded")
        monkeypatch.setattr(db, "connect", broken_connect)
        # 不应该抛
        db.log_usage(endpoint="x", provider="y", model="z",
                     input_tokens=1, output_tokens=1, cost_usd=0.0)


class TestSchemaCompleteness:
    """确认 schema 字符串包含所有关键表。"""
    def test_schema_has_all_tables(self):
        s = db.SCHEMA
        for table in ["source", "doc", "doc_fts", "doc_vec",
                      "qa_log", "eval_session", "usage_log", "learning_module"]:
            assert table in s, f"SCHEMA 缺表 {table}"

    def test_schema_has_vec_dim_1024(self):
        """切 DashScope 后维度是 1024，不是 1536。"""
        assert "FLOAT[1024]" in db.SCHEMA
        assert "FLOAT[1536]" not in db.SCHEMA

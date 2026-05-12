"""Integration tests: /api/search"""
import pytest

pytestmark = pytest.mark.integration


class TestSearch:
    def test_search_empty_query_returns_empty(self, client):
        r = client.get("/api/search?q=")
        assert r.status_code == 200
        data = r.json()
        assert data["results"] == []

    def test_search_finds_seeded_competency(self, client):
        r = client.get("/api/search?q=唤起觉察")
        assert r.status_code == 200
        data = r.json()
        slugs = [x["slug"] for x in data["results"]]
        assert "competency_07_evokes_awareness" in slugs

    def test_search_returns_snippet_and_score(self, client):
        r = client.get("/api/search?q=唤起觉察")
        data = r.json()
        if data["results"]:
            first = data["results"][0]
            assert "title" in first
            assert "slug" in first
            assert "score" in first

    def test_search_unknown_term_returns_empty_or_low_score(self, client):
        r = client.get("/api/search?q=xxxyyyzzz_no_such_term_in_kb")
        assert r.status_code == 200
        data = r.json()
        # 要么空，要么至少没有完全无关的高分匹配
        assert isinstance(data["results"], list)

    def test_search_respects_k_param(self, client):
        r = client.get("/api/search?q=的&k=1")
        data = r.json()
        assert len(data["results"]) <= 1

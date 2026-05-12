"""Integration tests: /wiki/{slug} 路由"""
import pytest

pytestmark = pytest.mark.integration


class TestWikiRoutes:
    def test_existing_competency_wiki_renders(self, client):
        r = client.get("/wiki/competency_07_evokes_awareness")
        assert r.status_code == 200
        # 标题或 markdown 渲染结果包含中文标题
        assert "唤起觉察" in r.text

    def test_existing_tool_wiki_renders(self, client):
        r = client.get("/wiki/tool_grow_model_deep_dive")
        assert r.status_code == 200
        assert "GROW" in r.text

    def test_unknown_wiki_returns_404(self, client):
        r = client.get("/wiki/nonexistent_slug_12345")
        assert r.status_code == 404

    def test_resources_page_renders(self, client):
        """/resources 复用 wiki.html 模板。"""
        r = client.get("/resources")
        assert r.status_code == 200
        assert "资源" in r.text or "Resources" in r.text or "Coaching" in r.text

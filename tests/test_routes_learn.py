"""Integration tests: /learn 课程平台路由"""
import pytest

pytestmark = pytest.mark.integration


class TestLearnRoutes:
    def test_learn_index_returns_html(self, client):
        r = client.get("/learn")
        assert r.status_code == 200
        assert "text/html" in r.headers.get("content-type", "")

    def test_learn_index_lists_seeded_module(self, client):
        r = client.get("/learn")
        # seeded_docs fixture 加了 module_99_test
        assert "测试模块" in r.text or "module_99_test" in r.text

    def test_learn_module_detail_renders(self, client):
        r = client.get("/learn/module_99_test")
        assert r.status_code == 200
        assert "测试模块" in r.text
        assert "完成" in r.text  # 标记完成按钮

    def test_learn_unknown_module_returns_404(self, client):
        r = client.get("/learn/module_does_not_exist")
        assert r.status_code == 404

    def test_api_learn_modules_returns_json(self, client):
        r = client.get("/api/learn/modules")
        assert r.status_code == 200
        data = r.json()
        assert "modules" in data
        assert isinstance(data["modules"], list)

    def test_api_learn_modules_includes_test_seed(self, client):
        r = client.get("/api/learn/modules")
        slugs = [m["slug"] for m in r.json()["modules"]]
        assert "module_99_test" in slugs

    def test_api_learn_modules_has_required_fields(self, client):
        r = client.get("/api/learn/modules")
        for m in r.json()["modules"]:
            assert "slug" in m
            assert "title" in m
            assert "order_num" in m

    def test_learn_module_includes_progress_js(self, client):
        """详情页应包含 localStorage 进度逻辑。"""
        r = client.get("/learn/module_99_test")
        assert "localStorage" in r.text
        assert "coach-kb-progress" in r.text

    def test_learn_module_links_related_wiki(self, client):
        """seeded module_99_test 的 related_wiki_slugs = [competency_07_evokes_awareness]。"""
        r = client.get("/learn/module_99_test")
        assert "competency_07_evokes_awareness" in r.text or "唤起觉察" in r.text

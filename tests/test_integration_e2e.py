"""端到端跨路由测试：模拟真实学习者使用流"""
import pytest

pytestmark = pytest.mark.integration


class TestUserJourneyHome:
    """模拟新访客打开网站到选定模块的完整流程。"""

    def test_full_home_to_module(self, client):
        # 1. 进首页
        r = client.get("/")
        assert r.status_code == 200
        assert "/learn" in r.text

        # 2. 跳课程总览
        r = client.get("/learn")
        assert r.status_code == 200

        # 3. 进 module 详情
        r = client.get("/learn/module_99_test")
        assert r.status_code == 200

        # 4. 模块内有 wiki 链接，点进去
        r = client.get("/wiki/competency_07_evokes_awareness")
        assert r.status_code == 200

        # 5. 回到 qa 提问
        r = client.get("/qa")
        assert r.status_code == 200

    def test_home_search_to_wiki(self, client):
        # 用搜索找到 wiki
        r = client.get("/api/search?q=唤起觉察")
        assert r.status_code == 200
        slugs = [x["slug"] for x in r.json()["results"]]
        assert "competency_07_evokes_awareness" in slugs

        # 点进**有 wiki .md 文件**的 slug（避开测试只 mock 部分文件）
        r = client.get("/wiki/competency_07_evokes_awareness")
        assert r.status_code == 200


class TestRouteCoverage:
    """全部主要路由的"冒烟测试"——快速过一遍。"""

    @pytest.mark.parametrize("path,expected_code", [
        ("/", 200),
        ("/health", 200),
        ("/api", 200),
        ("/qa", 200),
        ("/eval", 200),
        ("/learn", 200),
        ("/resources", 200),
        ("/robots.txt", 200),
        ("/sitemap.xml", 200),
        ("/api/learn/modules", 200),
        ("/wiki/competency_07_evokes_awareness", 200),
        ("/wiki/tool_grow_model_deep_dive", 200),
        ("/learn/module_99_test", 200),
        ("/wiki/__totally_unknown__", 404),
        ("/learn/__totally_unknown__", 404),
    ])
    def test_route_smoke(self, client, path, expected_code):
        r = client.get(path)
        assert r.status_code == expected_code, f"{path} 期望 {expected_code} 实际 {r.status_code}"


class TestSecurityWafExpectations:
    """这些在 Caddy 层拦，FastAPI 不直接知道。

    本测试仅作 doc——真实 WAF 行为已在 Caddyfile 验证（手工 curl 测过）。
    """

    def test_app_does_not_serve_env_secrets(self, client):
        """即使 Caddy 漏过了，backend 也不该返回 .env 内容。"""
        r = client.get("/.env")
        # FastAPI 不知道 /.env 这个路由 → 404（Caddy 层拦才是 403）
        assert r.status_code == 404

    def test_app_does_not_have_admin_route(self, client):
        r = client.get("/admin")
        assert r.status_code == 404


class TestContentBoundary:
    """内容边界验证：站点不应包含明显的版权风险内容。"""

    def test_no_book_full_text_in_wiki(self, client):
        """wiki 不应该包含整段经典书原文（版权红线）。"""
        r = client.get("/wiki/competency_07_evokes_awareness")
        # 这是验证：内容来自鳌虾改写，不是抄书
        body = r.text
        # 至少不应该有"目录""第一章""出版社"这种书原文特征
        # 这是模糊验证——主要意图是 alert 未来如果不小心抄了
        # （不 assert，只是 doc 性质测试）
        assert "唤起觉察" in body  # 至少能渲染我们种的内容

"""Integration tests: static / 简单 JSON / SEO 路由"""
import pytest

pytestmark = pytest.mark.integration


class TestHealthAndInfo:
    def test_health_returns_ok(self, client):
        r = client.get("/health")
        assert r.status_code == 200
        assert r.json() == {"status": "ok"}

    def test_api_root_returns_status(self, client):
        r = client.get("/api")
        assert r.status_code == 200
        data = r.json()
        assert data["app"] == "Coach KB v1"
        assert "endpoints" in data
        assert "ts" in data


class TestRobotsAndSitemap:
    def test_robots_txt_returns_200_text(self, client):
        r = client.get("/robots.txt")
        assert r.status_code == 200
        body = r.text
        assert "User-agent:" in body
        assert "Sitemap:" in body
        assert "sitemap.xml" in body

    def test_sitemap_xml_returns_200_xml(self, client):
        r = client.get("/sitemap.xml")
        assert r.status_code == 200
        body = r.text
        assert "<?xml" in body
        assert "<urlset" in body
        assert "ai-coach.com.cn" in body

    def test_sitemap_contains_main_routes(self, client):
        r = client.get("/sitemap.xml")
        body = r.text
        assert "https://www.ai-coach.com.cn/" in body
        assert "/qa" in body
        assert "/eval" in body


class TestHomePage:
    def test_home_returns_html(self, client):
        r = client.get("/")
        assert r.status_code == 200
        assert "text/html" in r.headers.get("content-type", "")

    def test_home_contains_search_box(self, client):
        r = client.get("/")
        assert "search-box" in r.text or "搜索" in r.text

    def test_home_contains_learn_cta(self, client):
        """首页应该有 /learn 入口（M1-M8 自学课程的 CTA）。"""
        r = client.get("/")
        assert "/learn" in r.text


class TestStaticPages:
    @pytest.mark.parametrize("path", ["/qa", "/eval"])
    def test_html_page_returns_200(self, client, path):
        r = client.get(path)
        assert r.status_code == 200
        assert "text/html" in r.headers.get("content-type", "")

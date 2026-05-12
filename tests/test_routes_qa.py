"""Integration tests: POST /api/qa (RAG streaming)"""
import json
import pytest

pytestmark = pytest.mark.integration


class TestQARoute:
    def test_qa_missing_question_returns_400(self, client):
        r = client.post("/api/qa", json={})
        assert r.status_code == 400
        assert "error" in r.json()

    def test_qa_empty_question_returns_400(self, client):
        r = client.post("/api/qa", json={"q": ""})
        assert r.status_code == 400

    def test_qa_question_too_long_returns_400(self, client):
        r = client.post("/api/qa", json={"q": "x" * 1500})
        assert r.status_code == 400

    def test_qa_valid_question_streams_response(self, client, mock_chat_stream):
        r = client.post("/api/qa", json={"q": "什么是临在？"})
        assert r.status_code == 200
        # SSE 内容
        body = r.text
        # citations event 一定有
        assert "event: citations" in body
        # mock_chat_stream 默认返回 "你好，世界"
        assert "你好" in body or "data:" in body

    def test_qa_emits_done_event(self, client, mock_chat_stream):
        r = client.post("/api/qa", json={"q": "测试问题"})
        assert "event: done" in r.text

    def test_qa_rate_limit_kicks_in(self, client, mock_chat_stream):
        """连发 ≥6 次 触发 5/min 限速。"""
        responses = []
        for _ in range(7):
            r = client.post("/api/qa", json={"q": "test rate"})
            responses.append(r.status_code)
        # 至少 1 个 429
        assert 429 in responses, f"未触发限速: {responses}"

    def test_qa_response_includes_citations_json(self, client, mock_chat_stream):
        r = client.post("/api/qa", json={"q": "什么是临在"})
        # citations event 后面的 data 行应该是 JSON 数组
        for line in r.text.split("\n"):
            if line.startswith("data: ") and line[6:].startswith("["):
                citations = json.loads(line[6:])
                assert isinstance(citations, list)
                break

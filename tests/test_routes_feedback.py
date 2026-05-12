"""Integration tests: POST /api/feedback (qa 答案点赞/点踩)"""
import pytest

pytestmark = pytest.mark.integration


class TestFeedback:
    def test_feedback_thumbs_up_returns_ok(self, client):
        r = client.post("/api/feedback", json={"q": "test question", "score": 1})
        assert r.status_code == 200
        assert r.json().get("ok") is True

    def test_feedback_thumbs_down_returns_ok(self, client):
        r = client.post("/api/feedback", json={"q": "test question", "score": -1})
        assert r.status_code == 200

    def test_feedback_invalid_score_returns_400(self, client):
        r = client.post("/api/feedback", json={"q": "test", "score": 5})
        assert r.status_code == 400

    def test_feedback_missing_q_returns_400(self, client):
        r = client.post("/api/feedback", json={"score": 1})
        assert r.status_code == 400

    def test_feedback_score_zero_invalid(self, client):
        r = client.post("/api/feedback", json={"q": "x", "score": 0})
        assert r.status_code == 400

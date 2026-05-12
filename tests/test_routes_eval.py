"""Integration tests: POST /api/eval (transcript evaluation)"""
import json
import pytest

pytestmark = pytest.mark.integration


def _valid_eval_result(quote_in_transcript="这是教练对话的一句话"):
    return {
        "scores": {str(i): "ACC" for i in range(1, 9)},
        "highlights": [
            {"competency_id": 6, "quote": quote_in_transcript, "comment": "倾听到位"}
        ],
        "improvements": [
            {
                "competency_id": 7,
                "suggestion": "可以更深一层提问",
                "example_phrasing": "如果你知道答案会是什么？",
            }
        ],
        "overall_level": "ACC",
        "summary": "整体 ACC 级，部分能力可深化。",
    }


class TestEvalRoute:
    def test_eval_missing_consent_returns_403(self, client, mock_chat_complete):
        r = client.post("/api/eval", json={"transcript": "test", "consent": False})
        assert r.status_code == 403

    def test_eval_consent_field_missing_returns_403(self, client, mock_chat_complete):
        r = client.post("/api/eval", json={"transcript": "test"})
        assert r.status_code == 403

    def test_eval_empty_transcript_returns_400(self, client, mock_chat_complete):
        r = client.post("/api/eval", json={"transcript": "", "consent": True})
        assert r.status_code == 400

    def test_eval_invalid_json_returns_400(self, client, mock_chat_complete):
        r = client.post("/api/eval", data="not json{{",
                        headers={"Content-Type": "application/json"})
        assert r.status_code == 400

    def test_eval_valid_request_returns_schema(self, client, mock_chat_complete):
        transcript = "教练：你好。\n客户：我有问题。这是教练对话的一句话\n教练：什么问题？"
        mock_chat_complete["text"] = json.dumps(
            _valid_eval_result(quote_in_transcript="这是教练对话的一句话"),
            ensure_ascii=False,
        )
        r = client.post("/api/eval", json={"transcript": transcript, "consent": True})
        assert r.status_code == 200, r.text
        data = r.json()
        assert set(data["scores"].keys()) == {str(i) for i in range(1, 9)}
        assert isinstance(data["highlights"], list)
        assert isinstance(data["improvements"], list)
        assert data["overall_level"] in {"ACC", "borderline_PCC", "PCC", "MCC"}

    def test_eval_invalid_llm_output_eventually_errors(self, client, mock_chat_complete):
        """LLM 返非 JSON，retry 一次还是错 → 返回 500 + error。"""
        mock_chat_complete["text"] = "这不是 JSON 这是空话"
        r = client.post("/api/eval", json={
            "transcript": "教练：什么？\n客户：测试。",
            "consent": True,
        })
        assert r.status_code in (500,)
        data = r.json()
        assert "error" in data

    def test_eval_rate_limit_blocks_4th_call(self, client, mock_chat_complete):
        """同 IP 每分钟 ≤3 次（routes_eval.py 设定）。"""
        mock_chat_complete["text"] = json.dumps(_valid_eval_result(), ensure_ascii=False)
        transcript = "教练：?\n客户：这是教练对话的一句话\n教练：嗯。"
        codes = []
        for _ in range(5):
            r = client.post("/api/eval", json={"transcript": transcript, "consent": True})
            codes.append(r.status_code)
        # 至少有一次 429
        assert 429 in codes, f"limit 没生效: {codes}"

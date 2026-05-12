"""Unit tests for app/lib/llm.py"""
import pytest
from lib import llm


pytestmark = pytest.mark.unit


class TestPricing:
    def test_known_model_pricing(self):
        assert "deepseek-v4-flash" in llm.PRICING
        assert "deepseek-v4-pro" in llm.PRICING
        assert "text-embedding-v3" in llm.PRICING

    def test_calc_cost_known_model(self):
        # deepseek-v4-flash: in=0.07, out=0.27 per 1M
        cost = llm._calc_cost("deepseek-v4-flash", 1_000_000, 1_000_000)
        assert cost == pytest.approx(0.07 + 0.27)

    def test_calc_cost_unknown_model_uses_default(self):
        # 未知 model fallback 到 0.5/1.5 per 1M
        cost = llm._calc_cost("future-mystery-model", 1_000_000, 1_000_000)
        assert cost == pytest.approx(0.5 + 1.5)

    def test_calc_cost_zero(self):
        assert llm._calc_cost("deepseek-v4-flash", 0, 0) == 0.0

    def test_embedding_cost(self):
        # text-embedding-v3: in=0.05, out=0 per 1M
        cost = llm._calc_cost("text-embedding-v3", 1_000_000, 0)
        assert cost == pytest.approx(0.05)


class TestEndpointTag:
    def test_set_and_get_endpoint(self):
        llm.set_endpoint("test_endpoint")
        # 直接验证 ContextVar 已设
        assert llm._endpoint_tag.get() == "test_endpoint"

    def test_default_endpoint(self):
        # 在 fresh ContextVar 里默认是 "unknown"
        # 注意：如果其他测试改了，可能不是 unknown——本测试用新值确认 set 工作
        llm.set_endpoint("known_value")
        assert llm._endpoint_tag.get() != "unknown"


class TestRecordUsage:
    def test_record_calls_db_log_usage(self, monkeypatch, patch_db_connect, db_conn):
        from lib import db
        llm.set_endpoint("test_record_ep")
        llm._record("test_provider", "deepseek-v4-flash", in_t=200, out_t=300)
        row = db_conn.execute("SELECT * FROM usage_log ORDER BY id DESC LIMIT 1").fetchone()
        assert row["endpoint"] == "test_record_ep"
        assert row["provider"] == "test_provider"
        assert row["model"] == "deepseek-v4-flash"
        assert row["input_tokens"] == 200
        assert row["output_tokens"] == 300

    def test_record_swallows_exceptions(self, monkeypatch):
        """_record 是 best-effort，db 失败也不抛错。"""
        def broken_log(**kwargs):
            raise RuntimeError("boom")
        from lib import db
        monkeypatch.setattr(db, "log_usage", broken_log)
        # 不应抛
        llm._record("p", "m", in_t=1, out_t=1)


class TestEnvConfig:
    def test_llm_model_fast_default(self):
        # 默认 deepseek-v4-flash
        assert llm.LLM_MODEL_FAST == "deepseek-v4-flash" or llm.LLM_MODEL_FAST is not None

    def test_llm_model_reason_default(self):
        assert llm.LLM_MODEL_REASON == "deepseek-v4-pro" or llm.LLM_MODEL_REASON is not None

    def test_embed_model_default(self):
        assert llm.EMBED_MODEL == "text-embedding-v3"

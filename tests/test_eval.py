from __future__ import annotations

import asyncio
import json
import sys
import types
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))
sys.modules.setdefault("sqlite_vec", types.SimpleNamespace(load=lambda conn: None))
sys.modules.setdefault("frontmatter", types.SimpleNamespace())

from lib import eval as eval_mod


class DummyConn:
    pass


def _docs():
    return [
        {
            "id": i,
            "slug": f"competency_{i:02d}",
            "title": f"能力 {i}",
            "content_md": (
                f"# {i}. 能力 {i}\n\n"
                "## 一句话定义\n定义文本。\n\n"
                "## ACC 判定标准（\"做到了\"长什么样）\nACC 证据。\n\n"
                "## PCC 判定标准（比 ACC 更深的地方）\nPCC 深层证据。\n"
            ),
            "meta": json.dumps({"icf_competency": i}, ensure_ascii=False),
        }
        for i in range(1, 9)
    ]


def _result(scores, quote):
    return {
        "scores": {str(i): scores.get(str(i), "ACC") for i in range(1, 9)},
        "highlights": [{"competency_id": 7, "quote": quote, "comment": "原文证据"}],
        "improvements": [
            {
                "competency_id": 1,
                "suggestion": "先处理安全风险并说明教练边界。",
                "example_phrasing": "我想先确认你的安全：你现在有没有伤害自己的计划？",
            }
        ],
        "overall_level": "ACC",
        "summary": "结构完整，仍需更严格处理关键风险与深层觉察。",
    }


def test_suicide_risk_missed_makes_ethics_below_pcc(monkeypatch):
    transcript = "客户：我有时候想从阳台跳下去。\n教练：嗯，我理解你的压力，我们看看时间管理。"
    monkeypatch.setattr(eval_mod.db, "all_docs", lambda conn: _docs())

    async def fake_chat_complete(**kwargs):
        return json.dumps(_result({"1": "ACC"}, "我有时候想从阳台跳下去"), ensure_ascii=False)

    monkeypatch.setattr(eval_mod.llm, "chat_complete", fake_chat_complete)
    result = asyncio.run(eval_mod.evaluate(transcript, DummyConn()))

    assert set(result["scores"]) == {str(i) for i in range(1, 9)}
    assert result["scores"]["1"] in {"ACC", "未观察到"}
    assert result["scores"]["1"] != "PCC"
    assert isinstance(result["highlights"], list)
    assert isinstance(result["improvements"], list)


def test_repeated_effective_awareness_questions_support_competency_7_pcc(monkeypatch):
    transcript = (
        "教练：如果暂时放下分析，你的直觉告诉你什么？\n"
        "教练：当你说这句话时，身体哪里有反应？\n"
        "教练：这个选择背后有什么假设？\n"
        "教练：你注意到这和上次的模式有什么相似吗？\n"
        "教练：这个发现对你意味着什么？"
    )
    monkeypatch.setattr(eval_mod.db, "all_docs", lambda conn: _docs())

    async def fake_chat_complete(**kwargs):
        return json.dumps(_result({"7": "PCC"}, "这个选择背后有什么假设？"), ensure_ascii=False)

    monkeypatch.setattr(eval_mod.llm, "chat_complete", fake_chat_complete)
    result = asyncio.run(eval_mod.evaluate(transcript, DummyConn()))

    assert result["scores"]["7"] == "PCC"
    assert result["highlights"][0]["quote"] in transcript


def test_empty_coaching_loops_can_score_below_acc(monkeypatch):
    transcript = "教练：你能多说说吗？\n客户：不知道。\n教练：你感觉怎么样？\n客户：还行。\n教练：你能多说说吗？"
    monkeypatch.setattr(eval_mod.db, "all_docs", lambda conn: _docs())

    async def fake_chat_complete(**kwargs):
        return json.dumps(
            _result({"1": "未观察到", "3": "未观察到", "7": "未观察到"}, "你能多说说吗？"),
            ensure_ascii=False,
        )

    monkeypatch.setattr(eval_mod.llm, "chat_complete", fake_chat_complete)
    result = asyncio.run(eval_mod.evaluate(transcript, DummyConn()))

    below_acc = [v for v in result["scores"].values() if v == "未观察到"]
    assert len(below_acc) >= 3
    assert isinstance(result["summary"], str)

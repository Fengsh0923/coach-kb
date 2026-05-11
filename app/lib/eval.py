"""ICF transcript evaluation orchestration."""
from __future__ import annotations

import json
import re
from typing import Any

from lib import db, llm
from lib.eval_prompt import build_system_prompt

VALID_SCORES = {"ACC", "PCC", "MCC", "未观察到"}
VALID_OVERALL = {"ACC", "borderline_PCC", "PCC", "MCC"}


def _extract_json(text: str) -> str:
    text = (text or "").strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text).strip()
    if text.startswith("{"):
        return text
    match = re.search(r"\{.*\}", text, flags=re.S)
    if not match:
        raise ValueError("LLM output did not contain a JSON object")
    return match.group(0)


def _validate_result(data: Any, transcript: str) -> dict:
    if not isinstance(data, dict):
        raise ValueError("result must be a JSON object")
    scores = data.get("scores")
    if not isinstance(scores, dict):
        raise ValueError("scores must be an object")
    expected = {str(i) for i in range(1, 9)}
    if set(scores.keys()) != expected:
        raise ValueError("scores must contain keys 1..8")
    bad_scores = {k: v for k, v in scores.items() if v not in VALID_SCORES}
    if bad_scores:
        raise ValueError(f"invalid score values: {bad_scores}")
    if not isinstance(data.get("highlights"), list):
        raise ValueError("highlights must be an array")
    if not isinstance(data.get("improvements"), list):
        raise ValueError("improvements must be an array")
    if data.get("overall_level") not in VALID_OVERALL:
        raise ValueError("overall_level is invalid")
    if not isinstance(data.get("summary"), str):
        raise ValueError("summary must be a string")

    for idx, item in enumerate(data["highlights"]):
        if not isinstance(item, dict):
            raise ValueError(f"highlights[{idx}] must be an object")
        cid = item.get("competency_id")
        if not isinstance(cid, int) or cid < 1 or cid > 8:
            raise ValueError(f"highlights[{idx}].competency_id is invalid")
        quote = item.get("quote")
        if not isinstance(quote, str) or not quote.strip():
            raise ValueError(f"highlights[{idx}].quote is required")
        if quote not in transcript:
            raise ValueError(f"highlights[{idx}].quote is not an exact transcript substring")

    for idx, item in enumerate(data["improvements"]):
        if not isinstance(item, dict):
            raise ValueError(f"improvements[{idx}] must be an object")
        cid = item.get("competency_id")
        if not isinstance(cid, int) or cid < 1 or cid > 8:
            raise ValueError(f"improvements[{idx}].competency_id is invalid")
        if not isinstance(item.get("suggestion"), str) or not item["suggestion"].strip():
            raise ValueError(f"improvements[{idx}].suggestion is required")
        if not isinstance(item.get("example_phrasing"), str) or not item["example_phrasing"].strip():
            raise ValueError(f"improvements[{idx}].example_phrasing is required")

    return data


def _parse_and_validate(raw: str, transcript: str) -> dict:
    return _validate_result(json.loads(_extract_json(raw)), transcript)


def _competency_docs(docs: list[dict]) -> list[dict]:
    selected = [d for d in docs if "competency_" in (d.get("slug") or "")]
    return selected[:8] if len(selected) >= 8 else docs[:8]


async def evaluate(transcript: str, conn) -> dict:
    transcript = (transcript or "").strip()
    if not transcript:
        return {"error": "transcript is required"}

    competencies = _competency_docs(db.all_docs(conn))
    if len(competencies) < 8:
        return {"error": "expected 8 competency rubric docs", "found": len(competencies)}

    system = build_system_prompt(competencies)
    raw = ""
    try:
        raw = await llm.chat_complete(system=system, user=transcript, max_tokens=4096)
        return _parse_and_validate(raw, transcript)
    except Exception as first_error:
        repair_system = (
            system
            + "\n\n你上一次输出无法通过 JSON/schema/引用校验。"
            "请只返回修正后的严格 JSON；highlights.quote 必须逐字来自原对话连续片段。"
        )
        repair_user = (
            f"原始对话：\n{transcript}\n\n"
            f"上一次错误：{first_error}\n\n"
            f"上一次输出：\n{raw}"
        )
        repaired = ""
        try:
            repaired = await llm.chat_complete(system=repair_system, user=repair_user, max_tokens=4096)
            return _parse_and_validate(repaired, transcript)
        except Exception as second_error:
            return {
                "error": f"eval JSON/schema validation failed: {second_error}",
                "raw": repaired or raw,
            }

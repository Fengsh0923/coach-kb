"""Prompt builder for ICF transcript evaluation."""
from __future__ import annotations

import json
import re


def _competency_id(item: dict) -> int:
    meta = item.get("meta") or {}
    if isinstance(meta, str):
        try:
            meta = json.loads(meta)
        except Exception:
            meta = {}
    raw = meta.get("icf_competency") or item.get("icf_competency")
    if raw is None:
        match = re.search(r"competency_(\d+)", item.get("slug", ""))
        raw = match.group(1) if match else item.get("id", 0)
    try:
        return int(raw)
    except Exception:
        return 0


def _section(md: str, heading: str) -> str:
    pattern = rf"##\s+{re.escape(heading)}.*?\n(?P<body>.*?)(?=\n##\s+|\Z)"
    match = re.search(pattern, md, flags=re.S)
    if not match:
        return ""
    return re.sub(r"\s+", " ", match.group("body")).strip()


def _clip(text: str, limit: int = 200) -> str:
    text = re.sub(r"\s+", " ", text).strip()
    return text if len(text) <= limit else text[:limit].rstrip() + "..."


def build_system_prompt(competencies: list[dict]) -> str:
    """Build a compact, evidence-first system prompt from ICF competency docs."""
    rubric_lines: list[str] = []
    for item in sorted(competencies, key=_competency_id):
        cid = _competency_id(item)
        if cid < 1 or cid > 8:
            continue
        title = item.get("title") or item.get("slug") or f"能力 {cid}"
        content = item.get("content_md", "")
        definition = _clip(_section(content, "一句话定义"), 120)
        acc = _clip(_section(content, 'ACC 判定标准（"做到了"长什么样）'), 200)
        pcc = _clip(_section(content, "PCC 判定标准（比 ACC 更深的地方）"), 200)
        rubric_lines.append(
            f"### {cid}. {title}\n"
            f"定义：{definition}\n"
            f"ACC 关键证据：{acc}\n"
            f"PCC 关键证据：{pcc}\n"
            "MCC：只有出现持续、深层、客户主导、能显著转化客户觉察/选择的行为证据时才可给出；否则不要给 MCC。"
        )

    rubric = "\n\n".join(rubric_lines)
    schema = {
        "scores": {"1": "PCC", "2": "ACC", "3": "PCC", "4": "ACC", "5": "PCC", "6": "ACC", "7": "PCC", "8": "ACC"},
        "highlights": [{"competency_id": 4, "quote": "<原对话片段>", "comment": "<评注>"}],
        "improvements": [{"competency_id": 7, "suggestion": "<具体建议>", "example_phrasing": "<示范句式>"}],
        "overall_level": "ACC | borderline_PCC | PCC | MCC",
        "summary": "<200字内总评>",
    }
    return (
        "你是 ICF 教练认证评估员，任务是评估一段中文教练对话转录。"
        "你必须严格依据下方 8 项核心能力 rubric，按可观察行为证据打分。\n\n"
        "## 评分铁律\n"
        "1. 只根据用户给出的对话文本评分，不得脑补背景、意图或未出现的行为。\n"
        "2. 每一项必须找到对应 ACC/PCC/MCC 行为证据才给该档；没有清晰证据给「未观察到」。\n"
        "3. PCC 不能只因为教练用了开放式问题就给出，必须有更深层的行为证据。\n"
        "4. 客户出现自杀、自伤、严重心理危机、违法伤害风险时，教练若未直接确认安全、说明边界并建议专业支持，"
        "第 1 项「展现伦理实践」必须低于 PCC，只能给 ACC 或「未观察到」。\n"
        "5. highlights 的 quote 必须逐字复制原对话中的连续片段，不得改写、概括或编造。\n"
        "6. improvements 必须具体到下一次对话可直接使用的做法和示范句式。\n"
        "7. summary 不超过 200 个中文字符。\n"
        "8. 只能输出严格 JSON，不能输出 markdown、代码围栏、解释文字或尾注。\n\n"
        "## 输出 JSON Schema 示例\n"
        f"{json.dumps(schema, ensure_ascii=False, indent=2)}\n\n"
        "字段约束：scores 必须包含字符串 key \"1\" 到 \"8\"；score value 只能是 "
        "\"ACC\"、\"PCC\"、\"MCC\"、\"未观察到\"。overall_level 只能是 "
        "\"ACC\"、\"borderline_PCC\"、\"PCC\"、\"MCC\"。\n\n"
        "## Rubric 摘要\n"
        f"{rubric}"
    )

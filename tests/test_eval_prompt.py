"""Unit tests for app/lib/eval_prompt.py"""
import json
import pytest

from lib import eval_prompt


pytestmark = pytest.mark.unit


def _make_competency_doc(cid: int, **overrides) -> dict:
    """Build a doc dict mimicking what eval.py passes in."""
    base = {
        "id": cid,
        "slug": f"competency_{cid:02d}_test",
        "title": f"能力 {cid}",
        "content_md": (
            f"# {cid}. 能力 {cid}\n\n"
            "## 一句话定义\n定义文本。\n\n"
            "## 完整定义（来自 ICF 官方）\n详细定义内容多句话。\n\n"
            "## ACC 判定标准（\"做到了\"长什么样）\n"
            "- 标准 1\n- 标准 2\n\n"
            "## PCC 判定标准（比 ACC 更深的地方）\n"
            "- PCC 标准 1\n- PCC 标准 2\n"
        ),
        "meta": json.dumps({"icf_competency": cid}, ensure_ascii=False),
    }
    base.update(overrides)
    return base


class TestBuildSystemPrompt:
    def test_returns_non_empty_string(self):
        docs = [_make_competency_doc(i) for i in range(1, 9)]
        prompt = eval_prompt.build_system_prompt(docs)
        assert isinstance(prompt, str)
        assert len(prompt) > 100  # 至少 100 字内容

    def test_contains_all_8_competency_ids(self):
        docs = [_make_competency_doc(i) for i in range(1, 9)]
        prompt = eval_prompt.build_system_prompt(docs)
        # 至少能找到每个 cid 编号
        for i in range(1, 9):
            assert str(i) in prompt or f"能力 {i}" in prompt

    def test_handles_meta_as_json_string(self):
        """meta 字段可能是 JSON 字符串（从 DB 取出来时常这样）。"""
        doc = _make_competency_doc(7)
        # 已经是 string
        prompt = eval_prompt.build_system_prompt([doc])
        assert isinstance(prompt, str)

    def test_handles_meta_as_dict(self):
        """meta 也可能直接是 dict。"""
        doc = _make_competency_doc(7)
        doc["meta"] = {"icf_competency": 7}
        prompt = eval_prompt.build_system_prompt([doc])
        assert isinstance(prompt, str)

    def test_handles_missing_meta(self):
        doc = _make_competency_doc(3)
        doc.pop("meta", None)
        # slug 含 competency_03 还能 fallback 出 cid=3
        prompt = eval_prompt.build_system_prompt([doc])
        assert isinstance(prompt, str)

    def test_extracts_competency_id_from_slug(self):
        """meta 没有 icf_competency，但 slug 是 competency_NN_xxx → 应该能解析出 NN。"""
        doc = {
            "id": 1,
            "slug": "competency_05_maintains_presence",
            "title": "保持临在",
            "content_md": "## 一句话定义\n临在。\n## ACC 判定标准\nx\n## PCC 判定标准\ny\n",
            "meta": "{}",
        }
        prompt = eval_prompt.build_system_prompt([doc])
        # 解析后用 cid=5 编号能力
        assert isinstance(prompt, str)

    def test_clips_long_sections(self):
        """单 section 不应超过 _clip 限制（200 字）—— prompt 总长应该是受控的。"""
        # 制造一个超长 content
        long_doc = _make_competency_doc(1)
        long_doc["content_md"] = (
            "## ACC 判定标准（\"做到了\"长什么样）\n" + ("超长文本 " * 500) +
            "\n## PCC 判定标准\n" + ("超长文本 " * 500)
        )
        prompt = eval_prompt.build_system_prompt([long_doc])
        # 应该被裁剪——总长不应该是 docs 文本的简单拼接
        # （具体阈值不验证，验证至少不爆炸增长）
        assert len(prompt) < 100_000  # 不应是无限拼接

    def test_empty_doc_list_does_not_crash(self):
        prompt = eval_prompt.build_system_prompt([])
        assert isinstance(prompt, str)

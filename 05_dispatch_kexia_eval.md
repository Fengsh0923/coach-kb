# 派单：克虾 · /api/eval 对话回放评估模块

> **派单人**：鳌虾 / 工头
> **执行人**：克虾（甜虾上 Codex CLI 0.130，ChatGPT Plus → GPT-5）
> **派单时间**：2026-05-11 08:15
> **目标交付**：今天中午前

---

## 任务目标

为 Coach KB v1 写**对话回放评估**模块——用户上传一段教练对话转录文本，系统按 ICF 8 项核心能力打分（ACC/PCC/MCC 三档），给出关键时刻引用 + 具体改进建议。这是 v1 的杀手 feature。

## 你要做什么（4 个文件）

在 git 仓库 `~/coach-kb/`（甜虾上已 clone）的 `app/` 目录里写下面 4 个文件——**不要动其他文件**（main.py / lib/db.py / lib/llm.py 已由鳌虾写，你只增不改）：

### 1. `app/lib/eval_prompt.py`
- 一个函数 `build_system_prompt(competencies: list[dict]) -> str`，把 8 项 ICF 能力的中文 rubric（从 DB doc 表读出来后传入）拼成一个 system prompt
- prompt 要求 LLM 输出**严格 JSON**：
  ```json
  {
    "scores": {"1": "PCC", "2": "ACC", "3": "PCC", ..., "8": "ACC"},
    "highlights": [{"competency_id": 4, "quote": "<原对话片段>", "comment": "<评注>"}],
    "improvements": [{"competency_id": 7, "suggestion": "<具体建议>", "example_phrasing": "<示范句式>"}],
    "overall_level": "ACC | borderline_PCC | PCC | MCC",
    "summary": "<200字内总评>"
  }
  ```
- 每档判定要**严格按 rubric**：你能找到对应能力 ACC/PCC 判定标准里的具体行为证据才给那一档；没证据给"未观察到"
- 你要做的是设计 prompt——选哪些 rubric 片段进 prompt（不要全塞，每项截最关键 200 字）+ 怎么引导 LLM 严格遵守 ICF 标准

### 2. `app/lib/eval.py`
- 一个 `async def evaluate(transcript: str, conn) -> dict` 函数
- 流程：① 从 DB 读 8 篇 doc 的 content_md ② 调 `eval_prompt.build_system_prompt` ③ 调 `llm.chat_complete` 拿 JSON 字符串 ④ 解析 + 校验 schema ⑤ 返回 dict
- 失败兜底：如果 JSON 解析失败，**重试一次**（让 LLM 修），还是不行返 `{"error": "...", "raw": ...}`
- 校验项：scores 必须有 8 项 key="1..8" + value 必须在 {ACC, PCC, MCC, 未观察到}；highlights/improvements 必须是数组

### 3. `app/routes_eval.py`
- 一个 FastAPI APIRouter，挂 `/api/eval` POST 端点
- 输入：`{"transcript": "<文本>", "consent": true}`
- 输出：上面的 result_json
- 隐私处理：consent 不为 true 直接拒；transcript 入 `eval_session` 表前**先 hash IP+UA 作匿名 session_id**，不存原始 IP
- 限速：单 IP 每分钟 3 次，超过返 429
- 在 main.py 里 `app.include_router(routes_eval.router)` —— 这一行加在文件末尾就行，**不重写 main.py**

### 4. `tests/test_eval.py`
- 至少 3 个 case：
  - case 1：客户提自杀风险，教练没处理 → 第 1 项（伦理）应该 < PCC
  - case 2：教练在 30 分钟内做了 5 次有效"唤起觉察"提问 → 第 7 项应该 PCC
  - case 3：纯空话教练（"你能多说说吗""你感觉怎么样"循环）→ 多项 ACC 都达不到
- 测 schema 完整性 + 直觉判断对错（不必百分百，但 case 1 第 1 项必须低分）

## 技术约束

- **不要 pip install 新依赖**（除非真要）。鳌虾装了：fastapi / uvicorn / jinja2 / markdown / python-frontmatter / httpx / sqlite-vec
- LLM 走 `lib.llm.chat_complete(system=..., user=transcript, max_tokens=4096)`，model 用默认 GLM-4.6（已配 GLM_INTL_API_KEY 环境变量）
- DB 走 `lib.db.connect()`（已配 /data/coach.db），用 `lib.db.all_docs()` 读 8 篇能力 rubric

## 你**不要**做的事

- 不动 main.py 的 `/` `/wiki/{slug}` `/api/search` `/api/qa` 路由
- 不改 docker-compose.yml / Caddyfile / Dockerfile
- 不动 templates 目录（前端鳌虾接）
- 不接入新的 LLM provider（用现有 GLM）

## 成功标准（鳌虾验收）

| # | 标准 | 失败判定 |
|---|---|---|
| 1 | 4 个文件全交付 | 缺一不通过 |
| 2 | 端到端：POST /api/eval 返合规 JSON（schema 校验通过） | 返非 JSON 或 schema 错 = 重做 |
| 3 | 测试 case 1（自杀风险未处理）第 1 项打分必须低于 PCC | 给 PCC 以上 = prompt 不严格 = 重做 |
| 4 | citations 准确引用原对话原文（不是编造） | 编造 = 重做，prompt 加约束 |
| 5 | 单 IP 限速 + 匿名化 session_id 实现 | 漏 = 补上 |
| 6 | 跑过 pytest（不必 100% 但 schema 校验必须过） | 跑不过 = 修 |

## 交付方式

1. 在 `~/coach-kb/` 工作目录里写完代码 + 测试
2. `git add -A && git commit -m "克虾：/api/eval 模块实现"`
3. `git push origin main`
4. 给鳌虾飞书发：`done + commit sha + 自评分(1-10)`

鳌虾收到后会 pull → docker compose build → 重启 → 端到端测 → 验收。

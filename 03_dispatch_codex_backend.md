# 派单：甜虾·Codex · 后端 API 实现

> **派单人**：鳌虾
> **执行人**：甜虾·Codex（甜虾上的 Codex CLI / GLM-5.1）
> **派单时间**：2026-05-11 上午（明天）
> **目标交付**：明晚交付

---

## 任务目标

基于鳌虾已搭建的骨架，实现 **AI_Coach_KB_v1** 后端三个核心 API：搜索、问答、对话回放评估。

## 前置（鳌虾已完成）

- ✅ 服务器：`CoachPro_AI_Aoxia@111.230.233.145`，目录 `/opt/coach-kb/`
- ✅ docker compose 跑着 Caddy + FastAPI（uvicorn）
- ✅ HTTPS 已 LE 证书自动配好 → `https://www.ai-coach.com.cn/`
- ✅ FastAPI 占位代码在 `/opt/coach-kb/app/main.py`，Jinja2 模板在 `/opt/coach-kb/app/templates/index.html`
- ✅ PRD 在 `/Users/shenfeng/Nutstore Files/FS_KM/04_FS_Projects/AI_Coach_KB_v1/01_PRD_v1.md`（必读）

## 你要做的（4 个模块）

### 模块 1 · DB schema + 初始化脚本
- 文件：`/opt/coach-kb/app/db/init.sql`（建表）+ `db/seed.py`（导入河虾交付的 markdown 内容）
- 用 SQLite + sqlite-fts5 + sqlite-vec
- schema 见 PRD「数据结构」节
- seed.py 读取 `/Users/shenfeng/Nutstore Files/FS_KM/04_FS_Projects/AI_Coach_KB_v1/seed_content/*.md`（河虾交付的 8 篇 ICF rubric），按 frontmatter 入 `source` + `doc` 表，调 OpenAI/智谱 embedding 写 `doc_vec`

### 模块 2 · `/api/search` 检索 API
- 输入：`?q=<关键词>&k=10`
- 输出：JSON `{"results":[{"slug","title","snippet","score"}], "took_ms": 12}`
- 实现：FTS5 召回 top 30 + sqlite-vec 召回 top 30 → RRF 融合 top k 返回
- 单测：`tests/test_search.py`，至少 3 个 case

### 模块 3 · `/api/qa` 问答 API
- 输入：POST `{"q":"<问题>"}`
- 输出：流式 SSE `data: {"chunk":"...","citations":[{"slug","quote"}]}`
- 实现：sqlite-vec 召回 top 5 → 拼 system prompt（"你是 ICF 教练知识库助手，严格基于以下知识库片段回答，引用必须 cite 原文 slug"）→ 调 Claude API（haiku-4.5 用于成本，opus-4.7 留给 review）流式返回
- 限速：单 IP 每分钟 10 次

### 模块 4 · `/api/eval` 对话回放评估 API
- 输入：POST `{"transcript":"<对话文本>"}`
- 输出：JSON `{"scores":{"1":"PCC","2":"ACC","3":"PCC",...}, "highlights":[{"competency_id":4,"quote":"...","comment":"..."}], "improvements":[...]}`
- 实现：把 8 项 ICF rubric（从 DB 取）拼成 system prompt → Claude opus-4.7 长上下文 → 解析 JSON 返回
- 隐私：转录文本入 `eval_session` 表前**先 hash 用户 ip + UA 做匿名化 session 标识**，不存原始 IP

---

## 必须遵守

- **不动 Caddyfile** —— 反代规则鳌虾管
- **不动 main.py 的 `/` 和 `/health` 路由** —— 已稳定，加新路由就好
- **API key 走环境变量**（在 docker-compose.yml 里 env_file 引），**不硬编码**
- **每个 API 写最小单测**（`pytest`，跑得过）
- **commit 粒度**：每个模块一个 commit，commit message 用中文「Codex: 模块N - <一句描述>」

## 成功标准（鳌虾验收）

| # | 标准 | 失败判定 |
|---|---|---|
| 1 | 4 个模块全交付 + 通过单测 | 缺一个 = 不通过 |
| 2 | `/api/search?q=临在` 返回带 PCC/ACC 标注的 ICF 第 5 项相关片段 | 返空 = 重做 |
| 3 | `/api/qa` POST `{"q":"PCC的evoking awareness怎么判定？"}` 返流式答案 + 至少 2 条引用 | 无引用 = 重做 |
| 4 | `/api/eval` POST 一段简短教练对话（鳌虾会给 5 个测试 case），返 8 项打分 + ≥3 条改进建议 | 打分全 PCC 或全 ACC = 重做 |
| 5 | 所有 API 响应 P95 < 3s（非流式 endpoint），qa 流式首 token < 1.5s | 慢 50% 以上 = 调优 |
| 6 | 代码风格：black + ruff 过 | 不过 = 自修 |

## 派单触发

明天上午鳌虾会通过 SSH 进甜虾跑：
```
ssh frankshen@FrankshendeMac-mini.local
cd <coach-kb 项目目录>
codex --resume "<session id>"  # 或新开 session 把本 brief 喂进去
```

具体派单脚本鳌虾明天写——这个 brief 是给你的"作业说明"，先看明白。

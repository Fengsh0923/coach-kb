# Coach KB v1 · PRD

> **状态**：草稿（鳌虾 2026-05-10 22:55 起手）
> **目标用户**：准备 ICF ACC / PCC 认证的中文教练学习者
> **不是什么**：F哥个人数字分身（那是 AI_Coach v2，独立 repo）

---

## 一句话定义

一个面向 ACC/PCC 备考与日常实践的**中文教练知识库**，提供搜索、问答、对话回放评估三件事——别人也能用，长期开源。

---

## 三个核心场景（v1 全做）

### 场景 1 · 知识检索（搜索 + 浏览）
**用户故事**：我学到 "ICF 第 4 项核心能力 Cultivates Trust and Safety"，想看看 ACC 和 PCC 级的判定差异、相关案例、推荐阅读。
- 输入：关键词 / 11 项能力名 / 流派名
- 输出：结构化 wiki 页（rubric 表 + 注解 + 示例 + 引用源）
- 技术：sqlite-fts5 全文 + sqlite-vec 语义双路召回

### 场景 2 · 教练问答（RAG）
**用户故事**：我想问"PCC 考核中 evoking awareness 怎么判定，跟 ACC 区别在哪？"
- 输入：自然语言问题
- 输出：基于知识库的回答 + 引用源链接（可点回 wiki）
- 技术：sqlite-vec 召回 → Claude/GLM API 生成 → 流式输出

### 场景 3 · 对话回放评估（v1 杀手 feature）
**用户故事**：我刚做完一次 30 分钟教练对话，把转录贴进来，请按 ICF 11 项打分 + 给改进建议。
- 输入：对话文本（最长 ~10K 字）
- 输出：11 项各项得分（0/PCC/MCC 三档）+ 关键时刻引用 + 具体改进句式建议
- 技术：Claude/GLM 长上下文 + ICF rubric 系统提示词
- ⚠️ 隐私红线：录音不落服务器（前端自调 ASR API），文本入库前用户确认

---

## 内容来源（v1 边界）

| 类别 | 收 | 不收 |
|---|---|---|
| ICF 官方材料 | ✅ 摘要 + 链接 | ❌ 全文转载 |
| 经典教练书（GROW/CTI/欧文亚隆 etc） | ✅ F哥读书笔记 | ❌ 原书全文 |
| 公开课程笔记 | ✅ 原作者授权或纯笔记 | ❌ 课程录像/PPT |
| ACC/PCC 真题 | ❌ v1 不收 | （v2 评估） |

**核心理念**：知识库内容 = `F哥独家笔记 + 公开材料指引`，**不做盗版搬运**。

---

## 技术栈（拍板）

| 层 | 选型 | 为什么 |
|---|---|---|
| 反代 + HTTPS | Caddy 2 | 自动 LE 证书，零运维 |
| 后端 | FastAPI + Python 3.12 | 鳌虾/Codex 都熟，生态足 |
| 数据库 | SQLite + sqlite-fts5 + sqlite-vec | 单文件，2C4G 完全跑得动，备份就一个文件 |
| 向量 | sqlite-vec（不用 Qdrant） | AI_Coach v2 用 Qdrant 是企微 Bot 时的选择，知识库这种规模 sqlite-vec 更轻 |
| LLM | Claude API（主）+ GLM API（中文 review） | 已有 key |
| Embedding | OpenAI text-embedding-3-small / 智谱 embedding-3 | 中文兼顾 |
| 前端 | 极简 SSR（Jinja2 + Alpine.js）→ v2 再上 React | 开局快，SEO 友好（教练学习者会 Google 搜） |
| 部署 | docker compose（Caddy + FastAPI 同 stack） | 一键 up/down |

**反对的选型**：
- ❌ 不上 Qdrant（杀鸡用牛刀）
- ❌ 不上 Next.js（v1 还不需要）
- ❌ 不上 PostgreSQL（SQLite 够）
- ❌ 不上 Redis（FastAPI in-memory cache 够）

---

## 数据结构（v1）

```sql
CREATE TABLE source (         -- 内容来源（书/文章/课程）
  id INTEGER PRIMARY KEY,
  type TEXT,                  -- icf_official | book | article | note
  title TEXT NOT NULL,
  author TEXT,
  url TEXT,
  license TEXT,               -- public | personal_note | cc_by
  added_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE doc (            -- 知识库文档（一条 wiki 页）
  id INTEGER PRIMARY KEY,
  source_id INTEGER REFERENCES source(id),
  slug TEXT UNIQUE NOT NULL,  -- url 友好
  title TEXT NOT NULL,
  category TEXT,              -- competency | school | technique | case | glossary
  content_md TEXT NOT NULL,
  meta JSON,                  -- {icf_competency: 4, level: ['ACC','PCC'], tags: [...]}
  updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE VIRTUAL TABLE doc_fts USING fts5(   -- 全文检索
  title, content_md, content='doc', content_rowid='id', tokenize='trigram'
);

CREATE VIRTUAL TABLE doc_vec USING vec0(   -- 语义检索
  doc_id INTEGER PRIMARY KEY,
  embedding FLOAT[1536]
);

CREATE TABLE qa_log (         -- 问答日志（用于改进）
  id INTEGER PRIMARY KEY,
  question TEXT,
  answer_md TEXT,
  citations JSON,
  user_session TEXT,
  ts DATETIME DEFAULT CURRENT_TIMESTAMP,
  feedback_score INTEGER      -- 用户点赞/踩
);

CREATE TABLE eval_session (   -- 对话回放评估日志
  id INTEGER PRIMARY KEY,
  transcript TEXT,
  result_json JSON,
  ts DATETIME DEFAULT CURRENT_TIMESTAMP
);
```

---

## v1 范围（要做 / 不要做）

**v1 做**：
- ✅ 后端 API：`/api/search /api/qa /api/eval`
- ✅ 前端：首页 + wiki 浏览页 + 搜索结果页 + 问答页 + 对话回放页
- ✅ 内容种子：ICF 8 项核心能力中文 rubric（河虾今晚做） + F哥已有读书笔记 ~5 篇
- ✅ HTTPS 上线 `www.ai-coach.com.cn`
- ✅ 中文友好 SEO（meta + sitemap + robots）

**v1 不做**：
- ❌ 用户登录/账号
- ❌ 评论/社区
- ❌ 飞书 Bot 接入（v2）
- ❌ 移动端 App
- ❌ 付费/会员
- ❌ ASR 音频转文字（前端调 API，不入库）

---

## 4 虾今晚 / 明天分工

### 今晚（凌晨前）
| 虾 | 任务 | 产出验真 |
|---|---|---|
| **鳌虾**（本机） | ① 服务器骨架（Caddy+FastAPI hello）② PRD（本文档）③ 前端骨架 ④ DB schema 落 v1.sql ⑤ 派单 brief 写完 | `https://www.ai-coach.com.cn/health` 返 ok + 文件全在 04_FS_Projects/AI_Coach_KB_v1/ |
| **河虾**（OpenCode :4096） | ICF 8 项核心能力中文 rubric 整理（每项 ACC/PCC 判定差异 + 示例 + 反例） | 8 个 markdown 文件，每个 ≥ 800 字，覆盖能力定义/ACC 判定/PCC 判定/常见误区/案例 |

### 明天白天
| 虾 | 任务 |
|---|---|
| **甜虾·Codex** | 后端 API 实现（基于鳌虾骨架 + DB schema） |
| **甜虾·Kimi** | 前端实现（基于鳌虾 HTML 占位 + Alpine.js 增强） |
| **鳌虾** | 工头：把河虾的 rumric 内容入库 → 跑通三场景端到端 → 接 LLM API |

### 后天
| 任务 |
|---|
| QA 测试 + 内容补充 |
| Open beta 邀请 5 位教练学习者用 + 反馈 |

---

## 风险与红线

1. **版权红线**：不爬 ICF 全文、不放经典书原文，只做摘要+链接+F哥读书笔记
2. **备案红线**：`ai-coach.com.cn` 备案状态 F哥早上确认，过期则配置回滚到 IP 直连方案
3. **隐私红线**：教练对话评估的录音不落服务器，文字入库前用户明确同意
4. **API 成本**：v1 限速 10 qps + 单 IP 每日 100 次，避免被恶意 abuse 烧 Claude/GLM 钱
5. **配额监控**：日报跑费用，超阈值告警

---

*生成：鳌虾 2026-05-10 23:00*

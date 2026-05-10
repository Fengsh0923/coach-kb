# Coach KB v1

中文教练学习者知识库 · 面向 ICF ACC/PCC 备考与日常实践

**线上**：https://www.ai-coach.com.cn/

## 目录

- `01_PRD_v1.md` — 产品需求文档（核心）
- `02_dispatch_hexia_icf_rubric.md` — 河虾派单：ICF 8项核心能力中文 rubric
- `03_dispatch_codex_backend.md` — 甜虾·Codex 派单：后端 API 实现
- `04_dispatch_kimi_frontend.md` — 甜虾·Kimi 派单：前端实现
- `seed_content/` — 种子内容（河虾交付）
- `server_mirror/` — 服务器 `/opt/coach-kb/` 的镜像副本

## 服务器

- 主机：`CoachPro_AI_Aoxia@111.230.233.145`（腾讯轻量云 2C4G）
- 部署：`/opt/coach-kb/` docker compose（Caddy + FastAPI）
- 域名：www.ai-coach.com.cn（Let's Encrypt 自动证书）

## 协作模式

- **鳌虾**（Claude Opus 4.7）：工头 + 架构 + 终审
- **河虾**（GLM 5.1）：中文内容主笔 + 合规 review
- **甜虾·Codex**（GLM 5.1）：后端 API
- **甜虾·Kimi**（K2.6）：前端实现


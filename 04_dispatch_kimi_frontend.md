# 派单：甜虾·Kimi · 前端实现

> **派单人**：鳌虾
> **执行人**：甜虾·Kimi（Kimi CLI K2.6）
> **派单时间**：2026-05-11 上午（明天）
> **目标交付**：明晚交付

---

## 任务目标

把鳌虾的 HTML 占位升级成可用的 v1 前端：搜索页、wiki 页、问答页、对话回放页 4 个核心页面。

## 前置（鳌虾已完成）

- ✅ HTML 占位骨架在 `/opt/coach-kb/app/templates/index.html`（保留风格作为基线）
- ✅ Jinja2 模板系统已配，FastAPI 路由在 `app/main.py`
- ✅ 视觉风格基线：极简、米白底（#fafaf7）、橙色强调（#c2410c）、PingFang/思源中文字体、卡片圆角 8px、栅格 880px
- ✅ PRD 在 `01_PRD_v1.md`

## 你要做的（4 个页面）

### 页面 1 · `/` 首页（已有占位，你升级）
- 保留视觉风格
- 搜索框接 `/api/search`，输入即时显示 dropdown 候选（debounce 300ms）
- 8 项核心能力卡片做 hover 微动效，点击跳 `/wiki/competency_{N}`
- 三个功能卡片（搜索/问答/回放）改成可点击跳路由

### 页面 2 · `/wiki/{slug}` 内容页
- 渲染 markdown（用 `marked` JS 库 client-side render，或后端 markdown-it）
- 左侧 sticky TOC（目录抓 h2/h3）
- 右侧主内容
- 顶部面包屑：首页 > 核心能力 > 第 N 项
- 底部"相关阅读"3 个卡片（基于 meta.tags 同标签召回）

### 页面 3 · `/qa` 问答页
- 中间一个大输入框（multiline，输入框最小 200px 高）
- 提交按 Cmd+Enter 或点按钮
- 流式接收 `/api/qa` 的 SSE，逐字渲染答案
- 引用源做 footnote 风格悬浮卡片（hover 显示 quote）
- 历史问答存 localStorage，左侧抽屉可切换

### 页面 4 · `/eval` 对话回放评估页
- 大 textarea 粘对话（提示"格式：教练: ... \n客户: ..."）
- 提交后调 `/api/eval`
- 结果展示：
  - 顶部 8 项能力雷达图（用 Chart.js）+ ACC/PCC/MCC 三档可视
  - 下方 8 个能力卡片，每个展示该项打分 + 高亮原对话引用 + 改进建议
- 隐私提示横幅：转录文本会存匿名 session（不含 IP），用户勾选同意才提交

---

## 技术约束

- **不上 React/Vue**：用原生 HTML + Alpine.js（已计划） + minimal vanilla JS
- **不引入 npm 依赖**：CDN 引 Alpine.js、marked.js、Chart.js（自己写 import map）
- **响应式**：手机端必须可用（断点 700px）
- **单文件 CSS**：所有样式在 `static/style.css`，不写 inline
- **暗色模式**：`prefers-color-scheme: dark` 自动切，色卡 `--bg-dark: #1a1a18`，`--text-dark: #e5e5e0`，强调色保持橙

## 视觉风格基线（继承首页）

```css
:root {
  --bg: #fafaf7;
  --text: #1a1a1a;
  --accent: #c2410c;        /* 橙色强调 */
  --border: #e5e5e0;
  --card-bg: #ffffff;
  --muted: #666;
}
font-family: -apple-system, "PingFang SC", "Microsoft YaHei", sans-serif;
line-height: 1.7;
```

## 成功标准（鳌虾验收）

| # | 标准 | 失败判定 |
|---|---|---|
| 1 | 4 个页面全部上线，路由可达 | 缺一个 = 不通过 |
| 2 | 首页搜索框可联动后端 API（即使 stub 数据），无 console 报错 | 报错 = 修 |
| 3 | wiki 页能渲染河虾交付的 8 篇 ICF rubric markdown，TOC 跟随 | 不渲染 = 重做 |
| 4 | 问答页流式渲染，引用 footnote hover 可见 | 非流式 = 改用 EventSource |
| 5 | 评估页雷达图 8 个维度可视，ACC/PCC 区分明显 | 区分不明显 = 改色彩 |
| 6 | 移动端（iPhone safari 测）布局不破，字号可读 | 破版 = 修 |
| 7 | 暗色模式切换无白闪 | 白闪 = 修 |
| 8 | Lighthouse 性能分 ≥ 90 | < 90 = 优化 |

## 视觉参考（一句话审美）

像 Stripe Press 的内容站 + Substack 的极简感，**反对**：花哨渐变、卡片阴影过重、emoji 滥用、动效喧宾夺主。**追求**：让人愿意阅读 30 分钟。

---

## 派单触发

明天上午鳌虾会通过 SSH 进甜虾跑 Kimi CLI 把这个 brief 喂进去。具体派单流程鳌虾明天补全（K2.6 远程调用方式还没自动化）。

# 派单：河虾 · ICF 8 项核心能力中文 rubric 整理

> **派单人**：鳌虾
> **执行人**：河虾（OpenCode :4096，GLM 5.1 / 中文合规主笔）
> **派单时间**：2026-05-10 23:05
> **目标交付**：明天 09:00 前

---

## 任务目标

为 **AI_Coach_KB_v1**（ACC/PCC 中文教练学习者知识库）整理 **ICF 8 项核心能力**（Updated 2019/2020 Core Competency Model）的中文 rubric——每项一个 markdown 文件，覆盖能力定义、ACC 判定、PCC 判定、常见误区、典型案例。

## 8 项核心能力清单

依据 ICF 2019 更新的 Core Competency Model，分 4 大类共 8 项：

**A. Foundation**
1. Demonstrates Ethical Practice（展现伦理实践）
2. Embodies a Coaching Mindset（具备教练心态）

**B. Co-Creating the Relationship**
3. Establishes and Maintains Agreements（建立与维护契约）
4. Cultivates Trust and Safety（培育信任与安全）
5. Maintains Presence（保持临在）

**C. Communicating Effectively**
6. Listens Actively（主动倾听）
7. Evokes Awareness（唤起觉察）

**D. Cultivating Learning and Growth**
8. Facilitates Client Growth（促进客户成长）

---

## 输出格式（每项一个文件，共 8 个）

文件名：`competency_{编号}_{英文名snake_case}.md`，例：
- `competency_01_demonstrates_ethical_practice.md`
- `competency_07_evokes_awareness.md`

每个文件结构（**严格遵守**）：

```markdown
---
icf_competency: 7
en_name: Evokes Awareness
zh_name: 唤起觉察
category: Communicating Effectively
levels: [ACC, PCC]
---

# 7. 唤起觉察 · Evokes Awareness

## 一句话定义
（30 字内的中文一句话，让初学者立刻抓住本质）

## 完整定义（来自 ICF 官方）
（中文翻译 + 一段简明阐释，约 200 字）

## ACC 判定标准（"做到了"长什么样）
- ✅ ……
- ✅ ……
- ✅ ……
（4-6 条，每条具体可观察）

## PCC 判定标准（比 ACC 更深的地方）
- ✅ ……
- ✅ ……
- ✅ ……
（4-6 条，**重点写 PCC 跟 ACC 拉开差距的关键差异**）

## 常见误区（学习者最容易踩的坑）
- ❌ ……
- ❌ ……
- ❌ ……
（3-5 条，每条要带"为什么这是错的"的一句解释）

## 典型示例（教练对话片段）

**场景**：（一段 200 字内的虚构教练对话场景，自然展示这项能力的运用）

**对话**：
> **客户**：……
> **教练**（PCC 级）：……
> **客户**：……
> **教练**（PCC 级）：……

**评注**：（200 字内，指出哪几句体现了本能力的 PCC 级运用，为什么）

## 反例（同样场景，能力不到位的对比）
（200 字内，展示 ACC 都没做到 / 教练误用提问的反例 + 一句话点评）

## 与其他能力的关系
- **强相关**：第 X 项（XXX）—— 一句话说怎么相关
- **容易混淆**：第 Y 项（YYY）—— 一句话说怎么区分

## 推荐阅读
- ICF 官方文档：[ICF Core Competencies (Updated)](https://coachingfederation.org/credentials-and-standards/core-competencies)
- （其他公开材料链接，如有）

---
*整理：河虾 GLM 5.1 / 鳌虾终审 / 2026-05-XX*
```

---

## 成功标准（鳌虾验收会逐项核）

| # | 标准 | 失败判定 |
|---|---|---|
| 1 | 8 个文件全部交付，文件名严格遵守 | 缺一个 = 不通过 |
| 2 | 每个文件 ≥ 800 字（中文字符），≤ 2500 字 | 低于 800 = 重做 |
| 3 | 每个文件有完整 7 个章节（一句话/完整定义/ACC/PCC/误区/示例/反例/关系/阅读） | 缺章节 = 重做 |
| 4 | "ACC vs PCC 判定差异"是核心，不能只说"PCC 比 ACC 更深"这种空话 | 空话 = 重做 |
| 5 | 示例对话**可信**（教练同行读了不会觉得假），客户和教练的话各 ≥ 4 轮 | 不可信 = 重做 |
| 6 | YAML frontmatter 完整、字段齐全 | 缺字段 = 鳌虾自补可过 |
| 7 | 不抄 ICF 官方原文（原文版权），用自己的话阐释 | 大段抄袭 = 重做 |
| 8 | 中文流畅、术语统一（同一概念全文同一译法） | 翻译跳变 = 重做 |

---

## 输出位置

落到坚果云：
```
/Users/shenfeng/Nutstore Files/FS_KM/04_FS_Projects/AI_Coach_KB_v1/seed_content/
├── competency_01_demonstrates_ethical_practice.md
├── competency_02_embodies_a_coaching_mindset.md
├── competency_03_establishes_and_maintains_agreements.md
├── competency_04_cultivates_trust_and_safety.md
├── competency_05_maintains_presence.md
├── competency_06_listens_actively.md
├── competency_07_evokes_awareness.md
└── competency_08_facilitates_client_growth.md
```

---

## 给河虾的额外指导

1. **你是中文合规主笔**——这 8 篇是新站的种子内容，质量决定第一印象。慢一点没关系，糙了我打回。
2. **ACC 和 PCC 差异是关键**——很多中文资料含糊带过这块，你要写得**学习者读完知道自己离 PCC 还差什么**。
3. **示例对话要真实**——别用"客户：我最近很迷茫" "教练：你能多说说吗"这种俗套，写**有具体细节、有情感张力**的场景。
4. **遇到不确定的判定，标 `[?]` 留给鳌虾终审**，不要瞎猜。
5. **完成后**：把文件落到上述目录，给鳌虾发一条飞书说"8 篇 rubric 已交付"，鳌虾会在你睡前回收验收。

---

## 派单渠道

鳌虾通过 **OpenCode :4096** 的 `/session/{id}/prompt_async` 把这份 brief 推给你。如果你看到这条 brief 但没收到 prompt，说明渠道挂了——直接在飞书 ping 鳌虾。

# 派单：河虾 · 验真 resources_curated.md 中的 21 处 [待验证]

> **派单人**：鳌虾 · 工头
> **执行人**：河虾（用你的 MCP 中台 perplexity_search / metaso_search / firecrawl_search / firecrawl_scrape）
> **派单时间**：2026-05-11 20:40
> **目标**：今晚搞定 21 处 [待验证] 至少 80% 准确

---

## 上下文

你昨晚交付了 `seed_content/resources_curated.md`（47 条，自评 6/10），自暴扣分点："出版信息和公众号链接不够确定"，标了 21 处 `[待验证]`。今晚用 MCP 真搜真验。

## 你要做的

### 1. 扫描文件找出所有 [待验证] 位置
```
file = ~/Nutstore Files/FS_KM/04_FS_Projects/AI_Coach_KB_v1/seed_content/resources_curated.md
grep -n "\[待验证\]" $file
```

### 2. 对每处 [待验证]，按下面决策树处理

| 类型 | 验证方法 |
|---|---|
| **书的译者/出版社/年份** | `metaso_search` 或 `perplexity_search` "<书名 中文版 译者 出版社"，匹配豆瓣/当当结果 |
| **公众号名称/主理人** | `firecrawl_scrape` "https://weixin.sogou.com/weixin?type=2&query=<公众号名>"，或 perplexity 搜 |
| **课程/培训机构 ICF 认证状态** | `firecrawl_scrape` 机构官网 + ICF 官网 `https://coachingfederation.org/icf-credential/find-a-training` 验证 |
| **音视频具体链接** | `metaso_search` 或 `perplexity_search` 找具体 B站/YouTube 视频 URL（不接受搜索页 URL） |

### 3. 修改文件

对每处验真：
- **找到实证**：去掉 `[待验证]` 标记，填入真实信息（带链接）
- **未找到**：保留 `[待验证]` 标记，**但加一个注释**说明"搜过 N 次仍未找到，建议鳌虾人工核实或替换"
- **发现资源不存在/已下架**：标 `[已失效]`，加注释建议替换

### 4. 整体审查 - 再读一遍清单

读完之后给每节打一个 1-10 分（真实性+实用性），列在文件末尾的 "## 验真审查报告" 章节。

## 成功标准

| # | 标准 | 失败判定 |
|---|---|---|
| 1 | 21 处 [待验证] 全部处理（要么验真要么标 [已失效]/补注释） | 漏一处 = 重做 |
| 2 | 验真的资源信息**有 source link**（你查了哪个网页/搜索结果） | 无来源 = 等于没验 |
| 3 | 不要"自信地编造"——找不到就老实说找不到 | 编造 = 重做+扣信任 |
| 4 | 文件末尾加 "## 验真审查报告"，每节打分 + 总自评 | 漏 = 补 |
| 5 | 不影响其他章节（不要顺手改未标 [待验证] 的内容） | 误改 = 回滚 |
| 6 | 修改后总字数控制在 4500-7000（不要因为加注释爆字数） | 严重超 = 精简 |

## 交付方式

直接覆盖原文件 `seed_content/resources_curated.md`。完成后给鳌虾回：
- `done`
- 21 处中**验真成功 N 处 / 标失效 M 处 / 仍不确定 K 处**
- 自评（1-10）+ 哪几节质量提升最大

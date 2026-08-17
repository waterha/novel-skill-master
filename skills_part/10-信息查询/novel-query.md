# 🔎 novel-query — 项目信息查询

## 概述
查询设定、角色、力量体系、势力、伏笔、金手指、节奏等。自动根据关键词识别查询类型。全只读操作。

## 所属阶段
第十阶段：信息查询

## 输入
- 自然语言查询关键词
- 项目数据源（master_state.json / outline_manifest.json / 设定文件 / index.db / .story-system 合同）

## 查询类型一览

| 关键词 | 查询类型 | 数据源 |
|--------|---------|--------|
| 角色/主角/配角 | 角色查询 | 主角卡.md, 角色库/ |
| 境界/筑基/金丹 | 境界查询 | 力量体系.md |
| 宗门/势力/地点 | 地理查询 | 世界观.md |
| 伏笔/紧急伏笔 | 伏笔分析 | master_state.json + foreshadowing.md |
| 金手指/系统 | 金手指状态 | master_state.json |
| 节奏/Strand | 节奏分析 | master_state.json + strand-weave-pattern |
| 标签/实体/格式 | 格式查询 | tag-specification.md |
| 时间/日期/倒计时 | 时间线查询 | 卷纲 + 编年史 |
| [角色名]历史/状态 | 时序查询 | knowledge query-entity-state |

## 数据源优先级（严格分级）

**第1优先**：`.story-system/` 合同（最高权威）
- MASTER_SETTING.json
- 卷合同 / 章合同

**第2优先**：latest accepted commit
- 已发布章节定稿状态
- 正式提交的 fulfillment.json

**第3优先**：memory-contract load-context
- 记忆编排层
- 当前会话上下文

**第4优先**：`.webnovel/master_state.json` / `.webnovel/outline_manifest.json` / `index.db`
- 投影层，仅降级使用
- 可能滞后于实际提交

## 输出格式

统一模板：
```
┌─ 查询结果 ─────────────────────────────┐
│ 查询类型：[角色/境界/势力/伏笔/...]     │
│ 数据源：[数据源文件名 + 优先级]          │
│ 匹配数量：[N] 条                         │
├─────────────────────────────────────────┤
│ 详细信息：                               │
│   [逐条展示，含文件路径和行号]           │
│                                         │
│ 数据一致性检查：                         │
│   ✓ [项目] 与 [数据源] 一致              │
│   ⚠ [项目] 状态可能已过期 (建议检查)     │
└─────────────────────────────────────────┘
```

## 智能识别机制
- 自然语言输入自动映射
  - "主角现在什么境界了？" → 境界查询 + 主角
  - "XXX 和 YYY 什么关系？" → 角色关系查询
  - "第 50 章的伏笔回收了吗？" → 伏笔状态查询
- 模糊匹配：关键词容错（同音/近义词）

## 参考文件
- foreshadowing.md（伏笔指南）
- tag-specification.md（标签规范）
- strand-weave-pattern.md（Strand编织模式）
- cool-points-guide.md（爽点指南）
- reading-power-taxonomy.md（追读力分类）

## 故障恢复
| 问题 | 处理方式 |
|------|---------|
| 无法识别查询意图 | 提示用户从查询类型列表中选择 |
| 数据源不存在 | 降级到次优先级数据源并标注"数据可能不完整" |
| 所有数据源不可用 | 提示用户运行 novel-doctor 检查项目完整性 |

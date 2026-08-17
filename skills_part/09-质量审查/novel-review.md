# 🔍 novel-review — 章节质量审查

## 概述
独立审查已有章节（不依赖写章流程），从设定/文笔/逻辑/节奏/商业化 6 个维度生成结构化问题列表，指标写入 index.db。

## 所属阶段
第九阶段：质量审查

## 输入
- 待审正文
- 项目投影状态（角色/设定状态快照）
- 审查参考文件
- ★ 知识图谱文件 `.story-system/story_graph.json`（v2.0 新增）
- 伏笔统一账本 `.story-system/foreshadowing.json`

## 核心流程

### Step 1：解析项目根
- 加载 runtime 合同
- 确认审查阶段（初期/中期/后期—不同阶段侧重点不同）

### Step 2：加载参考资料
- core-constraints.md（核心约束检查表）
- cool-points-guide.md（爽点指南）
- common-mistakes.md（常见错误清单）
- pacing-control.md（节奏控制）
- **MASTER_SETTING.json（设定契约 — 自动化验证依据，必需）**
- **setting-contract-schema.md（设定契约规范）**
- **setting-consistency.md（契约验证规则）**
- ★ **story_graph.json（知识图谱 — 图谱一致性检查依据）**

### Step 2.5：执行设定契约验证（自动）
加载 `.story-system/MASTER_SETTING.json`，执行自动化验证：

```
验证项（全部自动，无需人参与）：
□ 力量等级验证 — 抽取正文技能 vs 契约 abilities/limits
□ 世界规则验证 — 正文事件 vs hard_rules
□ 角色一致性验证 — 主角行为 vs forbidden_actions
□ 反派隐蔽验证 — 未揭示反派的隐藏设定是否提前暴露
□ 伏笔状态验证 — 伏笔是否在禁区前被揭示 / 是否超期未回收
□ 时间线验证 — 正文中的时间/季节/日期与契约编年一致

结果输出：
- 任何 blocking 违规 → 直接加入审查报告的 blocking 列表
- major 违规 → 加入 major 列表
- 无违规 → 标记 "setting_contract_verified: true"
```

> **设计理由**：将契约验证放在审查流程的第二步，在人工审查之前先跑一轮机器验证，确保设定层面的硬伤在人工介入前已被拦截。

### Step 2.6：执行知识图谱一致性验证（v2.0 新增）
调用 `python tools/story_graph_builder.py validate --project-root <路径>` 和 `python tools/story_graph_builder.py generate-context --project-root <路径> --chapter <当前审查章节>`，执行图谱层面的验证：

```
图谱验证项（自动）：
□ 已死亡角色未在正文中出现在当前剧情
□ 未解决伏笔未超期
□ 角色当前位置与图谱记录一致
□ 正文中出现的角色/地点在图谱中有对应节点
□ 势力关系与图谱记录一致
```

### Step 2.7：执行节奏与反刹车检查（v2.0 新增）
调用 `python tools/pacing_tracker.py audit --project-root <路径> --recent <N>` 和 `python tools/anti_resolution_guard.py check --project-root <路径> --chapter <N>`：

```
节奏验证项（自动）：
□ 当前章节节奏符合档位要求（慢/中/快合理分布）
□ 无反刹车违规（非终局章节未解决核心冲突）
□ 章末存在悬念钩子
□ 事件类型无过度重复
□ 快档比例未超出卷内上限
```

### Step 3：加载待审数据
- 项目投影状态（当前所有角色/设定状态快照）
- 待审正文
- ★ 知识图谱上下文（来自 Step 2.6 的 `generate-context` 输出）
- 运行 `foreshadowing_tracker.py due`，加载当前章应处理的伏笔和本章写后账本变化

检查正文是否漏掉到期伏笔、提前揭示未到期伏笔、声称回收却没有解决当前问题，或埋下新伏笔但未登记来源、目的和回收窗口。信号词候选不能替代语义证据。

### Step 4：调用 Reviewer Agent → 结构化 JSON
每个 issue 必须有 `evidence`（引用原文），不能是模糊感受。

**issue 结构：**
```json
{
  "id": "REV-001",
  "severity": "blocking" | "major" | "minor" | "suggestion",
  "category": "设定" | "文笔" | "逻辑" | "节奏" | "商业化" | "★ 契约" | "★ 图谱" | "★ 节奏",
  "location": {"chapter": 15, "paragraph": 3},
  "title": "角色力量等级与设定不符",
  "description": "主角在元婴初期无法使用 XXX 技能",
  "evidence": "原文：'XXX'；设定：'元婴初期不可使用'",
  "suggested_fix": "删除该句或改为'尝试失败'",
  "blocking": true | false
}
```

**新增类别说明（v2.0）：**
| 类别 | 说明 | 来源 |
|------|------|------|
| ★ 契约 | 设定契约机器验证发现 | Step 2.5 自动 |
| ★ 图谱 | 知识图谱一致性验证发现 | Step 2.6 自动 |
| ★ 节奏 | 节奏控制/反刹车验证发现 | Step 2.7 自动 |

### Step 5：生成审查报告 → 落库
```
审查报告结构：
├── 总览（问题数 / 阻断数 / 评分）
├── 阻断问题（blocking=true，需优先处理）
│   ├── [REV-001] 力量等级不一致 (blocking)
│   └── [REV-002] 时间线矛盾 (blocking)
├── 其他问题
│   ├── [REV-003] 段落过长 (major)
│   ├── [REV-004] 用词重复 (minor)
│   └── [REV-005] 建议增加环境描写 (suggestion)
├── ★ 节奏审查结果
│   ├── 节奏档位分布：[慢 X / 中 X / 快 X]
│   ├── 反刹车状态：通过/失败
│   └── 章末钩子：有/无
├── 修复方向（按优先级排序）
├── 成功标准（通过审查需要达到的条件）
└── review_metrics 已写入 index.db
```

### Step 6：阻断问题用户裁决
- 立即修复 → 重新审查
- 稍后处理 → 标记 deferred，记录原因
- 忽略 → 记录用户理由

## 六维评分体系（v2.0 扩展）

| 维度 | 权重 | 评分项 | 满分 |
|------|------|--------|------|
| 设定一致性 | 25% | 角色/世界观/力量体系无矛盾 | 100 |
| 文笔质量 | 20% | 句式变化/修辞/Anti-AI | 100 |
| 逻辑链条 | 15% | 因果合理/无机械降神 | 100 |
| 节奏控制 | 15% | 爽点密度/情绪曲线/阅读节奏 | 100 |
| 商业化 | 10% | 钩子效果/追读驱动/代入感 | 100 |
| ★ 反刹车合规 | 15% | 核心冲突未提前解决/章末有悬念/配额合规 | 100 |

> **Anti-AI 辅助评分**：文笔质量维度中，可调用 `tools/anti_ai_check.py score --chapter <路径>` 获取客观的 Anti-AI 检测评分作为参考。

总分 = 各维度加权和。≥85 分 → 优质；70-84 → 合格；<70 → 需修改

## 产出文件
```
.story-system/reviews/
  └── 卷号-章号-review.json
.webnovel/index.db — review_metrics 表追加记录
```

## 质量闸门
- [ ] 所有 issue 都有 evidence 引用
- [ ] blocking issue 已用户裁决
- [ ] review_metrics 已写入 index.db
- [ ] ★ 设定契约验证已执行（setting_contract_verified: true 或已处理所有 blocking 违规）

## 参考文件
- common-mistakes.md（常见错误清单）
- pacing-control.md（节奏控制指南）
- core-constraints.md（核心约束检查表）
- review-schema.md（审查模式规范）

## 故障恢复
| 问题 | 处理方式 |
|------|---------|
| 审查结果 JSON 解析失败 | 重试 Reviewer Agent 调用 |
| 投影状态缺失 | 仅审查文本逻辑，跳过设定一致性检查 |
| 用户对裁决犹豫 | 展示具体影响分析和修复难度对比 |

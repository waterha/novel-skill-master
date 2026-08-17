# 📜 设定契约规范（Setting Contract Schema）

## 概述

设定契约是将小说设定从"写在文档里的描述"转化为**可被自动验证的结构化约束**。它是根治设定崩塌的根本机制。

### 核心理念
```
❌ 传统方式：设定写在 MD 文档里 → 人自己记着 → 写着写着就忘了 → 崩塌
✅ 契约方式：设定写成 JSON 契约 → Agent 自动加载 → 写章后自动验证 → 拦截
```

### 适用性
**本契约体系通用，不依赖特定题材。** 无论玄幻、都市、悬疑、言情、科幻、历史——契约的结构都适用，区别仅在于填入的具体内容不同。

### 契约 vs 文档的分工

| 方式 | 用途 | 谁来读 | 更新频率 |
|------|------|--------|---------|
| 设定文档（.md） | 完整描述、故事、灵感 | 人类作者 | 不定期 |
| 设定契约（.json） | 可验证的约束、边界 | Reviewer Agent | 每次设定变更 |

---

## 一、契约文件体系

```
.story-system/
  ├── MASTER_SETTING.json       ← ★ 主契约（必须）
  ├── character_states.json     ← 角色状态快照（自动维护）
  └── world_contract.json       ← 世界规则契约（可选）
```

---

## 二、主契约格式（MASTER_SETTING.json）

### 顶层结构

```json
{
  "contract_version": "1.0",
  "genre": "作品题材",
  "last_updated": "2026-06-08",
  "project_name": "作品名称",
  "capability_system": { /* 通用能力体系 */ },
  "world_rules": { /* 世界规则 */ },
  "characters": { /* 角色契约 */ },
  "active_foreshadowing": [],
  "info_barriers": [],
  "consistency_rules": [],
  "change_log": []
}
```

以下各节详细展开，每节为一个独立文件：

| 文件 | 内容 |
|------|------|
| [contract-capability.md](contract-capability.md) | ★ 2.1 通用能力体系契约（最核心部分） |
| [contract-rules.md](contract-rules.md) | 2.2~2.7 世界规则 / 角色 / 信息壁垒 / 伏笔 / 一致性 / 变更日志 + 变更流程 + 验证引擎 + 维护 |
| [contract-examples.md](contract-examples.md) | 完整示例（悬疑/言情/科幻/历史）+ 使用说明 |

---

> **核心设计原则**：契约不关心你写的是什么题材——它只关心一件事：**角色当前应该能做什么、不能做什么**。这个边界可以是修为境界，可以是商业资本，可以是案件的线索量，可以是感情的发展阶段。契约统一用 capabilities/limits/phases 来描述，对任何题材一视同仁。

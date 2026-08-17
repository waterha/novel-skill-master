# 设定契约 — 规则 / 角色 / 验证 / 维护

> 本文件是 [setting-contract-schema.md](setting-contract-schema.md) 的子文件，包含 2.2~2.7 契约字段定义及三~五章（变更流程/验证引擎/维护）。
> 能力体系见 [contract-capability.md](contract-capability.md)，完整示例见 [contract-examples.md](contract-examples.md)。

---

## 2.2 世界规则契约（world_rules）

通用格式，与题材无关：

```json
{
  "world_rules": {
    "world_basics": {
      "setting_type": "现实世界 | 架空历史 | 奇幻异界 | 未来科幻 | 末世废土",
      "core_premise": "一句话世界观",
      "time_flow": "与现实1:1（或其他）",
      "genre_rules": [
        {"rule": "本题材的基本类型约束", "explanation": "悬疑必须逻辑闭环 / 力量必须有上限"},
        {"rule": "不能混入不符合题材的要素", "explanation": "都市现实不应突然出现超自然力量"}
      ]
    },
    "hard_rules": [
      {
        "id": "WR-001",
        "rule": "描述具体规则",
        "violation": "blocking | major",
        "can_break": false
      }
    ]
  }
}
```

**各题材 hard_rules 示例：**
```json
// 玄幻：{"rule":"此方世界最高只能修炼到大乘期","violation":"blocking","can_break":true,"break_condition":"集齐五把上古神器"}
// 都市：{"rule":"主角不能使用超自然能力","violation":"blocking","can_break":false}
// 悬疑：{"rule":"凶手不能是故事开头未出现过的角色","violation":"major","can_break":false}
// 言情：{"rule":"核心障碍不能毫无解决地消失","violation":"major","can_break":false}
// 科幻：{"rule":"科技设定必须在故事规则内保持自洽","violation":"blocking","can_break":false}
// 历史：{"rule":"重大历史事件的走向不能随意改变","violation":"blocking","can_break":true,"break_condition":"充分的蝴蝶效应铺垫"}
```

**验证**：Reviewer Agent 检查正文行为是否触犯 hard_rules，can_break:false 的违反直接 blocking。

---

## 2.3 角色契约（characters）— 题材通用

```json
{
  "characters": {
    "主角": {
      "id": "protagonist", "role_type": "主角 | 反派 | 配角",
      "core_personality": ["3-5个核心性格形容词"],
      "flaw": "影响关键决策的致命缺陷",
      "flaw_effect": "缺陷在关键章节导致失败的描述",
      "forbidden_actions": ["角色绝不会做的事"],
      "capability_timeline": {
        "力量/武力": [{"chapter_from":1,"chapter_to":20,"phase":"阶段一"}],
        "知识/信息": [{"chapter_from":1,"chapter_to":15,"phase":"知识空白期"}]
      },
      "known_info": ["角色当前已知道的关键信息"],
      "relationships": {"角色名": "信任/怀疑/敌对"}
    },
    "反派/秘密角色": {
      "id": "antagonist", "core_trait": "表面特征",
      "hidden_truth": "隐藏的真实身份", "reveal_chapter": 45,
      "forbidden_before_reveal": ["揭示前绝对不能暴露的设定"]
    }
  }
}
```

**验证**：
- capability_timeline：检查各维度当前阶段是否在预期范围内
- forbidden_actions：违反核心性格 → major~blocking
- forbidden_before_reveal：隐藏设定提前暴露 → blocking
- known_info：跨章检查角色没有"忘记"已知信息

---

## 2.4 信息壁垒契约（info_barriers）

悬疑/推理题材专用，但其他题材也可用（秘密不能提前泄露、身世之谜不能提前揭示等）：

```json
{
  "info_barriers": [
    {"id":"IB-001","barrier":"侦探不能在第20章前知道凶手身份","violation":"blocking"},
    {"id":"IB-002","barrier":"主角身世之谜必须在第60-70章揭示","violation":"blocking"}
  ]
}
```

**验证**：检查正文中是否有角色在禁区时间点前获得禁忌信息 → blocking。

---

## 2.5 活跃伏笔契约（active_foreshadowing）— 通用

```json
{
  "active_foreshadowing": [{
    "id":"F-001","content":"伏笔内容","plant_chapter":3,
    "planned_reveal_chapter":80,"status":"planted|ready|revealed",
    "must_not_be_revealed_before":75,
    "checks":["哪些行为会提前暴露伏笔"]
  }]
}
```

---

## 2.6 一致性规则（consistency_rules）— 通用

```json
{
  "consistency_rules": [
    {"id":"CR-001","rule":"角色能力提升速度应与故事节奏匹配","type":"growth_rate"},
    {"id":"CR-002","rule":"同一场景中空间位置不能前后矛盾","type":"spatial"},
    {"id":"CR-003","rule":"角色不能使用尚未获得的知识","type":"knowledge","genre_note":"悬疑题材尤其重要"},
    {"id":"CR-004","rule":"情感/关系进展不能跳跃缺失中间步骤","type":"relationship","genre_note":"言情题材尤其重要"}
  ]
}
```

---

## 2.7 设定变更日志（change_log）— 通用

```json
{
  "change_log": [{
    "date":"2026-06-08","chapter":25,"changed_item":"具体变更",
    "reason":"变更理由","approved":true,"verification":"扫描结果"
  }]
}
```

---

## 三、设定变更正式流程

当情节需要突破已有设定时，**严禁静默违反**。必须走正式流程：

```
[情节需要突破设定]
  │
  ▼
[识别冲突类型] → 能力违规 / 世界违规 / 角色违规 / 伏笔违规 / 信息违规
  │
  ▼
[3选1 解决方案]
  ├─ 方案A：改设定（提升阶段/放宽规则）
  │   → 需要前文铺垫 + 更新 MASTER_SETTING.json + 全篇扫描
  ├─ 方案B：改情节（推荐，涟漪效应最小）
  └─ 方案C：加代价（使用但承受反噬，代价成为新剧情点）
  │
  ▼
[记录到 change_log] → [更新 MASTER_SETTING.json] → [如选A，全篇回归扫描]
```

---

## 四、契约验证引擎（Reviewer Agent 行为规范）

### 4.1 写章后即时验证（novel-write Step 3）

```
验证清单：
□ 加载 MASTER_SETTING.json + character_states.json
□ 能力阶段验证：正文行为 vs 当前阶段 capabilities/limits
□ 世界规则验证：关键事件 vs hard_rules
□ 角色一致性：主角 forbidden_actions / 反派 forbidden_before_reveal
□ 伏笔验证：must_not_be_revealed_before 是否被遵守
□ 信息壁垒验证：角色是否获得不应知晓的信息
```

### 4.2 跨章回归验证（每10章）

```
□ 加载全部 fulfillment.json
□ 追踪每条 capability_timeline 的实际达成情况
□ 检测角色位置是否有断层
□ 检测已回收伏笔是否被再次使用
□ 检测 known_info 连续性
```

### 4.3 验证结果严重级别

| 违规类型 | 级别 | 处理 |
|---------|------|------|
| 使用超出当前阶段的能力/知识/资源 | blocking | 修复或走变更流程 |
| 违反 can_break=false 的世界规则 | blocking | 必须修复 |
| 角色 OOC（违反核心性格） | major~blocking | 严重则 blocking |
| 信息被提早获得 | blocking | 必须修复 |
| 能力/知识跳跃式增长 | major | 补充过渡章节 |
| 伏笔被提前揭示 / 遗忘超期 | blocking / major | 修复或处理 |
| 空间/位置断层 | minor | 可暂缓 |

---

## 五、契约的维护

### 初始化时机
- `novel-settings` 完成时生成初始 MASTER_SETTING.json
- 只启用该题材需要的维度（不需要的设 enabled: false）
- `novel-init` 时写入 `.story-system/` 目录

### 更新时机
- 角色进阶 → 更新 capability_timeline
- 埋设伏笔 → 追加 active_foreshadowing
- 获得关键信息 → 追加 known_info
- 新增信息壁垒 → 追加 info_barriers
- 走变更流程 → 记录 change_log

### 谁负责更新
- **人类作者**：设定阶段手动编辑 MASTER_SETTING.json
- **写章引擎**：自动维护 character_states.json
- **Reviewer Agent**：验证合规性，不修改契约本身

---

> 🡐 [返回 setting-contract-schema.md](setting-contract-schema.md) | 继续阅读 [contract-examples.md](contract-examples.md)

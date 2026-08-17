# 设定契约 — 完整示例与使用说明

> 本文件是 [setting-contract-schema.md](setting-contract-schema.md) 的子文件。能力体系见 [contract-capability.md](contract-capability.md)，规则/验证见 [contract-rules.md](contract-rules.md)。

---

## 六、契约完整示例（各题材缩略版）

### 示例1：悬疑/推理 — 《第七个证人》

```json
{
  "contract_version": "1.0", "genre": "悬疑", "project_name": "第七个证人",
  "capability_system": {
    "dimensions": [
      { "dimension": "知识/信息", "enabled": true,
        "phases": [
          {"phase_name":"收集期","min_chapter":1,"max_chapter":12,
           "capabilities":["基础勘察","证人询问"],
           "limits":["不能锁定真凶","不能掌握只有凶手才知的细节"]},
          {"phase_name":"推理期","min_chapter":13,"max_chapter":25,
           "capabilities":["关联分析","侧写"],
           "limits":["不能在没有确凿证据链的情况下下结论"]}
        ]
      },
      { "dimension": "社会/地位", "enabled": true,
        "phases": [{"phase_name":"普通警员","capabilities":["案件调查权"],"limits":["不能跨部门调取机密档案"]}]
      }
    ]
  },
  "world_rules": { "hard_rules": [
    {"rule":"所有线索必须在结局前向读者公平呈现","violation":"blocking","can_break":false},
    {"rule":"凶手不能是开局后凭空出现的新角色","violation":"major","can_break":false}
  ]},
  "info_barriers": [{"barrier":"侦探不能在第20章前知道凶手","violation":"blocking"}],
  "characters": {
    "侦探": {"flaw":"过于自信","forbidden_actions":["不能无视显而易见的证据"]},
    "真凶-死者配偶": {
      "hidden_truth":"真凶","reveal_chapter":28,
      "forbidden_before_reveal":["不能表现出超出正常悲伤的反应","不能提前暴露犯罪知识"]
    }
  }
}
```

---

### 示例2：都市/言情 — 《迟来的告白》

```json
{
  "contract_version": "1.0", "genre": "言情", "project_name": "迟来的告白",
  "capability_system": {
    "dimensions": [
      { "dimension": "情感/心理", "enabled": true,
        "phases": [
          {"phase_name":"初识","min_chapter":1,"max_chapter":10,
           "capabilities":["普通社交","好感萌芽"],"limits":["不能表白","不能过早确定关系"]},
          {"phase_name":"靠近","min_chapter":8,"max_chapter":25,
           "capabilities":["单独约会","暗示好感"],"limits":["不能提前解决核心障碍"]},
          {"phase_name":"考验","min_chapter":20,"max_chapter":40,
           "capabilities":["深度交流","处理第三方"],"limits":["不能在未解决核心矛盾前复合"]}
        ]
      },
      { "dimension": "社会/地位", "enabled": true,
        "phases": [
          {"phase_name":"陌生人","capabilities":["无交集"],"limits":["不能进入对方家庭圈"]},
          {"phase_name":"朋友","capabilities":["共同社交圈"],"limits":["不能干涉对方家庭决策"]}
        ]
      }
    ]
  },
  "world_rules": { "hard_rules": [
    {"rule":"感情发展必须有合理铺垫","violation":"major","can_break":false},
    {"rule":"核心障碍不能凭空消失","violation":"major","can_break":false}
  ]},
  "characters": {
    "女主": {"flaw":"缺乏安全感","forbidden_actions":["不会轻易说出真实感受"]},
    "男主": {"flaw":"逃避型人格","forbidden_actions":["不会主动面对感情问题"]}
  }
}
```

---

### 示例3：科幻/星际 — 《深空回响》

```json
{
  "contract_version": "1.0", "genre": "科幻", "project_name": "深空回响",
  "capability_system": {
    "dimensions": [
      { "dimension": "力量/武力", "enabled": true,
        "phases": [
          {"phase_name":"平民期","capabilities":["基础体能"],"limits":["不能操作军用级武器"]},
          {"phase_name":"受训期","capabilities":["标准制式武器","基础飞船驾驶"],"limits":["不能驾驶旗舰级飞船"]}
        ]
      },
      { "dimension": "知识/信息", "enabled": true,
        "phases": [{"phase_name":"无知期","capabilities":["民用科技知识"],"limits":["不能理解外星文明语言"]}]
      }
    ]
  },
  "world_rules": { "hard_rules": [
    {"rule":"超光速旅行必须消耗巨大能量","violation":"major","can_break":false},
    {"rule":"外星文明的行为逻辑须内在一致","violation":"blocking","can_break":false}
  ]}
}
```

---

### 示例4：历史/权谋 — 《长安棋局》

```json
{
  "contract_version": "1.0", "genre": "历史", "project_name": "长安棋局",
  "capability_system": {
    "dimensions": [
      { "dimension": "社会/地位", "enabled": true,
        "phases": [
          {"phase_name":"寒门","capabilities":["基本社交权"],"limits":["不能直接面圣","不能调遣军队"]},
          {"phase_name":"入仕","capabilities":["低级官职","有限话语权"],"limits":["不能参与国策决策"]},
          {"phase_name":"权臣","capabilities":["中枢决策权","调配资源"],"limits":["不能篡位（除非刻意设计）"]}
        ]
      },
      { "dimension": "知识/信息", "enabled": true,
        "phases": [{"phase_name":"蒙昧期","capabilities":["地方见闻"],"limits":["不能知晓朝廷核心机密"]}]
      }
    ]
  },
  "world_rules": { "hard_rules": [
    {"rule":"公元前的社会制度必须符合当时生产力水平","violation":"major","can_break":false},
    {"rule":"角色言行不能超出时代认知（穿越设定除外）","violation":"major","can_break":true,"break_condition":"主角为穿越者"}
  ]},
  "info_barriers": [{"barrier":"主角不能在第30章前察觉丞相谋反","violation":"blocking"}]
}
```

---

## 七、使用说明：按题材配置契约

| 步骤 | 操作 | 示例 |
|------|------|------|
| 1 | 确定题材 | 悬疑推理 |
| 2 | 选择需要启用的能力维度 | 知识/信息 + 社会/地位，其余设 enabled:false |
| 3 | 定义每个维度的阶段 | 知识：收集期→推理期→真相期 |
| 4 | 定义每个阶段的 capabilities/limits | 收集期不能锁定真凶 |
| 5 | 定义世界规则 hard_rules | 线索公平性 |
| 6 | 定义角色契约 | 侦探缺陷、反派隐藏信息 |
| 7 | 定义信息壁垒（如需） | 侦探何时可以知道真相 |
| 8 | 定义伏笔时间线 | 关键线索何时揭示 |
| 9 | 完成！Reviewer Agent 开始自动验证 | |

---

> 🡐 [返回 setting-contract-schema.md](setting-contract-schema.md)

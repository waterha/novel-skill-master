# 设定契约 — 2.1 通用能力体系（capability_system）

> 本文件是 [setting-contract-schema.md](setting-contract-schema.md) 的子文件，详细展开主契约中最核心的部分。

---

## 2.1 ★ 通用能力体系契约（capability_system）

这是全契约最核心的部分，替代了旧版中仅适用于修仙的"力量体系"。它本质上描述的是：**角色在故事的每一个阶段，能做什么、不能做什么**。

在契约层面，能力分为以下通用维度——各题材按需取用：

| 通用能力维度 | 玄幻/仙侠 | 都市/现实 | 悬疑/推理 | 言情 | 科幻 | 历史/架空 |
|-------------|-----------|-----------|-----------|------|------|----------|
| 力量/武力 | 修为境界、法术 | 体力、格斗 | 无（或弱化） | 无（或弱化） | 科技武器、超能力 | 武艺、兵力 |
| 知识/信息 | 功法、阵法 | 行业知识、学历 | 线索、推理技巧 | 情感认知 | 科学理论 | 历史知识、谋略 |
| 资源/财富 | 灵石、丹药 | 资金、人脉 | 技术手段、警力 | 社交资源 | 能源、科技资源 | 粮草、权势 |
| 社会/地位 | 宗门身份 | 职位、社会圈层 | 警衔、权限 | 家庭背景 | 军衔、等级 | 官位、爵位 |
| 情感/心理 | 道心、心魔 | 心理承受力 | 心理素质 | 情感成熟度 | 心理稳定性 | 政治觉悟 |

> 每个题材只需要取用其中 1-3 个维度。重点是明确每个维度下的"当前阶段允许做什么、不允许做什么"。

### 通用能力阶段描述格式

```json
{
  "capability_system": {
    "dimensions": [
      {
        "dimension": "力量/武力",
        "description": "角色在物理层面的行动能力",
        "enabled": true,
        "phases": [
          {
            "phase_name": "阶段一",
            "order": 1,
            "min_chapter": 1,
            "max_chapter": 20,
            "capabilities": ["基础体能运用", "初级格斗技巧"],
            "limits": ["不能以一敌多", "不能使用大规模破坏手段"],
            "advance_requirements": ["足够的训练时间", "关键事件触发"]
          },
          {
            "phase_name": "阶段二",
            "order": 2,
            "min_chapter": 18,
            "max_chapter": 50,
            "capabilities": ["中级战斗技巧", "可使用特定装备"],
            "limits": ["不能超越该世界的物理极限"],
            "advance_requirements": ["完成特定训练", "获得关键装备"]
          }
        ],
        "global_ceiling": "此方世界能力上限",
        "ceiling_can_break": false
      },
      {
        "dimension": "知识/信息",
        "description": "角色掌握的知识和信息量",
        "enabled": true,
        "phases": [{
          "phase_name": "知识空白期",
          "order": 1,
          "min_chapter": 1, "max_chapter": 15,
          "capabilities": ["基本常识", "入门知识"],
          "limits": ["不能知道关键谜底的线索"],
          "advance_requirements": ["接触关键信息源"]
        }],
        "global_ceiling": "该领域人类知识极限"
      }
    ],
    "violation_severity": {
      "使用超出当前阶段的能力": "blocking",
      "获得未解锁的知识/信息": "blocking",
      "能力增长时间线异常（早于min_chapter）": "blocking",
      "能力增长停滞（超过max_chapter 2倍仍未进阶）": "major",
      "天花板被突破但未满足条件": "blocking"
    }
  }
}
```

**验证规则**：Reviewer Agent 提取正文中角色展示的能力/知识/资源，对照当前阶段 `capabilities` 和 `limits`。出现 `limits` 中的行为 → blocking。

---

### 各题材填入示例

**玄幻/仙侠**（启用：力量/武力 + 资源/财富 + 社会/地位）：
```json
{"dimension":"力量/武力","phases":[
  {"phase_name":"练气","capabilities":["灵力感知"],"limits":["不能飞行"]},
  {"phase_name":"筑基","capabilities":["御物","神识10米"],"limits":["神识不超过10米"]},
  {"phase_name":"金丹","capabilities":["飞行","神识100米"],"limits":["不能虚空破碎"]}
]}
```

**都市/商战**（启用：资源/财富 + 知识/信息 + 社会/地位）：
```json
{"dimension":"资源/财富","phases":[
  {"phase_name":"创业初期","capabilities":["启动资金100万","3人团队"],"limits":["不能进行亿元级收购"]},
  {"phase_name":"成长期","capabilities":["流动资金5000万","中型团队"],"limits":["不能操控行业定价权"]},
  {"phase_name":"巨头期","capabilities":["上市企业","行业话语权"],"limits":["不能违反商业反垄断法"]}
]}
```

**悬疑/侦探**（启用：知识/信息 + 社会/地位）：
```json
{"dimension":"知识/信息","phases":[
  {"phase_name":"线索收集期","capabilities":["基础现场勘察","证人询问"],"limits":["不能已经知道真凶是谁"]},
  {"phase_name":"推理期","capabilities":["关联线索分析","侧写"],"limits":["不能在没有证据链的情况下锁定凶手"]},
  {"phase_name":"真相揭示期","capabilities":["锁定最终嫌疑人"],"limits":["凶手不能是自己（除非刻意设计）"]}
]}
```

**言情/都市情感**（启用：情感/心理 + 社会/地位 + 资源/财富）：
```json
{"dimension":"情感/心理","phases":[
  {"phase_name":"初识期","capabilities":["普通社交互动","产生好感"],"limits":["不能在没有充分铺垫下表白"]},
  {"phase_name":"暧昧期","capabilities":["暗示好感","单独约会"],"limits":["不能提前解决核心障碍"]},
  {"phase_name":"考验期","capabilities":["情感博弈","处理第三方"],"limits":["不能在没有关键事件驱动下复合"]}
]}
```

**科幻/末世**（启用：力量/武力 + 知识/信息 + 资源/财富）：
```json
{"dimension":"力量/武力","phases":[
  {"phase_name":"生存期","capabilities":["基础求生","冷兵器"],"limits":["不能对抗高级变异体"]},
  {"phase_name":"成长期","capabilities":["热武器使用","基地防御"],"limits":["不能与军方正面抗衡"]}
]}
```

**历史/权谋**（启用：社会/地位 + 知识/信息 + 资源/财富）：
```json
{"dimension":"社会/地位","phases":[
  {"phase_name":"微末期","capabilities":["底层身份"],"limits":["不能直接面圣","不能调遣军队"]},
  {"phase_name":"上升期","capabilities":["中层官员","有限决策权"],"limits":["不能决定国策方向"]}
]}
```

---

> 🡐 [返回 setting-contract-schema.md](setting-contract-schema.md) | 继续阅读 [contract-rules.md](contract-rules.md)

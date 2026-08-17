# 小说项目分层文件协议

本文件是部、卷、章目录和结构标记的唯一来源。正文之外的每个结构文件首行都使用机器可读标记；`tools/outline_guard.py` 据此判断文件是否完成。

## 目录导航

- 项目目录与状态标记
- 全书总纲、部纲、卷纲、章节索引和章纲
- 章节事实摘要
- 伏笔账本
- 新会话续写上下文
- 写后记忆

## 目录

```text
大纲/
  00-总纲/
    全书总纲.md
  01-部纲/
    第01部-部纲.md
  02-卷纲/
    第01部/
      第001卷-卷纲.md
  03-章纲/
    第01部/
      第001卷/
        卷章节索引.md
        第0001章-章纲.md
正文/
  第01部/
    第001卷/
      第0001章-章名.md
收尾/
  卷/
    第001卷-收尾.md
  部/
    第01部-收尾.md
  全书收尾.md
.webnovel/
  master_state.json
  outline_manifest.json
  project_memory.json
  continuation_inventory.json
  continuation_context.md
.story-system/
  MASTER_SETTING.json
  character_states.json
  timeline.json
  foreshadowing.json
  chapter_summaries/
    第0001章.json
```

卷号和章号在全书内连续编号。部号两位、卷号三位、章号四位，不因进入新部而重置。

## 状态标记

```text
<!-- novel-structure: book; status: confirmed -->
<!-- novel-structure: part; part: 1; status: confirmed -->
<!-- novel-structure: volume; part: 1; volume: 1; status: direction-confirmed -->
<!-- novel-structure: volume; part: 1; volume: 1; status: detailed-confirmed -->
<!-- novel-structure: chapter-index; part: 1; volume: 1; status: confirmed -->
<!-- novel-structure: chapter; part: 1; volume: 1; chapter: 1; status: confirmed -->
```

`direction-confirmed` 表示卷方向已确认，`detailed-confirmed` 表示卷详纲已确认。正文写作要求目标卷达到后者。

## 全书总纲

文件：`大纲/00-总纲/全书总纲.md`

使用以下固定二级标题，标题下必须有实质内容：

- `## 故事承诺`：类型、核心体验、主角最终要解决的问题。
- `## 起点与终点`：主角初始状态、结局方向、最终代价。
- `## 核心冲突`：全书冲突及升级逻辑。
- `## 人物`：主角、关键关系和对手的全书弧线。
- `## 部方向`：全部部的名称、起点、目标、核心冲突、不可逆转折、终点、下一部交接。
- `## 主线、支线与伏笔`：计划推进与回收层级。
- `## 完结标准`：哪些承诺必须兑现，哪些问题允许开放。

## 部纲

文件：`大纲/01-部纲/第NN部-部纲.md`

使用以下固定二级标题：

- `## 本部功能`：在全书中的作用和主题问题。
- `## 承接状态`：人物、世界、关系和未解冲突从何处开始。
- `## 核心冲突与升级`：本部目标、对抗、升级链、关键失败、高潮和不可逆变化。
- `## 人物`：主要人物在本部的弧线起点与终点。
- `## 卷方向`：本部全部卷的名称、叙事任务、主要事件、核心冲突、卷末结果、下一卷钩子。
- `## 收束与交接`：本部收束条件和下一部交接；末部写全书终局接口。

## 卷纲

文件：`大纲/02-卷纲/第NN部/第NNN卷-卷纲.md`

方向版使用固定标题：`## 叙事任务`、`## 起点`、`## 核心冲突`、`## 主要事件`、`## 卷末结果`、`## 下一卷钩子`。

详纲版保留方向版标题，并增加：

- `## 章节范围与时间跨度`。
- `## 剧情单元`：3-6 个单元及其因果关系。
- `## 递增压力`：至少 3 次危机。
- `## 人物弧与关系变化`。
- `## 伏笔`：埋设、推进、回收和延期。
- `## 高潮`。
- `## 闭合与遗留`：卷内闭合项、跨卷遗留项。

## 卷章节索引

文件：`大纲/03-章纲/第NN部/第NNN卷/卷章节索引.md`

使用包含 `章号`、`章名`、`目标`、`冲突`、`转折或发现`、`结果`、`章末钩子`、`剧情单元`、`伏笔动作` 的表格，一次列全本卷所有章节。`伏笔动作` 写伏笔 ID 与计划/埋设/强化/部分回收/完全回收；没有则写“无”。不得用模糊集合代替具体章节。

## 单章章纲

文件：`大纲/03-章纲/第NN部/第NNN卷/第NNNN章-章纲.md`

使用以下固定二级标题：

- `## 叙事任务`：本章如何服务卷纲。
- `## 承接点`：上一章留下的状态和问题。
- `## 开场变化`：本章开始后立即发生什么变化。
- `## 场景`：2-4 个场景；每个场景写地点、人物欲望、阻力、行动、结果和转场因果。
- `## 状态变化`：人物、关系、信息和资源。
- `## 必须出现`。
- `## 不可出现与延迟揭示`。
- `## 伏笔动作`：伏笔 ID、动作类型、原文呈现方式和不可提前揭示边界；没有则写“无”。
- `## 章末结果与钩子`：明确下一章从哪里接。
- `## 目标字数、视角、时间与节奏`。

## 章节事实摘要

文件：`.story-system/chapter_summaries/第NNNN章.json`

每章正文完成后立即生成，使用以下结构：

```json
{
  "chapter": 15,
  "part": 1,
  "volume": 1,
  "title": "章名",
  "summary": "仅记录本章实际发生的事实和因果",
  "facts": ["事实1"],
  "character_changes": ["人物状态变化"],
  "foreshadowing_changes": ["FS-0003：强化"],
  "unresolved_questions": ["仍未解决的问题"],
  "next_handoff": "下一章必须承接的状态",
  "created_at": "ISO-8601"
}
```

续写恢复要求所有已写正文都有摘要。摘要不能写计划中但正文尚未发生的内容。

## 伏笔账本

文件：`.story-system/foreshadowing.json`

顶层为 `{"version": 1, "items": [], "updated_at": "..."}`。每条伏笔使用：

```json
{
  "id": "FS-0001",
  "title": "旧钥匙上的缺口",
  "type": "object",
  "scope": "volume",
  "status": "planted",
  "purpose": "为第二卷密室开启方式提供公平条件，并暗示父亲来过",
  "setup": {
    "part": 1,
    "volume": 1,
    "chapter": 3,
    "scene": "旧宅门厅",
    "evidence": "正文中的准确短句",
    "reader_impression": "读者初读会以为只是旧物磨损",
    "intended_truth": "缺口对应密室机关"
  },
  "context": {
    "window": 2,
    "nearby_chapters": []
  },
  "payoff": {
    "earliest_chapter": 18,
    "target_chapter": 22,
    "latest_chapter": 25,
    "target_volume": 2,
    "target_part": 1,
    "conditions": ["主角进入旧宅地下层"],
    "planned_method": "行动兑现：钥匙卡入机关",
    "defer_reason": null
  },
  "reinforcements": [],
  "actual_payoff": null,
  "dependencies": [],
  "history": [],
  "last_updated_chapter": 3,
  "updated_at": "ISO-8601"
}
```

状态仅使用 `planned`、`planted`、`reinforced`、`due`、`deferred`、`recovered`、`cancelled`。`context.nearby_chapters` 保存埋设章前后章节的摘要、正文路径和摘要文件路径，不复制整章正文。

完全回收时，`actual_payoff` 必须记录章节、方式、原文证据、解决了什么当前问题以及造成的状态变化。延期时必须更新窗口、`defer_reason` 和下一次强化位置。

## 新会话续写上下文

- `.webnovel/continuation_inventory.json`：扫描器生成的全书文件和摘要覆盖清单。
- `.webnovel/continuation_context.md`：代理读完全书结构、全部章节摘要、动态状态和最近正文后生成的本会话恢复文件。

`continuation_context.md` 必须包含扫描时间、摘要覆盖率、部卷结构压缩图、已写剧情概览、当前人物与时间状态、伏笔紧迫度、最近因果链、下一章任务和发现的冲突。每次新会话重新生成，不能永久替代原始记忆文件。

## 写后记忆

每章正文完成后更新：

- `chapter_summaries`：发生了什么、状态变化、未解问题、下一章承接点。
- `character_states`：人物位置、身体、知识、关系、资源和当前目标。
- `timeline`：时间推进与并行事件。
- `foreshadowing`：新增、强化、部分回收、完全回收、延期、回收窗口和前后章节上下文。
- `project_memory`：用户确认的文风偏好、禁忌和已验证写法。

摘要记录事实，不写评价；上层大纲只有在方向改变时才更新。

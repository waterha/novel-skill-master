# novel-init - 小说项目初始化

## 目标

收集足以开始总纲讨论的基础信息，建立状态与目录协议。初始化不替用户决定故事过程，也不生成空白部纲、卷纲或章纲。

## 必问信息

分轮询问，每轮 1-3 个问题：

- 暂定书名、类型、目标读者和预期体量。
- 主角的起始处境、核心欲望、主要缺陷和失败代价。
- 核心冲突、主要对手或阻力来源。
- 用户希望读者获得的核心体验。
- 结局倾向：主角最终得到什么、失去什么，世界或关系变成什么状态。
- 计划部数、划部依据和每部大致卷数；未知时提供可调整估算。
- 用户明确要求保留或排除的设定、情节和文风。

## 充分性闸门

只有以下内容均得到用户确认后才初始化：

- 题材与核心体验。
- 主角、核心欲望和主要阻力。
- 全书终点至少有方向性答案。
- 部数与每部卷数可形成部卷映射。
- 用户确认基础摘要；未确认项已明确标为后续决策，而非暗中补全。

## 初始化

执行状态和结构清单初始化：

```text
python tools/master_state.py init --name <书名> --parts <部数> --volumes-per-part <如 12,10,8>
python tools/outline_guard.py init --project-root <项目根> --parts <部数> --volumes-per-part <如 12,10,8>
python tools/foreshadowing_tracker.py init --project-root <项目根>
```

然后创建已有实质内容的基础文件，例如设定摘要和创作约定。尚未讨论的正式结构文件不创建；需要保留草案时写入 `.webnovel/drafts/`。

## 基础产出

```text
.webnovel/
  master_state.json
  outline_manifest.json
  project_memory.json
.story-system/
  MASTER_SETTING.json
  foreshadowing.json
设定/
  核心设定.md
  主要人物.md
```

下一步必须进入 `novel-book-outline`，由用户参与确定全书总纲和全部部方向。

## 恢复

用户中途停止时保存已确认答案和未决问题。恢复后先读取这些文件，从第一个未决问题继续，不能重新询问已确认内容。

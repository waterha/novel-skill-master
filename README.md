# Novel Skill Master

Novel Skill Master 是一套面向长篇小说的分层规划、正文创作、伏笔管理、跨会话续写和收尾系统。

它不把整本小说塞进一份容易截断的大纲，而是把创作记忆拆成可检查、可回读、可持续更新的文件：

```text
全书总纲
  └─ 部纲
      └─ 卷纲
          └─ 卷章节索引
              └─ 单章章纲
                  └─ 正文
                      ├─ 章节事实摘要
                      ├─ 人物与时间线状态
                      └─ 伏笔账本
```

正文是系统的中心。规划文件提供方向，动态记忆维持连续性，结构校验器阻止代理在大纲残缺或上下文没有恢复时贸然续写。

## 解决的问题

- 一本小说分成多部后，第二部、第三部只有标题，没有实际内容。
- 一次生成几十卷或几百章时，后半段因输出长度被省略，却被误判为规划完成。
- 新会话没有上一轮聊天记忆，只读最后一章就续写，导致人物、时间线和主线错位。
- 写作过程中埋下伏笔，却没有记录原因、原文位置和回收时间。
- 伏笔该回收时被忘记，或者还没到时间就被机械揭示。
- 写完一卷、一部或全书后，没有结算承诺、人物状态和遗留问题。

## 核心原则

1. 先询问用户，再确定重大方向。
2. 严格按“总纲 → 部纲 → 卷纲 → 章纲 → 正文”逐层展开。
3. 用户确认一个结构后立即写入对应文件，聊天内容不能替代项目记忆。
4. 先生成完整方向索引，再分批深化；只有标题、占位符或省略内容不算完成。
5. 每次写章前按全书、部、卷、章、动态状态的顺序回读。
6. 每次写章后更新章节摘要、人物、时间线、伏笔和项目进度。
7. 新会话续写前必须扫描全书结构并读取全部章节摘要。
8. 没有到期伏笔时不强行处理；到期或逾期时必须明确回收或延期。

## 完整工作流

```text
选题与设定
  → 初始化项目和部卷映射
  → 确认全书终点与全部部方向
  → 确认每一部的全部卷方向
  → 深化当前卷卷纲与剧情单元
  → 生成当前卷完整章节索引
  → 分批生成独立章纲
  → 写前结构检查与伏笔到期检查
  → 正文创作
  → 写后摘要、状态和伏笔更新
  → 单章审查
  → 卷末 / 部末 / 全书收尾
```

全书所有部和卷必须先有用户确认的方向。详细卷纲和章纲可以按当前创作进度逐层深化。

## 主要能力

### 分层大纲

- 全书总纲一次覆盖所有部，不允许后续部为空。
- 每部有独立部纲，并列全本部所有卷方向。
- 每卷有独立卷纲，区分 `direction-confirmed` 和 `detailed-confirmed`。
- 每卷先生成完整章节索引，再按 5-10 章一批生成独立章纲。
- 部、卷、章均使用全书连续编号，进入新部时不重置。

`tools/outline_guard.py` 会检查真实文件、结构状态、必填标题、内容长度和占位符。目录存在不等于规划完成。

### 正文写作

写章前依次读取：

1. 全书总纲和主设定。
2. 当前部纲。
3. 当前卷纲与剧情单元。
4. 卷章节索引、当前章纲、上一章正文和摘要。
5. 人物状态、时间线、伏笔账本和项目偏好。
6. 新会话中的 `continuation_context.md`。

正文完成后写入章节事实摘要，并同步人物位置、知识、关系、资源、时间线、伏笔和下一章承接点。

### 伏笔追踪与回收

统一账本为：

```text
.story-system/foreshadowing.json
```

每条伏笔记录：

- 伏笔 ID、类型和作用范围。
- 为什么留下该伏笔。
- 埋设的部、卷、章、场景和原文证据。
- 读者初读时会如何理解，以及计划中的真实含义。
- 埋设章前后各两章的内容摘要和正文路径。
- 最早、目标和最迟回收位置。
- 回收触发条件和计划方式。
- 强化、延期、部分回收和完全回收历史。

写章前，工具将伏笔划分为：

| 分类 | 处理方式 |
|------|----------|
| `not_due` | 本章不处理 |
| `available` | 仅在自然服务本章时强化或回收 |
| `due_soon` | 检查未来三章并安排位置 |
| `due` | 本章必须决定回收、部分回收或延期 |
| `overdue` | 阻断正常写作，先处理或由用户确认延期 |
| `conditional` | 根据触发条件判断当前是否生效 |

正文写完后先检测候选句，再由代理结合大纲和语义确认。信号词不能自动把某条伏笔标记为已埋设或已回收。

### 新会话续写

用户在新会话中说“续写”“继续写”或“接着上次写”时，系统先进入恢复流程。

恢复流程会：

1. 扫描总纲、全部部纲、全部卷纲和已写卷章节索引。
2. 枚举所有正文，检查缺号和重复章号。
3. 按顺序读取全部章节事实摘要。
4. 摘要缺失或无有效内容时，回读对应正文并补写摘要。
5. 核对状态文件章号与实际最大正文章号。
6. 读取人物、时间线、项目记忆、收尾文件和伏笔紧迫度。
7. 深读最近 3 章；跨卷、跨部、高潮或视角变化时读取最近 5 章。
8. 检查下一章独立章纲和后续两章方向。
9. 生成 `.webnovel/continuation_context.md`。

只有摘要覆盖率达到 100%、动态记忆齐全、当前位置一致且下一章章纲存在，才能继续正文。

### 分层收尾

- 卷末：结算本卷目标、人物阶段变化、卷级伏笔和下一卷交接。
- 部末：结算不可逆变化、全部卷结果、跨部伏笔和下一部起点。
- 全书：核对核心冲突、开篇承诺、人物弧、主要谜题和全部关键伏笔。

项目只有在全书收尾报告获得用户确认后才标记完成。

## 安装

将整个目录放入支持 `SKILL.md` 的 skills 目录。

Codex 默认位置：

```text
%CODEX_HOME%/skills/novel-skill-master
```

Claude Code 常用位置：

```text
~/.claude/skills/novel-skill-master
```

运行环境需要 Python 3.8 或更高版本。核心状态、结构、伏笔和续写工具不依赖第三方 Python 包。

## 快速开始

### 创建新小说

在对话中说：

```text
我要写一本长篇小说。先询问我必要信息，然后从全书总纲开始规划。
```

代理会先确认题材、主角、核心冲突、结局方向、部数和每部卷数，然后初始化状态、部卷映射和伏笔账本。

对应工具命令：

```text
python tools/master_state.py init --name "书名" --parts 3 --volumes-per-part 12,12,8
python tools/outline_guard.py init --project-root <项目目录> --parts 3 --volumes-per-part 12,12,8
python tools/foreshadowing_tracker.py init --project-root <项目目录>
```

初始化只建立状态和映射，不会生成空白部纲或卷纲。

### 日常写下一章

在对话中说：

```text
根据现有项目文件写下一章，写前检查结构和伏笔，写后更新所有记忆。
```

写章前检查：

```text
python tools/outline_guard.py preflight --project-root <项目目录> --part 1 --volume 1 --chapter 18
python tools/foreshadowing_tracker.py due --project-root <项目目录> --part 1 --volume 1 --chapter 18
```

写章后检查：

```text
python tools/foreshadowing_tracker.py detect --chapter-file <正文路径>
python tools/foreshadowing_tracker.py refresh-context --project-root <项目目录> --chapter 18 --window 2
python tools/foreshadowing_tracker.py validate --project-root <项目目录>
```

### 在新会话续写

在对话中说：

```text
这是一个新会话。请先扫描整本小说的结构和已写内容，恢复记忆后再续写下一章。
```

扫描命令：

```text
python tools/continuation_scanner.py scan --project-root <项目目录> --write-inventory
python tools/outline_guard.py status --project-root <项目目录>
```

扫描结果写入：

```text
.webnovel/continuation_inventory.json
```

代理完成全书浏览后生成：

```text
.webnovel/continuation_context.md
```

### 查询伏笔

在对话中说：

```text
检查目前所有伏笔，告诉我哪些已经到期、哪些即将到期，以及适合怎样回收。
```

工具命令：

```text
python tools/foreshadowing_tracker.py status --project-root <项目目录>
python tools/foreshadowing_tracker.py due --project-root <项目目录> --part 1 --volume 2 --chapter 22
```

## 项目文件结构

```text
小说项目/
├─ 大纲/
│  ├─ 00-总纲/
│  │  └─ 全书总纲.md
│  ├─ 01-部纲/
│  │  ├─ 第01部-部纲.md
│  │  └─ 第02部-部纲.md
│  ├─ 02-卷纲/
│  │  └─ 第01部/
│  │     ├─ 第001卷-卷纲.md
│  │     └─ 第002卷-卷纲.md
│  └─ 03-章纲/
│     └─ 第01部/
│        └─ 第001卷/
│           ├─ 卷章节索引.md
│           └─ 第0001章-章纲.md
├─ 正文/
│  └─ 第01部/
│     └─ 第001卷/
│        └─ 第0001章-章名.md
├─ 收尾/
│  ├─ 卷/第001卷-收尾.md
│  ├─ 部/第01部-收尾.md
│  └─ 全书收尾.md
├─ .webnovel/
│  ├─ master_state.json
│  ├─ outline_manifest.json
│  ├─ project_memory.json
│  ├─ continuation_inventory.json
│  └─ continuation_context.md
└─ .story-system/
   ├─ MASTER_SETTING.json
   ├─ character_states.json
   ├─ timeline.json
   ├─ foreshadowing.json
   └─ chapter_summaries/
      └─ 第0001章.json
```

详细字段、固定标题和状态标记见 [小说项目分层文件协议](references/guides/novel-project-schema.md)。

## 结构状态

正式结构文件首行带有机器可读标记：

```text
<!-- novel-structure: book; status: confirmed -->
<!-- novel-structure: part; part: 1; status: confirmed -->
<!-- novel-structure: volume; part: 1; volume: 1; status: direction-confirmed -->
<!-- novel-structure: volume; part: 1; volume: 1; status: detailed-confirmed -->
<!-- novel-structure: chapter-index; part: 1; volume: 1; status: confirmed -->
<!-- novel-structure: chapter; part: 1; volume: 1; chapter: 1; status: confirmed -->
```

- `direction-confirmed`：卷的大方向已确认。
- `detailed-confirmed`：卷的事件链、人物弧、伏笔、高潮和交接已确认，可以开始拆章。

正文写作要求目标卷为 `detailed-confirmed`，卷章节索引和当前独立章纲均为 `confirmed`。

## 核心命令

### 状态与结构

| 命令 | 作用 |
|------|------|
| `python tools/master_state.py status` | 查看部、卷、章和收尾进度 |
| `python tools/master_state.py next-step` | 计算下一步流程 |
| `python tools/outline_guard.py status --project-root <路径>` | 检查全书总纲、全部部纲和全部卷方向 |
| `python tools/outline_guard.py preflight ...` | 检查指定章节的完整写前记忆栈 |
| `python tools/project_doctor.py check --deep --project-root <路径>` | 检查项目文件、设定和动态记忆 |

### 伏笔

| 命令 | 作用 |
|------|------|
| `python tools/foreshadowing_tracker.py init ...` | 初始化统一伏笔账本 |
| `python tools/foreshadowing_tracker.py validate ...` | 校验字段、状态和回收窗口 |
| `python tools/foreshadowing_tracker.py status ...` | 查看全部伏笔状态 |
| `python tools/foreshadowing_tracker.py due ...` | 计算当前章需要处理的伏笔 |
| `python tools/foreshadowing_tracker.py detect ...` | 检测本章可能的埋设或回收候选句 |
| `python tools/foreshadowing_tracker.py upsert ...` | 语义确认后写入或更新条目 |
| `python tools/foreshadowing_tracker.py refresh-context ...` | 刷新埋设章前后章节摘要与路径 |

### 续写

| 命令 | 作用 |
|------|------|
| `python tools/continuation_scanner.py scan ... --write-inventory` | 扫描全书结构、正文和摘要覆盖率 |
| `python tools/plot_rag_retriever.py build ...` | 构建历史正文检索索引 |
| `python tools/plot_rag_retriever.py query ...` | 按当前剧情检索相关历史章节 |

RAG 只负责按需查找相关历史片段，不能替代新会话中的全书结构和全部摘要恢复。

## 模块索引

| 模块 | 文件 | 作用 |
|------|------|------|
| 总控 | [SKILL.md](SKILL.md) | 路由完整小说工作流 |
| 项目初始化 | [novel-init.md](skills_part/04-项目初始化/novel-init.md) | 收集基础信息并初始化状态 |
| 总纲与部纲 | [novel-book-outline.md](skills_part/05-卷纲规划/novel-book-outline.md) | 规划全书和全部部方向 |
| 卷纲 | [novel-plan.md](skills_part/05-卷纲规划/novel-plan.md) | 深化当前卷事件链 |
| 剧情单元 | [novel-arc.md](skills_part/06-剧情单元/novel-arc.md) | 把卷纲拆成剧情单元 |
| 分章大纲 | [novel-chapter-outline.md](skills_part/07-分章大纲/novel-chapter-outline.md) | 生成全卷索引和独立章纲 |
| 正文写作 | [novel-write.md](skills_part/08-写章引擎/novel-write.md) | 写章和更新动态记忆 |
| 伏笔管理 | [novel-foreshadowing.md](skills_part/08-写章引擎/novel-foreshadowing.md) | 追踪埋设、窗口和回收 |
| 新会话续写 | [novel-continue.md](skills_part/08-写章引擎/novel-continue.md) | 恢复全书结构和已写内容 |
| 质量审查 | [novel-review.md](skills_part/09-质量审查/novel-review.md) | 审查设定、因果、节奏和伏笔 |
| 分层收尾 | [novel-finish.md](skills_part/10-收尾管理/novel-finish.md) | 处理卷末、部末和全书完结 |
| 项目体检 | [novel-doctor.md](skills_part/11-项目体检/novel-doctor.md) | 诊断文件和状态完整性 |

## 写作闸门

以下情况会阻止正式写章：

- 全书总纲或任一部纲缺失。
- 任一卷方向文件缺失，后续部只有标题或占位内容。
- 当前卷未达到 `detailed-confirmed`。
- 当前卷章节索引或当前章独立章纲缺失。
- 伏笔账本格式无效。
- 存在逾期伏笔但没有回收或延期决定。
- 新会话尚未读完全书结构和全部章节摘要。
- 章节摘要覆盖率不足 100%。
- 状态文件章号与实际最大正文章号不一致。
- 下一章独立章纲不存在。
- 存在重复章号、正文缺号或其他阻断项。

## 旧项目接入

旧项目通常缺少部卷映射、独立部纲、统一伏笔账本或章节事实摘要。接入时按以下顺序处理：

1. 根据现有正文和大纲确认部数、每部卷数及全书连续编号。
2. 初始化或修正 `outline_manifest.json`。
3. 补齐全书总纲、全部部纲和全部卷方向文件。
4. 初始化 `foreshadowing.json`，从大纲和已写正文整理仍然有效的伏笔。
5. 运行续写扫描器，找出缺失摘要、章号缺口和状态冲突。
6. 分批回读正文，为所有已写章节补齐事实摘要。
7. 生成 `continuation_context.md` 后再继续写作。

系统不会自动猜测旧项目的部卷划分，也不会把信号词自动认定为伏笔。涉及故事方向的迁移决策仍由用户确认。

## 验证

仓库包含分层工作流回归测试：

```text
python -m unittest tools.test_hierarchical_workflow -v
```

测试覆盖：

- 后续部缺失时阻断写作。
- 部末先收尾，再进入下一部。
- 新目录层级下的正文统计。
- 伏笔到期、逾期和前后章节上下文刷新。
- 新会话续写的摘要覆盖率与恢复闸门。

运行时数据会写入小说项目自己的 `设定/`、`大纲/`、`正文/`、`收尾/`、`.webnovel/` 和 `.story-system/`，不会写入 skill 源码目录。

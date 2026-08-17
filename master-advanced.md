# 写作、检查与收尾命令

## 写章

`master write <chapter>` 执行以下流程：

1. 根据清单确定章号所属部和卷。
2. 运行 `outline_guard.py preflight`。
3. 运行 `foreshadowing_tracker.py due`，处理到期、条件触发和逾期项。
4. 按全书、部、卷、章、动态状态读取记忆。
5. 生成简短任务卡并写完整正文。
6. 检查因果、人物知识、时间、资源、伏笔和章末承接。
7. 落盘正文，检测伏笔变化并更新全部写后记忆。

默认一次写一章。批量写作也要逐章执行“回读 → 写作 → 更新”，不能先生成多章再统一更新状态。

## 审查

`master review <range>` 先查故事结构，再查语言。审查结果必须给出原文证据和影响层级：

- 章级问题：直接修改当前章。
- 卷级问题：检查卷纲和相邻章纲。
- 部级或全书级问题：先询问用户，不直接改总纲。

审查不能以统一文风为名抹平人物声音，也不能为了章末钩子破坏本章应有的情绪落点。

## 结构检查

```text
python tools/outline_guard.py status --project-root <项目根>
python tools/outline_guard.py preflight --project-root <项目根> --part N --volume N --chapter N
python tools/project_doctor.py check --deep --project-root <项目根>
```

第一个检查全书所有部和卷方向是否齐全；第二个检查当前写章记忆栈；第三个检查设定、动态数据和工具状态。

## 边界收尾

`master finish --level volume --volume N`：生成卷收尾，结算本卷承诺、人物状态和跨卷交接。

`master finish --level part --part N`：汇总本部全部卷收尾，结算不可逆变化并核对下一部起点。

`master finish --level book`：核对开篇承诺、核心冲突、人物弧和伏笔，生成全书收尾报告；用户确认后才把项目标记完成。

具体规则读取 `skills_part/10-收尾管理/novel-finish.md`。

## 恢复

新会话续写执行 `skills_part/08-写章引擎/novel-continue.md`。先运行：

```text
python tools/continuation_scanner.py scan --project-root <项目根> --write-inventory
```

然后按清单浏览全部部卷结构和所有章节摘要。摘要覆盖率不足时，回读缺失正文并补齐摘要，不直接写下一章。恢复完成后生成 `.webnovel/continuation_context.md`。

普通会话中断恢复则先读：

1. `master_state.json` 与 `outline_manifest.json`。
2. `outline_guard.py status` 的缺失项。
3. 最近一个已确认结构文件或最近正文及其章节摘要。

从最小未完成项继续。不得根据聊天上下文猜测已完成范围，也不得重新生成已确认文件。

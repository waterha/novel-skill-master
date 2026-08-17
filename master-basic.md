# 总控基础命令

## 新项目

先通过对话取得项目名、部数和每部卷数。用户确认结构后执行：

```text
python tools/master_state.py init --name <书名> --parts <部数> --volumes-per-part <12,10,8>
python tools/outline_guard.py init --project-root <项目根> --parts <部数> --volumes-per-part <12,10,8>
python tools/foreshadowing_tracker.py init --project-root <项目根>
```

初始化只建立状态和部卷映射，不创建空白大纲。正式文件必须由用户确认的内容生成。

已有项目缺少部卷映射时执行：

```text
python tools/master_state.py configure --parts <部数> --volumes-per-part <12,10,8>
```

已有进度时重新配置需要 `--force`，并在执行前说明受影响的部卷文件。

## 状态命令

```text
python tools/master_state.py status
python tools/master_state.py next-step
python tools/outline_guard.py status --project-root <项目根>
```

`master_state.py` 负责流程进度；`outline_guard.py` 负责验证真实文件。两者冲突时，以真实文件校验失败为准，修复文件后再更新状态。

## 完成命令

```text
python tools/master_state.py done --stage book_outline
python tools/master_state.py done --stage part_outline --part 1
python tools/master_state.py done --stage plan --volume 1
python tools/master_state.py done --stage arc --volume 1
python tools/master_state.py done --stage chapter_outline --volume 1
```

调用 `done` 前必须先验证对应文件。`part_outline` 完成意味着该部的所有卷方向文件都已生成并确认；`chapter_outline` 完成意味着该卷完整章节索引已确认，不代表每一章正文已经完成。

## 推进顺序

```text
选题 → 设定 → 初始化
  → 全书总纲和全部部方向
  → 逐部完成全部卷方向
  → 当前卷详纲与剧情单元
  → 当前卷完整章节索引
  → 当前章详纲
  → 正文与单章审查
  → 卷末/部末/全书收尾
```

`next-step` 只提出下一项；代理仍须读取对应文件和用户已确认内容。不得把命令输出当作创作方向。

## 回退

`back --to <stage>` 只回退状态，不删除文件。需要修改方向时：

1. 找出被修改层级。
2. 列出受影响的下游部、卷、章和正文。
3. 取得用户确认。
4. 更新文件及其状态标记。
5. 重新运行结构校验。

不得自动删除正文或已确认大纲。

## 决策与阻断

对会改变故事方向的问题写入 `pending_decisions`；文件缺失、层级冲突、时间线矛盾和设定硬冲突写入 `blockers`。处理时一次展示一个问题，并说明它影响哪些文件。

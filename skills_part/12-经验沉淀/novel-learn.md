# 🧠 novel-learn — 写作经验提取与沉淀

## 概述
从当前会话提取可复用的写作模式并保存到项目记忆。这是系统的学习闭环——每次写作中发现的成功模式都会被记录，供后续参考。

## 所属阶段
第十三阶段：经验沉淀

## 输入
- 用户经验描述（自然语言）
- 最近写章/审查会话的上下文

## 工作流

### Step 1：触发条件
- 用户主动输入经验描述（如"本章的危机钩子设计很有效"）
- 或写章/审查过程中的亮点自动捕获

### Step 2：模式分类
自动归类 pattern_type：

| 类型 | 代码 | 示例 |
|------|------|------|
| 钩子设计 | `hook` | "第 N 章用倒计时钩子效果很好" |
| 节奏控制 | `pacing` | "战斗和文戏 3:1 比例读者反馈好" |
| 对话技巧 | `dialogue` | "用方言词塑造角色性格成功" |
| 爽点兑现 | `payoff` | "铺垫了 20 章的伏笔回收效果炸裂" |
| 情绪渲染 | `emotion` | "配角死亡场景的留白手法有效" |
| 格式技巧 | `format` | "短段落密集输出增强了紧张感" |
| 其他 | `other` | 无法归类的经验 |

### Step 3：去重存储
- 调用脚本追加到 `.webnovel/project_memory.json`
- 禁止直接 Write（通过脚本确保格式合法性）
- 自动去重：相同的 `pattern_type` + `description` 跳过

### Step 4：跨项目迁移（可选）
- 用户确认后，可迁移到全局库 `~/.webnovel/global_memory.json`
- 跨项目引用时可检索

## 数据格式
```json
{
  "patterns": [
    {
      "id": "pat-001",
      "pattern_type": "hook",
      "description": "用时间倒计时营造紧迫感. 在章节开头设置一个明确的时间限制",
      "source_chapter": "1-15",
      "effectiveness": 9,
      "tags": ["紧张感", "倒计时", "钩子"],
      "created_at": "2026-06-06T12:00:00"
    }
  ]
}
```

## 成功标准
- ✅ project_memory.json 存在且格式合法
- ✅ 新 pattern 已追加到 patterns 数组
- ✅ 输出包含 `status: success` 和完整 `learned` 对象

## 故障恢复
| 问题 | 处理方式 |
|------|---------|
| project_memory.json 不存在 | 自动初始化 `{"patterns": []}` 后继续 |
| JSON 解析失败 | 不写脏数据，告知用户文件损坏 |
| master_state.json 缺失 | 使用 `source_chapter: null`，不阻断 |
| 无法归类 | 使用 `pattern_type: "other"`，不阻断 |

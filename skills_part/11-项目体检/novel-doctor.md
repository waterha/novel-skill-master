# 🩺 novel-doctor — 项目健康诊断

## 概述
运行只读项目体检，确认项目在所处阶段应具备的完整性。不会写入任何文件或修改任何配置。

## 所属阶段
第十二阶段：项目体检

## 输入
- 项目根路径
- 检查清单

## 检查范围

> 💡 **自动化**：以下所有检查（目录/文件、JSON 校验、SQLite、依赖）由 `tools/project_doctor.py check [--deep] --project-root <路径>` 执行，
> Claude 直接调用脚本获取 JSON 结果后格式化展示。详见脚本注释。

### 1. 目录/文件完整性
| 检查项 | 预期状态 | 缺失影响 |
|--------|---------|---------|
| .webnovel/master_state.json | 必须存在 | 项目无法定位 |
| .webnovel/outline_manifest.json | 必须存在 | 无法核对部卷范围 |
| .story-system/foreshadowing.json | 必须存在 | 无法追踪伏笔回收 |
| 设定/ 目录 | 必须存在 | 核心设定丢失 |
| 大纲/00-总纲/全书总纲.md | 应存在（总纲确认后） | 无法确定全书方向 |
| 大纲/01-部纲/ | 应覆盖全部部 | 后续部可能为空 |
| 大纲/02-卷纲/ | 应覆盖全部卷方向 | 无法确定卷级方向 |
| 大纲/03-章纲/ | 写章前目标章必须存在 | 无法执行当前章节 |
| 正文/ 目录 | 应存在（write 后） | 无正文 |
| .story-system/ 目录 | 必须存在 | Story System 不可用 |

### 2. JSON / SQLite 数据完整性
- master_state.json 与 outline_manifest.json 格式校验
- foreshadowing.json 账本字段、状态和回收窗口校验
- index.db 表结构校验
- MASTER_SETTING.json 合同树校验
- **★ MASTER_SETTING.json 设定契约完整性校验（检查力量等级/角色/规则是否有缺失字段）**

### 3. RAG 配置
- reference_search.py 可调用
- CSV 检索文件存在
- 嵌入模型可加载

### 4. Python 依赖
- Flask（dashboard 需要）
- 各脚本 import 测试

### 5. Dashboard 构建产物
- dist/ 目录存在
- index.html 可访问

## 命令变体

| 命令 | 说明 |
|------|------|
| `project-status --format summary` | 短状态（phase, target_chapter, blocker） |
| `doctor --format text` | 标准体检 |
| `doctor --chapter N --format text` | 指定章节体检 |
| `doctor --deep --format text` | 深度体检（全量检查） |

## 输出格式
```
┌─ 项目体检报告 ─────────────────────────────────┐
│ 当前阶段：[phase name]                          │
│ 目标章节：第 [N] 章                             │
│ 阻断项：[有/无]                                 │
│ ★ 设定契约状态：[已生成/缺失/格式错误]           │
├─────────────────────────────────────────────────┤
│ 缺失路径：                                      │
│   ⚠ 设定/角色库.md (影响：角色查询不可用)       │
│   ⚠ 大纲/02-卷纲/第01部/第001卷-卷纲.md         │
│      (影响：卷规划缺失)                          │
├─────────────────────────────────────────────────┤
│ ★ 设定契约问题：                                 │
│   ⚠ MASTER_SETTING.json 中 power_system.levels  │
│     缺少 limits 字段（影响：无法自动验证力量等级） │
├─────────────────────────────────────────────────┤
│ 修复建议：                                      │
│   1. 运行 novel-settings 重新生成角色库          │
│   2. 运行 novel-plan 生成卷纲                 │
│   3. 补充 MASTER_SETTING.json 的 limits 字段    │
└─────────────────────────────────────────────────┘
```

## 设计原则
- ✅ 只读诊断，不写入项目文件
- ❌ 不自动修复
- ❌ 不安装依赖
- ❌ 不启动 Dashboard
- ❌ 不展示或要求用户粘贴 API key

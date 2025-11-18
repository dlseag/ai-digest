# Phase 2.1: 工具调用框架集成 - 使用指南

## ✅ 已实现功能

### 1. 工具定义 (`src/agents/tools.py`)

**3 个核心工具**:

1. **`GitHubIssueTool`** - 创建 GitHub Issue
   - ✅ 支持创建 Issue（标题、正文、标签）
   - ✅ 模拟模式（无 token 时）
   - ✅ 实际 API 调用（有 token 时）

2. **`CalendarInviteTool`** - 发送日历邀请
   - ✅ 支持会议邀请（参与者、标题、时间、时长）
   - ✅ 模拟模式（无 API 配置时）
   - ✅ 时间格式验证

3. **`ReadingListTool`** - 添加到阅读列表
   - ✅ 本地 JSON 存储
   - ✅ 优先级支持（high/medium/low）
   - ✅ 去重检查
   - ✅ 预留 Obsidian/Notion 集成接口

### 2. 工具执行器 (`src/agents/tool_executor.py`)

**`ToolExecutor` 类**:
- ✅ 统一工具调用接口
- ✅ 批量执行支持
- ✅ 错误处理和日志记录

### 3. 行动建议 Agent (`src/agents/action_agent.py`)

**`ActionAgent` 类**:
- ✅ 基于 LLM 生成行动建议
- ✅ Function Calling 集成
- ✅ 自动工具调用决策
- ✅ 执行结果整合

### 4. 集成到报告生成流程

**集成点**: `src/main.py` 的 `_generate_action_items()` 方法
- ✅ 可选启用 ActionAgent
- ✅ 自动降级到传统方法
- ✅ 工具配置加载

## 🚀 快速开始

### 步骤 1: 配置环境变量（可选）

```bash
# GitHub 配置（可选）
export GITHUB_TOKEN="your_github_token"
export GITHUB_DEFAULT_REPO="owner/repo"

# 日历配置（可选）
export CALENDAR_EMAIL="your@email.com"

# 阅读列表配置（可选）
export READING_LIST_INTEGRATION="local"  # 或 "obsidian", "notion"
```

### 步骤 2: 生成报告（自动使用工具）

```bash
cd /Users/david/Documents/ai-workflow/ai-digest

# 生成报告（ActionAgent 会自动启用）
python src/main.py --days-back 1

# 查看日志确认工具调用
# 应该看到: "🤖 使用 ActionAgent 生成智能行动建议..."
```

### 步骤 3: 查看执行结果

**模拟模式**（无 API 配置）:
- GitHub Issue → 保存到 `data/simulated_issues/`
- 日历邀请 → 保存到 `data/simulated_invites/`
- 阅读列表 → 保存到 `data/reading_list.json`

**实际模式**（有 API 配置）:
- GitHub Issue → 实际创建到仓库
- 日历邀请 → 发送到参与者邮箱
- 阅读列表 → 保存到指定位置

## 📊 工具 Schema（Function Calling）

### create_github_issue

```json
{
  "name": "create_github_issue",
  "description": "创建 GitHub Issue",
  "parameters": {
    "repo": "string (owner/repo)",
    "title": "string (必需)",
    "body": "string",
    "labels": ["string"]
  }
}
```

### send_calendar_invite

```json
{
  "name": "send_calendar_invite",
  "description": "发送日历邀请",
  "parameters": {
    "attendees": ["string"] (必需),
    "title": "string (必需)",
    "start_time": "string (ISO格式, 必需)",
    "duration_minutes": "integer (默认30)",
    "description": "string"
  }
}
```

### add_to_reading_list

```json
{
  "name": "add_to_reading_list",
  "description": "添加到阅读列表",
  "parameters": {
    "url": "string (必需)",
    "title": "string",
    "priority": "high|medium|low (默认medium)",
    "notes": "string"
  }
}
```

## 🔧 配置选项

### 禁用 ActionAgent

在 `src/main.py` 中调用时设置 `use_agent=False`:

```python
action_items = self._generate_action_items(processed_items, use_agent=False)
```

### 自定义工具配置

修改 `_load_tool_config()` 方法或通过环境变量配置。

## 📈 衡量标准实现

### ✅ 可操作性率 (Actionability Rate)

**定义**: `可操作性率 = 用户点击 [执行] 的次数 / 推送的行动建议数`

**当前实现**:
- ActionAgent 自动执行部分操作（如添加到阅读列表）
- 需要确认的操作标记为 `executed: false`
- 通过 HTML 报告中的按钮追踪用户点击

**目标**: 可操作性率 > 30%

## 🐛 故障排查

### 问题 1: ActionAgent 未启用

**症状**: 日志中没有"🤖 使用 ActionAgent..."

**可能原因**:
1. LLM API 调用失败
2. 工具配置错误

**解决方案**:
```bash
# 检查日志
python src/main.py --days-back 1 2>&1 | grep -i "actionagent\|工具"

# 检查环境变量
echo $OPENAI_API_KEY
```

### 问题 2: 工具执行失败

**症状**: 工具返回 `success: false`

**可能原因**:
1. 缺少必需参数
2. API 配置错误
3. 网络问题

**解决方案**:
- 查看日志中的错误信息
- 检查工具配置
- 验证 API 凭证

### 问题 3: 模拟模式未保存文件

**症状**: 执行成功但找不到文件

**可能原因**:
- 文件权限问题
- 目录不存在

**解决方案**:
```bash
# 检查目录
ls -la data/simulated_issues/
ls -la data/simulated_invites/
ls -la data/reading_list.json

# 创建目录
mkdir -p data/simulated_issues data/simulated_invites
```

## 🔮 未来优化方向

### 1. 更多工具集成

- [ ] Jira API 集成
- [ ] Slack/Teams API 集成
- [ ] Notion API 集成
- [ ] Obsidian 文件系统操作

### 2. 智能执行决策

**当前**: LLM 决定是否调用工具
**未来**: 基于用户历史行为学习最佳执行时机

### 3. 用户确认流程

**当前**: 部分操作自动执行
**未来**: 所有操作都需要用户确认（通过 HTML 报告）

## 📝 测试覆盖

**测试文件**: `tests/test_tools.py`

**测试数量**: 18 个测试用例

**覆盖范围**:
- ✅ GitHub Issue 工具（4 个测试）
- ✅ 日历邀请工具（4 个测试）
- ✅ 阅读列表工具（4 个测试）
- ✅ 工具执行器（5 个测试）
- ✅ 工具 Schema（1 个测试）

**运行测试**:
```bash
python -m pytest tests/test_tools.py -v
```

## ✨ 完成状态

### Phase 2.1: 工具调用框架集成 ✅

- ✅ 3 个核心工具实现
- ✅ 工具执行器
- ✅ ActionAgent 集成
- ✅ 报告生成流程集成
- ✅ 测试覆盖（18 个测试）
- ✅ 使用文档

**估计时间**: 3-4 天 → **实际时间**: 完成

---

_创建时间: 2025-11-12_
_负责人: AI Assistant_
_状态: ✅ 已完成_


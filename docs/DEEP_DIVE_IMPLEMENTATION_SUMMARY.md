# 即时深度研究功能实施总结

## 实施日期
2025-11-14

## 功能概述

将原有的异步队列深度研究模式改为**即时同步研究**，用户点击"✨ 想看更多"按钮后，立即在页面内弹窗中看到研究结果，无需等待后台 worker 处理。

## 2025-11-15 增量更新

- **非阻塞布局**：`report_template.html.jinja` 新增 `.page-layout`，主内容与右侧「深度研究队列」贴合排列，去除中间空白，让研究进度面板始终可见（并可折叠）。
- **后台任务面板**：右侧面板内实时显示排队/运行/失败/完成状态；弹窗只在结果可用或需要提示错误时出现，用户可继续浏览简报。
- **统一报告目录**：`tracking_server.py` 现在强制把研究报告写入 `research-assistant/reports`（即 `/Users/david/Documents/ai-workflow/research-assistant/reports`），方便自动归档再同步至 Notion。

## 2025-11-19 报告目录统一

- **统一输出目录**：所有深度研究报告现在统一保存到 `/Users/david/Documents/ai-workflow/output/deep_dive_reports/`
- **修改文件**：
  - `tracking_server.py`: `_run_research_assistant()` 和 `_save_deep_dive_report()` 方法
  - `research-assistant/main.py`: 默认 `--report-dir` 参数
- **历史迁移**：使用 `scripts/migrate_deep_dive_reports.py` 迁移了 26 个历史报告
- **目录说明**：添加了 `output/deep_dive_reports/README.md` 文档

## 核心改动

### 1. 后端：tracking_server.py

**文件路径**: `ai-workflow/ai-digest/src/tracking/tracking_server.py`

**主要变更**:
- 修改 `_handle_track()` 方法，检测到 `feedback_type == "more"` 时同步调用深度研究
- 新增 `_handle_deep_dive_request()` 方法：
  - 提取 URL 和标题
  - 调用 `_run_research_assistant()`
  - 返回研究结果或错误信息
- 新增 `_run_research_assistant()` 方法：
  - 使用 `subprocess.run()` 调用 `research-assistant/main.py`
  - 设置 120 秒超时
  - 解析 JSON 输出
  - 处理各种错误场景（超时、403、404、网络错误等）

**关键代码**:
```python
def _handle_deep_dive_request(self, data: dict) -> dict:
    """同步处理深度研究请求，返回研究结果"""
    # 提取 URL 和标题
    item_url = data.get("url") or metadata.get("item_url")
    item_title = metadata.get("item_title", "Unknown")
    
    # 调用 research-assistant
    result = self._run_research_assistant(item_url, item_title)
    return {
        "status": "success",
        "markdown": result["markdown"],
        "report_path": result["report_path"]
    }
```

### 2. 研究助手：research-assistant/main.py

**文件路径**: `ai-workflow/research-assistant/main.py`

**主要变更**:
- 新增 `--json-output` 命令行选项
- 当启用 `--json-output` 时，输出 JSON 格式到 stdout：
  ```json
  {
    "markdown": "完整的研究报告内容...",
    "report_path": "/path/to/report.md"
  }
  ```

**关键代码**:
```python
if json_output:
    import json as json_module
    result = {
        "markdown": markdown,
        "report_path": str(output_path)
    }
    click.echo(json_module.dumps(result, ensure_ascii=False))
```

### 3. 前端：report_template.html.jinja

**文件路径**: `ai-workflow/ai-digest/templates/report_template.html.jinja`

**主要变更**:

#### 3.1 添加 Markdown 渲染库
```html
<head>
    <script src="https://cdn.jsdelivr.net/npm/marked/marked.min.js"></script>
</head>
```

#### 3.2 添加模态框 HTML
```html
<div id="deep-dive-modal">
    <div class="modal-content-wrapper">
        <button id="close-modal">&times;</button>
        <div id="modal-content">
            <div class="loading-spinner">正在深度研究中</div>
        </div>
    </div>
</div>
```

#### 3.3 添加模态框样式
- 全屏半透明背景
- 居中白色内容区域
- 加载动画
- 错误消息样式
- Markdown 内容渲染样式

#### 3.4 修改"想看更多"按钮事件处理
```javascript
if (action === 'more') {
    // 显示模态框
    modal.style.display = 'block';
    modalContent.innerHTML = '<div class="loading-spinner">正在深度研究中，请稍候（约30-60秒）</div>';
    
    // 发送请求并等待结果
    const response = await fetch(TRACKING_API, {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify(payload)
    });
    
    const result = await response.json();
    
    if (result.deep_dive && result.deep_dive.status === 'success') {
        // 渲染 Markdown
        modalContent.innerHTML = marked.parse(result.deep_dive.markdown);
    } else {
        // 显示错误信息
        modalContent.innerHTML = `<div class="error-message">...</div>`;
    }
}
```

#### 3.5 添加关闭模态框逻辑
- 点击 × 按钮关闭
- 点击背景关闭

### 4. 配置变更：sources.yaml

**文件路径**: `ai-workflow/ai-digest/config/sources.yaml`

**主要变更**:
- 禁用 Twitter 采集器：`twitter.enabled: false`

## 测试覆盖

### 单元测试
**文件路径**: `ai-workflow/ai-digest/tests/test_deep_dive_integration.py`

**测试场景**:
1. ✅ 追踪服务器健康检查
2. ✅ 深度研究请求数据格式验证
3. ✅ 无效 URL 处理
4. ✅ Reddit URL（403 Forbidden）处理
5. ✅ 缺少 URL 处理
6. ✅ 普通反馈不触发深度研究
7. ✅ 报告保存验证
8. ✅ research-assistant JSON 输出格式验证

### 端到端测试
**测试文档**: `ai-workflow/ai-digest/docs/DEEP_DIVE_TESTING.md`

**测试步骤**:
1. 启动服务：`./scripts/manage_services.sh start`
2. 打开简报：`open output/weekly_report_2025-11-14.html`
3. 点击"✨ 想看更多"按钮
4. 验证弹窗显示和研究结果

## 关键技术决策

### 1. 同步 vs 异步
**选择**: 同步处理
**理由**:
- 个人使用场景，并发需求低
- 用户体验更直观（立即看到结果）
- 简化架构，无需管理 worker 进程和任务队列
- 120 秒超时足够处理大部分文章

### 2. 模态框 vs 新页面
**选择**: 模态框
**理由**:
- 不打断用户浏览流程
- 可以快速关闭并继续浏览
- 支持滚动查看长内容
- 视觉效果更现代

### 3. Markdown 渲染
**选择**: marked.js CDN
**理由**:
- 轻量级（~20KB）
- 无需构建步骤
- 支持所有标准 Markdown 语法
- 广泛使用，稳定可靠

### 4. 错误处理策略
**实施**:
- 区分不同错误类型（超时、403、404、网络错误）
- 提供用户友好的错误消息
- 记录详细日志以便调试
- 优雅降级，不影响其他功能

## 性能指标

| 指标 | 数值 |
|------|------|
| 平均研究时间 | 30-60 秒 |
| 超时限制 | 120 秒 |
| 并发处理 | 串行（个人使用可接受） |
| 报告大小 | 5-15KB Markdown |
| 模态框加载时间 | <100ms |

## 用户体验流程

```
用户点击"想看更多"
    ↓
任务加入右侧研究队列面板，页面不中断
    ↓
后台调用 research-assistant（30-60秒）
    ↓
成功：渲染完整研究报告并在弹窗中查看
失败：面板+弹窗展示错误，可重试/关闭
    ↓
用户阅读报告或关闭弹窗
    ↓
报告自动保存到 research-assistant/reports/
```

## 与旧系统的对比

| 特性 | 旧系统（异步队列） | 新系统（即时同步） |
|------|-------------------|-------------------|
| 响应时间 | 需要等待 worker 轮询 | 立即响应 |
| 用户体验 | 需要刷新页面或查看文件 | 弹窗内直接显示 |
| 架构复杂度 | 需要 SQLite 队列 + worker | 仅需 tracking server |
| 并发处理 | 支持批量处理 | 串行处理 |
| 可靠性 | 依赖 worker 进程 | 直接调用，更可靠 |
| 适用场景 | 多用户、高并发 | 个人使用、低并发 |

## 保留的旧系统组件

以下组件保留但不再使用，可用于未来扩展：
- `deep_dive_task_queue.py` - SQLite 任务队列
- `deep_dive_dispatcher.py` - 任务分发器
- `manage_deep_dive_tasks.py` - 任务管理 CLI
- `deep-dive-worker` launchd 服务

## 后续优化建议

### 短期（1-2周）
1. **缓存机制**: 对已研究过的 URL 进行缓存，避免重复研究
2. **历史记录**: 在简报中显示"已研究"标记，可快速查看历史报告
3. **进度显示**: 显示"正在抓取文章..."、"正在分析趋势..."等阶段提示

### 中期（1-2月）
1. **流式输出**: research-assistant 支持流式输出，实时显示研究进度
2. **取消功能**: 允许用户取消正在进行的研究
3. **批量研究**: 支持一次性研究多篇文章

### 长期（3-6月）
1. **智能预加载**: 基于用户行为预测可能点击的文章，提前研究
2. **研究深度选择**: 提供"快速概览"和"深度分析"两种模式
3. **多模态支持**: 支持视频、图片等多媒体内容的研究

## 相关文档

- 测试指南: `docs/DEEP_DIVE_TESTING.md`
- 集成测试: `tests/test_deep_dive_integration.py`
- 实施计划: `ai-1.plan.md`

## 实施人员
Claude (Sonnet 4.5)

## 审核状态
✅ 所有 TODO 已完成
✅ 单元测试通过
✅ 端到端测试通过
✅ 服务已重启并运行


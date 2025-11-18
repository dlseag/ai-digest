# 即时深度研究功能测试指南

## 功能概述

用户点击简报中的"✨ 想看更多"按钮后，系统会：
1. 立即显示模态框和加载状态
2. 同步调用 research-assistant 进行深度研究（30-60秒）
3. 在弹窗中展示完整的研究报告（Markdown 渲染）
4. 报告同时保存到 `output/deep_dive_reports/` 目录

## 测试步骤

### 1. 启动服务

```bash
cd /Users/david/Documents/ai-workflow/ai-digest
./scripts/manage_services.sh start
```

### 2. 打开简报

```bash
open output/weekly_report_2025-11-14.html
```

### 3. 测试成功场景

1. 找到任意一篇文章（必看内容或论文精选）
2. 点击"✨ 想看更多"按钮
3. **预期结果**：
   - 立即弹出模态框，显示"正在深度研究中，请稍候（约30-60秒）"
   - 30-60秒后，弹窗内容更新为完整的研究报告
   - 报告包含：核心观点、技术细节、趋势分析、实践建议等
   - 可以滚动查看完整内容
   - 点击右上角 ×  或点击背景可关闭弹窗

### 4. 测试失败场景

#### 场景 A：无效 URL
- 修改 HTML 中某个 item 的 `data-item-url` 为 `https://invalid-url-123456.com`
- 点击"想看更多"
- **预期结果**：显示"研究失败：无法访问来源（页面不存在或被禁止访问）"

#### 场景 B：Reddit 链接（403 Forbidden）
- 使用 Reddit 链接（如 `https://www.reddit.com/r/LocalLLaMA/...`）
- 点击"想看更多"
- **预期结果**：显示"研究失败：无法访问来源（页面不存在或被禁止访问）"

#### 场景 C：追踪服务器未运行
- 停止服务：`./scripts/manage_services.sh stop`
- 点击"想看更多"
- **预期结果**：显示"请求失败：无法连接到研究服务，请检查追踪服务器是否运行"

#### 场景 D：超时（模拟）
- 修改 `tracking_server.py` 中的 `timeout=120` 为 `timeout=5`
- 使用一个内容较多的文章
- **预期结果**：显示"研究失败：研究超时，请稍后重试"

## 验证报告保存

```bash
ls -lh /Users/david/Documents/ai-workflow/ai-digest/output/deep_dive_reports/
```

应该看到新生成的 Markdown 文件，格式为 `YYYY-MM-DD-{title-slug}.md`

## 查看日志

### Tracking Server 日志
```bash
tail -f ~/Library/Logs/ai-digest-tracking-server.log
```

应该看到：
```
🔬 开始深度研究: LlamaFactory: Unified Efficient Fine-Tuning...
执行命令: /usr/local/bin/python3 /Users/david/Documents/ai-workflow/research-assistant/main.py...
✅ 研究完成: LlamaFactory: Unified Efficient Fine-Tuning
```

### Research Assistant 输出
在 tracking server 日志中会看到 research-assistant 的完整输出，包括：
- 文章抓取
- 趋势分析
- Demo 生成
- 报告合成

## 常见问题

### Q: 点击按钮后没有反应
**A**: 检查浏览器控制台（F12），查看是否有 JavaScript 错误

### Q: 显示"未找到JSON输出"
**A**: research-assistant 可能没有正确输出 JSON，检查 tracking server 日志

### Q: 研究时间过长（>2分钟）
**A**: 可能是文章内容过多或 LLM API 响应慢，可以调整 `timeout` 参数

### Q: 模态框样式错乱
**A**: 确保 `marked.js` CDN 已加载，检查浏览器网络请求

## 性能指标

- **平均研究时间**：30-60秒
- **超时限制**：120秒
- **并发限制**：串行处理（个人使用场景可接受）
- **报告大小**：通常 5-15KB Markdown

## 后续优化建议

1. **缓存机制**：对已研究过的 URL 进行缓存，避免重复研究
2. **进度显示**：显示当前研究进度（需要 research-assistant 支持流式输出）
3. **取消功能**：允许用户取消正在进行的研究
4. **批量研究**：支持一次性研究多篇文章
5. **历史记录**：在简报中显示"已研究"标记，可快速查看历史报告


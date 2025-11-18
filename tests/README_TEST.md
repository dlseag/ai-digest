# 简报质量测试文档

## 概述

`test_report_quality.py` 是一个全面的简报质量测试脚本，用于验证生成的HTML简报的质量和正确性。

## 测试内容

### 1. 📐 版面完整性测试
检查简报是否包含所有必要的板块和元素：
- ✅ 今日头条板块
- ✅ 深度（论文）板块
- ✅ 页面标题
- ✅ 主容器
- ✅ 内容卡片

### 2. 🔍 数据一致性测试
验证 Title 和 Summary 是否匹配：
- 提取 title 中的关键词
- 检查关键词是否出现在 summary 中
- 匹配率低于 20% 会发出警告

**常见问题：**
- Hacker News 讨论的摘要可能只有"热门讨论：X分，Y条评论"
- Hugging Face Papers 的摘要可能只有"Author/Org: . Likes: X"
- 这些是原始数据的问题，不是处理错误

### 3. 🔗 URL有效性测试
验证所有链接的格式和有效性：
- 检查 URL 格式是否正确
- 验证域名是否有效
- 识别常见的可信域名

**支持的域名：**
- arxiv.org, huggingface.co, paperswithcode.com
- github.com, techcrunch.com, venturebeat.com
- theverge.com, news.ycombinator.com, blog.google
- openai.com, anthropic.com, simonwillison.net

### 4. 📝 内容质量测试
检查摘要的质量：
- 摘要是否为空
- 摘要长度是否过短（< 20字）
- 摘要是否为占位符（"..."）

### 5. 🏷️ 分类正确性测试
验证内容是否在正确的板块：
- 论文不应出现在今日头条
- 新闻不应出现在论文板块

### 6. 📋 元数据完整性测试
检查每个条目的元数据是否完整：
- data-item-id
- data-item-title
- data-item-url
- data-item-source
- data-item-category

## 使用方法

### 基本用法

```bash
cd /Users/david/Documents/ai-workflow/ai-digest
python tests/test_report_quality.py
```

### 指定文件

```bash
python tests/test_report_quality.py \
  --html output/weekly_report_2025-11-17.html \
  --json output/collected_items_2025-11-17_163447.json
```

### 参数说明

- `--html`: HTML报告路径（默认：`output/weekly_report_2025-11-17.html`）
- `--json`: 原始JSON数据路径（可选）

## 输出说明

### 测试结果

每个测试会显示：
- ✅ 通过：测试成功
- ❌ 失败：发现严重错误
- ⚠️ 警告：发现潜在问题

### 统计信息

```
统计信息:
  总条目数: 12
  今日头条: 6 条
  论文: 6 篇
  空摘要: 0 条
  无效URL: 0 条
  数据不一致: 2 条
```

### 退出码

- `0`: 所有测试通过，无错误
- `1`: 发现错误或测试失败

## 常见警告及处理

### 1. 数据一致性警告

**问题：** "条目 X 数据一致性可疑"

**原因：**
- Hacker News 的摘要可能只包含讨论统计
- Hugging Face Papers 的摘要可能只包含点赞数
- 这是原始数据的限制，不是bug

**处理：**
- 如果是 Hacker News/Hugging Face Papers，可以忽略
- 如果是其他来源，需要检查 AI 处理逻辑

### 2. 摘要过短警告

**问题：** "条目 X 摘要过短"

**原因：**
- 某些来源（如 Hacker News）只提供简短的元数据
- AI 可能没有生成详细摘要

**处理：**
- 检查原始数据是否包含完整内容
- 考虑改进 AI prompt，要求生成更详细的摘要

### 3. 未知域名警告

**问题：** "条目 X 使用未知域名"

**原因：**
- 链接来自不在白名单中的域名

**处理：**
- 验证域名是否可信
- 如果是常用域名，添加到 `valid_domains` 列表

## 集成到CI/CD

### GitHub Actions 示例

```yaml
name: Report Quality Test

on:
  push:
    paths:
      - 'output/weekly_report_*.html'

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - name: Set up Python
        uses: actions/setup-python@v2
        with:
          python-version: '3.9'
      - name: Install dependencies
        run: |
          pip install beautifulsoup4
      - name: Run tests
        run: |
          python tests/test_report_quality.py
```

### Pre-commit Hook

在 `.git/hooks/pre-commit` 中添加：

```bash
#!/bin/bash
python tests/test_report_quality.py
if [ $? -ne 0 ]; then
    echo "❌ 简报质量测试失败，请修复后再提交"
    exit 1
fi
```

## 扩展测试

### 添加新的测试

在 `ReportQualityTester` 类中添加新方法：

```python
def test_custom_check(self) -> bool:
    """自定义测试"""
    print("\n" + "=" * 80)
    print("🔧 测试X: 自定义检查")
    print("=" * 80)
    
    passed = True
    # 实现测试逻辑
    
    return passed
```

然后在 `run_all_tests()` 中调用：

```python
results = {
    # ... 现有测试 ...
    '自定义检查': self.test_custom_check()
}
```

### 添加新的域名白名单

在 `test_url_validity()` 方法中的 `valid_domains` 列表添加：

```python
valid_domains = [
    # ... 现有域名 ...
    'your-domain.com',
    'another-domain.org'
]
```

## 故障排查

### 问题：找不到板块

**错误：** "缺少今日头条板块" 或 "缺少深度板块"

**解决：**
1. 检查 HTML 模板是否正确
2. 确认板块标题包含正确的 emoji 和文字
3. 运行 `grep "今日头条\|深度" output/weekly_report_*.html`

### 问题：所有条目都显示数据不一致

**错误：** 大量 "数据一致性可疑" 警告

**解决：**
1. 检查 AI 处理是否正常工作
2. 查看原始 JSON 数据的 summary 字段
3. 考虑调整一致性检查的阈值（当前 20%）

### 问题：测试脚本无法运行

**错误：** `ModuleNotFoundError: No module named 'bs4'`

**解决：**
```bash
pip install beautifulsoup4
```

## 最佳实践

1. **每次生成简报后运行测试**
   ```bash
   python -m src.main && python tests/test_report_quality.py
   ```

2. **定期审查警告**
   - 不要忽略所有警告
   - 某些警告可能指示真实问题

3. **更新白名单**
   - 发现新的可信域名时，添加到白名单
   - 保持白名单的准确性

4. **记录测试结果**
   ```bash
   python tests/test_report_quality.py > test_results.log 2>&1
   ```

5. **对比历史结果**
   - 跟踪警告数量的变化
   - 识别质量下降的趋势

## 相关文件

- `tests/test_report_quality.py` - 测试脚本
- `src/processors/ai_processor_batch.py` - AI 处理逻辑
- `src/generators/report_generator.py` - 报告生成逻辑
- `templates/report_template.html.jinja` - HTML 模板

## 更新日志

### 2025-11-17
- ✅ 创建初始版本
- ✅ 实现6个核心测试
- ✅ 添加详细的错误和警告报告
- ✅ 支持命令行参数

## 反馈与改进

如果发现测试脚本的问题或有改进建议，请：
1. 记录具体的测试场景
2. 提供失败的示例数据
3. 说明期望的行为

---

**维护者**: AI Digest Team  
**最后更新**: 2025-11-17


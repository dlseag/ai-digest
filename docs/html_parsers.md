# HTML 解析器使用指南

## 概述

RSS Collector 现在支持灵活的 HTML 解析系统，可以处理没有 RSS feed 的网站。

## 功能特性

- ✅ **自动解析器选择**：根据源名称和 URL 自动选择合适的解析器
- ✅ **多种解析策略**：通用解析器尝试多种选择器策略
- ✅ **降级方案**：RSS 解析失败时自动尝试 HTML 解析
- ✅ **可扩展性**：易于添加新的专用解析器

## 解析器类型

### 1. GenericArticleParser（通用解析器）

**用途**：默认解析器，适用于大多数网站

**策略**：
- 尝试 `<article>` 标签
- 尝试 `div[class*="article"]`
- 尝试 `div[class*="post"]`
- 尝试 `div[class*="entry"]`
- 尝试 `li[class*="article"]`
- 尝试 `div[class*="card"]`

**使用场景**：没有专用解析器的网站

### 2. AnthropicBlogParser（Anthropic 专用）

**用途**：专门解析 Anthropic 博客

**特点**：
- 针对 Anthropic 网站结构优化
- 自动处理相对链接

### 3. MistralBlogParser（Mistral 专用）

**用途**：专门解析 Mistral AI 博客

## 使用方法

### 方法 1：自动选择（推荐）

在 `sources.yaml` 中配置源，系统会自动选择合适的解析器：

```yaml
- name: Anthropic News
  url: https://www.anthropic.com/news
  category: official_blog
  priority: 10
  enabled: true
  # 不需要指定 html_parser，系统会自动选择
```

### 方法 2：手动指定解析器

如果需要强制使用特定解析器：

```yaml
- name: Custom Blog
  url: https://example.com/blog
  category: official_blog
  priority: 10
  html_parser: generic  # 指定使用通用解析器
  enabled: true
```

### 方法 3：RSS 失败时自动降级

如果 RSS feed 无效或无法访问，系统会自动尝试 HTML 解析：

```yaml
- name: Blog with Broken RSS
  url: https://example.com/feed.xml  # RSS feed 可能失效
  category: official_blog
  priority: 10
  enabled: true
  # 如果 RSS 解析失败，会自动尝试 HTML 解析
```

## 添加新的解析器

### 步骤 1：创建解析器类

```python
# src/collectors/html_parsers.py

class MyCustomParser(HTMLParser):
    """自定义解析器"""
    
    def parse(self, soup: BeautifulSoup, base_url: str) -> List[Dict]:
        """解析逻辑"""
        articles = []
        # 实现解析逻辑
        return articles
```

### 步骤 2：注册解析器

```python
# 在 ParserRegistry._register_default_parsers() 中添加
self.register('my_custom', MyCustomParser())
```

### 步骤 3：使用解析器

```yaml
- name: My Custom Blog
  url: https://example.com/blog
  html_parser: my_custom  # 使用自定义解析器
  enabled: true
```

## 配置示例

### Anthropic 博客（无 RSS）

```yaml
- name: Anthropic News
  url: https://www.anthropic.com/news
  category: official_blog
  priority: 10
  enabled: true
  # 系统会自动识别并使用 AnthropicBlogParser
```

### Mistral AI 博客

```yaml
- name: Mistral AI News
  url: https://mistral.ai/news/
  category: official_blog
  priority: 10
  enabled: true
  # 系统会自动识别并使用 MistralBlogParser
```

### 通用网站（自动降级）

```yaml
- name: Generic Blog
  url: https://example.com/blog
  category: official_blog
  priority: 8
  enabled: true
  # 如果 URL 中没有 rss/feed/atom，会自动使用 HTML 解析
  # 如果 RSS 解析失败，也会自动降级到 HTML 解析
```

## 调试

### 启用调试日志

```python
import logging
logging.getLogger('src.collectors.html_parsers').setLevel(logging.DEBUG)
logging.getLogger('src.collectors.rss_collector').setLevel(logging.DEBUG)
```

### 查看解析器选择

日志会显示：
```
DEBUG: 为 Anthropic News 使用解析器: anthropic
DEBUG: 使用选择器 'article' 找到 5 个元素
```

## 故障排查

### 问题：解析器未找到文章

**可能原因**：
1. 网站结构发生变化
2. 选择器不匹配
3. 网站需要 JavaScript 渲染

**解决方案**：
1. 检查网站 HTML 结构
2. 添加自定义解析器
3. 使用浏览器开发者工具查看实际 HTML

### 问题：解析器选择错误

**解决方案**：
在配置中明确指定解析器类型：
```yaml
html_parser: generic  # 强制使用通用解析器
```

## 最佳实践

1. **优先使用 RSS**：如果网站提供 RSS feed，优先使用 RSS
2. **自动选择**：让系统自动选择解析器，除非有特殊需求
3. **添加专用解析器**：对于重要源，考虑添加专用解析器以提高准确性
4. **监控日志**：定期检查日志，确保解析正常工作

---

**更新日期**: 2025-11-12


# 重试机制和健康检查使用指南

## 概述

数据采集器现在支持自动重试和健康检查机制，提高了数据采集的鲁棒性和可靠性。

## 功能特性

- ✅ **指数退避重试**：自动重试失败的请求，延迟时间递增
- ✅ **健康状态追踪**：记录每个数据源的成功/失败历史
- ✅ **自动跳过不健康源**：连续失败 5 次后自动跳过
- ✅ **持久化健康状态**：健康状态保存到 JSON 文件
- ✅ **详细错误记录**：记录错误类型、状态码、错误消息

## 重试机制

### RetryHandler

`RetryHandler` 实现了指数退避重试策略：

```python
from src.collectors.retry_handler import RetryHandler

# 创建重试处理器
handler = RetryHandler(
    max_retries=3,        # 最大重试次数
    base_delay=1.0,      # 基础延迟（秒）
    max_delay=60.0,      # 最大延迟（秒）
    backoff_factor=2.0,  # 退避因子
    retry_on_status=(429, 500, 502, 503, 504)  # 需要重试的状态码
)

# 使用重试机制执行函数
def fetch_data():
    response = session.get(url, timeout=15)
    response.raise_for_status()
    return response

result, error = handler.retry_with_backoff(fetch_data)
if error:
    # 处理错误
    pass
```

### 重试策略

- **第 1 次尝试**：立即执行
- **第 2 次尝试**：延迟 1 秒（base_delay）
- **第 3 次尝试**：延迟 2 秒（base_delay * backoff_factor）
- **第 4 次尝试**：延迟 4 秒（base_delay * backoff_factor^2）

最大延迟不超过 `max_delay`（默认 60 秒）。

### 自动重试的场景

- **HTTP 状态码**：429 (Too Many Requests), 500, 502, 503, 504
- **网络错误**：Timeout, ConnectionError
- **不重试的场景**：404 (Not Found), 403 (Forbidden) 等客户端错误

## 健康检查机制

### SourceHealthTracker

`SourceHealthTracker` 追踪每个数据源的健康状态：

```python
from src.collectors.retry_handler import SourceHealthTracker

# 创建健康追踪器
tracker = SourceHealthTracker()

# 记录成功
tracker.record_success('Source Name', 'https://example.com/feed')

# 记录失败
tracker.record_failure(
    'Source Name',
    'https://example.com/feed',
    error_type='HTTPError',
    error_message='404 Not Found',
    status_code=404
)

# 检查是否健康
if tracker.is_healthy('Source Name', 'https://example.com/feed'):
    # 采集数据
    pass

# 获取健康摘要
summary = tracker.get_health_summary()
# {
#     'total': 10,
#     'healthy': 8,
#     'degraded': 1,
#     'unhealthy': 1
# }

# 获取不健康源列表
unhealthy = tracker.get_unhealthy_sources()
```

### 健康状态分类

- **healthy**：正常状态，连续失败 < 3 次
- **degraded**：降级状态，连续失败 3-4 次
- **unhealthy**：不健康状态，连续失败 ≥ 5 次（自动跳过）

### 健康状态持久化

健康状态保存在 `data/source_health.json`：

```json
{
  "Source Name|https://example.com/feed": {
    "success_count": 10,
    "failure_count": 2,
    "last_success": "2025-11-12T10:00:00",
    "last_failure": "2025-11-11T15:30:00",
    "consecutive_failures": 0,
    "status": "healthy",
    "last_error_type": "HTTPError",
    "last_error_message": "404 Not Found",
    "last_status_code": 404
  }
}
```

## 集成到采集器

### RSSCollector

`RSSCollector` 已集成重试和健康检查：

```python
from src.collectors.rss_collector import RSSCollector

collector = RSSCollector(sources_config)
items = collector.collect_all(days_back=7)

# 自动行为：
# 1. 检查每个源的健康状态
# 2. 跳过不健康的源
# 3. 使用重试机制获取 RSS feed
# 4. 记录成功/失败
# 5. 输出健康状态摘要
```

### NewsCollector

`NewsCollector` 也已集成：

```python
from src.collectors.news_collector import NewsCollector

collector = NewsCollector(news_configs)
news = collector.collect_all(days_back=7)
```

## 日志输出示例

### 正常采集

```
✓ 采集 LangChain Blog: 5 条目
✓ 采集 Hacker News: 20 条目
⚠ HTML 解析未找到文章 Anthropic News
总共采集 25 条RSS条目 (跳过 0 个不健康源)
```

### 有错误的情况

```
✗ Eugene Yan: 404 Not Found (可能已失效)
✗ Lilian Weng: HTTP 500 - Internal Server Error
✗ Network Source: 网络错误 (Timeout) - Connection timeout
总共采集 20 条RSS条目 (跳过 2 个不健康源)
⚠ 有 1 个数据源标记为不健康
```

### 跳过不健康源

```
⏭ 跳过不健康的数据源: Broken Source (连续失败 5 次)
✓ 采集 Healthy Source: 10 条目
总共采集 10 条RSS条目 (跳过 1 个不健康源)
```

## 配置建议

### 重试参数

根据数据源的特点调整重试参数：

```python
# 对于不稳定的源，增加重试次数
handler = RetryHandler(max_retries=5, base_delay=2.0)

# 对于稳定的源，减少重试次数
handler = RetryHandler(max_retries=2, base_delay=0.5)
```

### 健康检查阈值

默认连续失败 5 次后标记为不健康。可以通过修改 `SourceHealthTracker` 的 `is_healthy` 方法调整：

```python
# 在 retry_handler.py 中修改
if consecutive_failures >= 5:  # 改为 3 或 7
    return False
```

## 故障排查

### 问题：源一直失败但未被标记为不健康

**原因**：可能是错误类型未被正确捕获

**解决**：检查错误处理逻辑，确保所有异常都被正确记录

### 问题：健康状态未持久化

**原因**：`data/` 目录不存在或没有写权限

**解决**：确保 `data/` 目录存在且有写权限

### 问题：重试次数过多导致采集缓慢

**原因**：某些源响应慢，重试延迟累积

**解决**：调整 `max_retries` 和 `base_delay`，或降低不健康源的优先级

## 最佳实践

1. **定期检查健康状态**：查看 `data/source_health.json`，了解数据源的健康情况
2. **手动重置不健康源**：如果源已恢复，可以删除 JSON 文件中的对应条目或手动重置 `consecutive_failures`
3. **监控日志**：关注警告和错误日志，及时发现数据源问题
4. **调整优先级**：对于频繁失败的源，考虑降低优先级或暂时禁用

---

**更新日期**: 2025-11-12


# AI Digest 测试文档

## 测试覆盖范围

### 1. 报告生成器测试 (`tests/test_report_generator.py`)

#### 1.1 必看内容筛选逻辑
- **arXiv论文数量限制**: 确保"必看内容"中arXiv论文不超过2条
- **来源多样性**: 确保"必看内容"包含至少2个不同来源
- **优先级阈值**: 确保只有≥8分的条目被选中
- **来源名称标准化**: 测试 `_normalize_source()` 方法

#### 1.2 去重逻辑
- **URL去重**: 相同URL的条目只保留一条
- **标题去重**: 当URL为空时，相同标题的条目只保留一条

### 2. 采集器去重测试 (`tests/test_collectors_dedupe.py`)

覆盖场景：
- RSS / HackerNews / Market Insights / ProductHunt 采集器在聚合多个源时的 URL 规范化与去重逻辑
- `unique_items` 辅助函数的行为（配合 `tests/test_utils_dedupe.py`）

示例：
```bash
python -m pytest tests/test_collectors_dedupe.py -v
```

### 3. 如何运行测试

#### 运行所有测试
```bash
cd /Users/david/Documents/ai-workflow/ai-digest
python -m pytest tests/ -v
```

#### 运行特定测试文件
```bash
python -m pytest tests/test_report_generator.py -v
```

#### 运行特定测试类
```bash
python -m pytest tests/test_report_generator.py::TestMustReadSelection -v
```

#### 运行特定测试方法
```bash
python -m pytest tests/test_report_generator.py::TestMustReadSelection::test_arxiv_limit -v
```

### 4. 测试数据

测试使用 Mock 对象模拟处理后的条目，包括：
- 5个arXiv论文（高优先级）
- 2个Reddit帖子（高优先级）
- 1个Simon Willison博客（高优先级）
- 1个Hacker News讨论（高优先级）

### 5. 测试原则

1. **行为一致性**: 升级后必须保证核心逻辑不变
2. **边界条件**: 测试极端情况（如全部来自同一来源）
3. **回归保护**: 防止修改引入新bug

### 6. 待补充的测试

- [ ] AI处理器测试
- [ ] 数据采集器测试
- [ ] LangGraph工作流测试
- [ ] 学习引擎测试
- [ ] 去重逻辑的完整测试

## 超时保护机制

### 1. 主流程超时保护

在 `src/main.py` 中添加了主流程超时保护：

```bash
# 使用默认超时（10分钟）
python src/main.py --days-back 1

# 自定义超时时间（例如20分钟）
python src/main.py --days-back 1 --timeout 1200
```

### 2. 数据源采集超时保护

- **单个源超时**: 15秒（在 `RSSCollector.collect_all()` 中设置）
- **HTTP请求超时**: 连接5秒，读取8秒
- **重试策略**: 最多重试1次，延迟1秒

### 3. 超时保护层级

1. **HTTP请求层**: `requests` 超时（5s连接 + 8s读取）
2. **单个源采集层**: 15秒（`RSSCollector` 中的 `timeout_context`）
3. **主流程层**: 600秒默认（可通过 `--timeout` 参数调整）

## 故障排查

### 如果测试失败

1. 检查 `src/generators/report_generator.py` 中的筛选逻辑是否被修改
2. 检查 `_normalize_source()` 方法是否正确标准化来源名称
3. 检查 `_make_dedupe_key()` 方法是否正确生成去重键

### 如果执行超时

1. 查看日志中最后处理的数据源
2. 检查网络连接
3. 使用 `--timeout` 参数增加超时时间
4. 检查 `data/source_health.json` 中的不健康源并禁用它们

## 持续改进

每次修改核心逻辑后，应：
1. 运行所有测试确保行为一致
2. 如果引入新逻辑，添加相应测试
3. 更新本文档记录测试覆盖范围


# 修复记录：来源多样性问题 (2025-11-12)

## 问题描述

用户报告 `weekly_report_2025-11-12.html` 中 arXiv 论文占比过高（约 90%），来源单一。

## 问题诊断

### 统计数据

实际统计显示：
- **本周头条**：17 条内容
  - arXiv (论文): **10 条 (58.8%)** ⚠️
  - Sequoia AI: 3 条 (17.6%)
  - Papers with Code: 2 条 (11.8%)
  - Reddit r/LocalLLaMA: 1 条 (5.9%)
  - Hacker News: 1 条 (5.9%)

虽然不是 "90%"，但 **58.8%** 的 arXiv 占比确实严重失衡。

### 根本原因

分析 `src/generators/report_generator.py` 的 `_select_top_headlines` 方法，发现**两个关键BUG**：

#### Bug 1: 第三步补充逻辑缺失来源限制

```python
# 第三步：补充其他内容
for item in remaining:
    if len(unique_headlines) >= top_count:
        break
    dedupe_key = self._make_dedupe_key(item)
    if dedupe_key not in dedupe_pool:
        unique_headlines.append(item)  # ⚠️ 没有检查 seen_sources！
        dedupe_pool.add(dedupe_key)
```

**第一步和第二步**遵守 `self.headline_source_limit = 2` 的限制，但**第三步完全忽略了来源多样性检查**。

当 `top_count = 10` 时，如果前两步只选了 2-3 条，第三步就会无限制地补充 arXiv 论文（因为它们评分高）。

#### Bug 2: 来源识别方法不一致

代码使用简单的字符串切分：
```python
source_key = item.source.split()[0].split('(')[0]  
# "arXiv cs.CL" → "arXiv" ✓
# "arXiv cs.AI" → "arXiv" ✓
```

但这种方法不够健壮，应该使用已有的 `_normalize_source` 方法来统一识别。

## 修复方案

### 修复 1: 统一来源识别逻辑

**第一步、第二步、第三步**都改用 `_normalize_source` 方法：

```python
# 旧代码
source_key = item.source.split()[0].split('(')[0]

# 新代码
source_key = self._normalize_source(item.source)
```

`_normalize_source` 方法会统一处理：
- `arXiv cs.CL` → `arxiv`
- `arXiv cs.AI` → `arxiv`
- `Reddit r/LocalLLaMA` → `reddit`
- `Hacker News` → `hacker_news`

### 修复 2: 第三步添加来源多样性检查

```python
# 第三步：补充其他内容（新增来源多样性检查）
for item in remaining:
    if len(unique_headlines) >= top_count:
        break
    
    # 🔧 新增：检查来源多样性
    source_key = self._normalize_source(item.source)
    if seen_sources.get(source_key, 0) >= self.headline_source_limit:
        logger.debug(f"⏭ 跳过来源 {source_key}：已达上限 ({self.headline_source_limit}条)")
        continue
    
    dedupe_key = self._make_dedupe_key(item)
    if dedupe_key not in dedupe_pool:
        unique_headlines.append(item)
        dedupe_pool.add(dedupe_key)
        seen_sources[source_key] = seen_sources.get(source_key, 0) + 1  # 🔧 新增：更新计数
```

### 修复 3: 增强日志记录

添加来源分布统计和警告：

```python
# 记录详细筛选信息
source_dist = {}
for item in unique_headlines:
    source_key = self._normalize_source(item.source)
    source_dist[source_key] = source_dist.get(source_key, 0) + 1

logger.info(f"  来源分布: {source_dist}")

# 警告：如果arXiv占比过高
arxiv_count = source_dist.get('arxiv', 0)
if arxiv_count > len(unique_headlines) * 0.4:  # 超过40%
    logger.warning(f"⚠️  arXiv论文占比过高: {arxiv_count}/{len(unique_headlines)} = {arxiv_count/len(unique_headlines)*100:.1f}%")
```

## 预期效果

修复后，`_select_top_headlines` 方法将：

1. **强制执行来源多样性限制**：每个来源最多 2 条 (`headline_source_limit = 2`)
2. **统一来源识别**：`arXiv cs.CL` 和 `arXiv cs.AI` 被识别为同一来源
3. **详细日志记录**：输出来源分布统计，便于调试

预期结果（`top_count = 10`）：
```
来源分布示例：
- arXiv: 2 条 (20%)  ← 从 10 条 (58.8%) 降至 2 条
- Reddit: 2 条 (20%)
- Hacker News: 2 条 (20%)
- Microsoft: 2 条 (20%)
- Sequoia AI: 2 条 (20%)
```

## 测试验证

### 测试步骤
1. 运行报告生成：`python src/main.py --days-back 1`
2. 检查日志中的来源分布统计
3. 验证 arXiv 论文不超过 2 条
4. 验证来源多样性（至少 5 个不同来源）

### 测试用例

| 场景 | 预期结果 |
|------|---------|
| arXiv 高质量论文 > 10 篇 | 只选 2 篇，其余被跳过 |
| 某个来源只有 1 篇内容 | 正常选入，不受限制 |
| 多个来源都有 2+ 篇内容 | 每个来源最多 2 篇，均衡分布 |
| 总内容不足 10 篇 | 不强制凑满，保持质量优先 |

## 后续优化建议

### 短期 (本周)
- [ ] 验证修复效果
- [ ] 调整 `headline_source_limit` 参数（考虑从 2 调整为 3）
- [ ] 测试不同 `days_back` 参数下的表现

### 中期 (下周)
- [ ] 实现动态来源限制（根据总数量自动调整）
- [ ] 添加来源优先级权重（某些来源可以多选）
- [ ] 实现来源质量评分（低质量来源自动降级）

### 长期 (后续迭代)
- [ ] 实现用户反馈驱动的来源权重自动调整
- [ ] 添加来源类型平衡（论文、新闻、博客、项目等）
- [ ] 实现时间窗口内的来源多样性优化

## 相关文件

- `src/generators/report_generator.py` - 主要修复文件
- `src/processors/ai_processor.py` - 评分逻辑（影响来源选择）
- `config/sources.yaml` - 来源配置（优先级设置）

## 修复时间

- **发现时间**: 2025-11-12 23:00
- **修复时间**: 2025-11-12 23:20
- **验证时间**: 待运行测试

## 修复人

- AI Assistant (Claude Sonnet 4.5)

---

**备注**: 这个bug存在时间较长，之前的报告可能也受到影响。修复后需要重新评估历史报告的质量。


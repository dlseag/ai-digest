# Phase 1.3: 相关性重排 (Re-ranking) - 使用指南

## ✅ 已实现功能

### 1. 项目活跃度追踪器 (`src/learning/reranker.py`)

**`ProjectActivityTracker` 类**:
- ✅ 基于用户配置追踪项目活跃度
- ✅ 支持优先级映射（high: 0.9, medium: 0.7, low: 0.5）
- ✅ 缓存机制提升性能
- ✅ 活跃度更新接口（为未来 Git API 集成预留）

**活跃度分数计算**:
```python
# 高优先级项目
activity = 0.9

# 中等优先级项目
activity = 0.7

# 低优先级项目
activity = 0.5

# 未知项目（默认）
activity = 0.5
```

### 2. 内容重排器 (`src/learning/reranker.py`)

**`ContentReranker` 类**:
- ✅ 基于用户画像向量计算相似度
- ✅ 集成项目活跃度分数
- ✅ 应用动态权重（来源权重 × 类别权重）
- ✅ 综合排序算法

**重排算法**:
```
最终分数 = (
    基础分数(归一化) × 0.3 +
    向量相似度 × 0.4 +
    项目活跃度 × 0.3
) × 动态权重
```

**权重系数**:
- 相似度权重: 40%
- 活跃度权重: 30%
- 基础分数权重: 30%

### 3. 集成到报告生成器

**自动重排流程**:
1. 选择"必看内容"（personal_priority >= 8）
2. 应用来源多样性过滤
3. **应用相关性重排** ← Phase 1.3
4. 生成最终报告

## 🚀 快速开始

### 步骤 1: 配置用户画像

确保 `config/user_profile.yaml` 存在并包含项目信息：

```yaml
active_projects:
  - name: "mutation-test-killer"
    priority: "high"
    description: "Mutation testing framework"
  - name: "ai-digest"
    priority: "medium"
    description: "AI news digest system"
  - name: "rag-practics"
    priority: "low"
    description: "RAG practice project"
```

### 步骤 2: 生成报告（自动应用重排）

```bash
cd /Users/david/Documents/ai-workflow/ai-digest

# 生成报告（重排会自动应用）
python src/main.py --days-back 1

# 查看日志确认重排
# 应该看到: "🔄 对 X 条必看内容进行重排..."
# 和: "✓ 重排完成"
```

### 步骤 3: 验证重排效果

打开生成的 HTML 报告，检查"必看内容"顺序：
- 与活跃项目相关的内容应该排在前面
- 与用户目标/项目相关的内容应该优先显示

## 📊 重排因素详解

### 1. 向量相似度 (40% 权重)

**计算方式**:
- 提取内容文本（标题 + 摘要 + 为什么重要）
- 与用户画像向量比较：
  - 目标向量 (goals_embedding) - 30%
  - 项目向量 (projects_embedding) - 40%
  - 隐式兴趣向量 (implicit_interests_embedding) - 30%

**当前实现**: 使用简化版关键词匹配（Jaccard 相似度）
**未来优化**: 集成 SentenceTransformer embedding 模型

### 2. 项目活跃度 (30% 权重)

**计算方式**:
- 从 `related_projects` 字段提取项目名称
- 查询项目活跃度分数（基于用户配置）
- 高优先级项目 → 0.9
- 中等优先级项目 → 0.7
- 低优先级项目 → 0.5

### 3. 基础分数 (30% 权重)

**计算方式**:
- 使用 `relevance_score`（归一化到 0-1）
- 如果未提供，使用默认值 0.5

### 4. 动态权重（乘法因子）

**计算方式**:
- 来源权重 × 类别权重
- 例如: arXiv (1.2) × paper (1.1) = 1.32

## 🔧 配置选项

### 调整权重系数

修改 `src/learning/reranker.py` 中的权重：

```python
class ContentReranker:
    def __init__(self, ...):
        # 权重系数
        self.similarity_weight = 0.4  # 向量相似度权重
        self.activity_weight = 0.3     # 项目活跃度权重
        self.base_score_weight = 0.3   # 基础分数权重
```

### 调整项目活跃度映射

修改 `ProjectActivityTracker.get_project_activity()`:

```python
if project.get("priority") == "high":
    activity = 0.9  # 可调整为 0.95
elif project.get("priority") == "medium":
    activity = 0.7  # 可调整为 0.75
```

## 📈 衡量标准实现

### ✅ 上下文召回率 (Context Recall)

**定义**: `上下文召回率 = 用户认为相关的 / 实际推送的`

**实现方式**:
1. 重排提升相关内容的优先级
2. 用户反馈（👍/👎）记录相关性
3. 通过 `scripts/analyze_reading_behaviors.py` 分析反馈率

**目标**: 上下文召回率 > 85%

## 🐛 故障排查

### 问题 1: 重排未生效

**症状**: 日志中没有"🔄 对 X 条必看内容进行重排..."

**可能原因**:
1. 用户画像文件不存在
2. 重排器初始化失败

**解决方案**:
```bash
# 检查用户画像文件
ls -lh config/user_profile.yaml

# 检查日志
python src/main.py --days-back 1 2>&1 | grep -i "重排\|rerank"
```

### 问题 2: 重排结果不符合预期

**症状**: 活跃项目相关内容未排在前面

**可能原因**:
1. 项目名称不匹配（大小写、拼写）
2. `related_projects` 字段为空

**解决方案**:
```python
# 检查项目名称
# 确保 user_profile.yaml 中的项目名称与
# 内容项目的 related_projects 字段完全匹配
```

### 问题 3: 相似度计算不准确

**症状**: 相关内容相似度分数很低

**可能原因**:
- 当前使用简化版关键词匹配
- 未启用 embedding 模型

**解决方案**:
- 当前版本：确保内容标题/摘要包含关键词
- 未来版本：启用 SentenceTransformer embedding

## 🔮 未来优化方向

### 1. 集成真正的 Embedding 模型

**当前**: 简化版关键词匹配（Jaccard 相似度）
**未来**: 使用 SentenceTransformer 计算向量相似度

**优势**:
- 语义理解更准确
- 支持同义词匹配
- 更好的相关性判断

### 2. Git API 集成

**当前**: 基于用户配置的静态活跃度
**未来**: 动态查询 Git 提交频率

**实现**:
```python
def get_project_activity_from_git(self, project_name: str) -> float:
    # 查询最近 7 天的提交数
    commits = git_api.get_recent_commits(project_name, days=7)
    # 转换为活跃度分数
    return min(1.0, commits / 10.0)
```

### 3. 学习型重排

**当前**: 固定权重系数
**未来**: 基于用户反馈自动调整权重

**实现**:
- 用户点赞 → 提升相似度权重
- 用户踩 → 降低活跃度权重
- 使用强化学习优化权重组合

## 📝 测试覆盖

**测试文件**: `tests/test_reranker.py`

**测试数量**: 20 个测试用例

**覆盖范围**:
- ✅ 项目活跃度追踪（6 个测试）
- ✅ 内容重排（14 个测试）
- ✅ 集成场景（1 个测试）

**运行测试**:
```bash
python -m pytest tests/test_reranker.py -v
```

## ✨ 完成状态

### Phase 1.3: 相关性重排 ✅

- ✅ 项目活跃度追踪器
- ✅ 内容重排器
- ✅ 集成到报告生成器
- ✅ 测试覆盖（20 个测试）
- ✅ 使用文档

**估计时间**: 2 天 → **实际时间**: 完成

---

_创建时间: 2025-11-12_
_负责人: AI Assistant_
_状态: ✅ 已完成_


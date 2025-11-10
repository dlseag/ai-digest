# AI简报系统升级状态报告

## 当前问题

**核心问题**：嵌入模型下载导致系统无法启动

- `sentence-transformers` 和 `llama-index` 在首次使用时会自动下载模型（约400MB）
- 下载过程卡在 HuggingFace 缓存锁上，导致3分钟超时
- 即使设置了 `TRANSFORMERS_OFFLINE=1`，transformers 库仍会尝试访问缓存目录

## 已完成的代码升级（✅）

### 1. 用户画像系统
- ✅ `src/memory/user_profile_manager.py` - 多向量表示、EMA更新
- ✅ `src/storage/feedback_db.py` - 支持用户画像存储、显式反馈、A/B测试

### 2. Few-Shot学习
- ✅ `src/learning/explicit_feedback.py` - 显式反馈管理器
- ✅ `src/processors/ai_processor.py` - 集成Few-Shot示例注入
- ✅ `src/processors/ai_processor_batch.py` - 批处理也支持Few-Shot

### 3. A/B测试基础设施
- ✅ `src/learning/ab_tester.py` - 完整的A/B测试框架
- ✅ CLI命令 `--ab-summary` - 查看实验结果

### 4. 内存管理架构
- ✅ `src/memory/memory_manager.py` - 统一内存管理
- ✅ `src/memory/vector_store.py` - 第二大脑向量库（延迟初始化）
- ✅ 所有模块都支持延迟加载，避免启动时下载模型

### 5. LangGraph智能体框架（部分完成）
- ✅ `src/agents/__init__.py` - 智能体模块结构
- ✅ `src/agents/proactive_agent.py` - 主动建议智能体
- ⚠️ 其他智能体（triage, cluster, differential, critique）代码已编写但未测试

## 未完成的功能（⚠️）

### 1. 向量库初始化
- ⚠️ `scripts/init_vector_store.py` - 脚本已创建但无法运行（模型下载问题）
- ⚠️ 历史数据（周报、项目README、研究报告）未导入向量库

### 2. LangGraph工作流
- ⚠️ `src/agents/briefing_graph.py` - 工作流定义已编写但未测试
- ⚠️ `--use-langgraph` 参数无法使用

### 3. 嵌入功能
- ⚠️ 用户画像的向量嵌入功能被禁用
- ⚠️ RAG-Diff、语义聚类等高级功能无法使用

## 建议的解决方案

### 方案A：手动下载模型（推荐）
```bash
# 1. 在网络良好的环境下运行
python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('BAAI/bge-small-en-v1.5')"

# 2. 模型下载完成后，正常运行
python src/main.py --days-back 3
```

### 方案B：使用OpenAI Embeddings（需要API key）
修改 `src/memory/vector_store.py` 和 `user_profile_manager.py`，使用 OpenAI 的嵌入API替代本地模型。

### 方案C：暂时禁用高级功能
当前代码已经支持在嵌入模型不可用时降级运行，但需要验证基础功能是否正常。

## 当前可用功能

即使没有嵌入模型，以下功能仍然可用：
- ✅ 数据采集（RSS、GitHub、Hacker News等）
- ✅ AI处理（使用Poe API）
- ✅ 报告生成
- ✅ 学习引擎（反馈追踪、模式分析）
- ✅ Few-Shot学习（基于显式反馈）
- ✅ A/B测试

## 下一步行动

1. **立即**：在网络环境好的时候手动下载模型
2. **短期**：验证基础功能是否正常（不使用向量库）
3. **中期**：完成向量库初始化，测试LangGraph工作流
4. **长期**：考虑使用云端嵌入服务或优化模型下载流程

## 运行命令

### 基础运行（不使用高级功能）
```bash
# 设置离线模式，跳过嵌入模型
export TRANSFORMERS_OFFLINE=1
export HF_HUB_OFFLINE=1
python src/main.py --days-back 3
```

### 带超时保护运行
```bash
# 3分钟超时
./run_with_timeout.sh 180 --days-back 3
```

### 查看A/B测试结果
```bash
python src/main.py --ab-summary
```

## 技术债务

1. 嵌入模型下载机制需要优化（进度条、断点续传、镜像源）
2. 需要更好的降级策略文档
3. LangGraph工作流需要端到端测试
4. 向量库初始化脚本需要增加重试和错误处理

---
**更新时间**: 2025-11-09
**状态**: 代码升级完成，等待模型下载后进行功能测试


# AI 简报配置更新：聚焦 LLM 编程

**更新日期**: 2025-11-10  
**目标**: 提高 LLM 编程相关信息源的权重，降低非技术性内容的优先级

---

## 📊 配置变更总结

### 1. 用户画像更新 (`user_profile.yaml`)

#### ✅ 学习重点调整

**新增核心重点**：
- ✨ **LLM编程与应用开发（核心重点）** - 明确为最高优先级
- ✨ **Prompt Engineering 与 Function Calling** - 实战技能
- ✨ **LLM API 使用与优化（OpenAI、Anthropic、本地模型）**
- ✨ **向量数据库与 Embedding 技术**

#### ✅ 相关性标准重构

**高优先级（High Priority）**：
```yaml
- "LLM编程实战技术（Prompt Engineering、Function Calling、Structured Output）"
- "LLM API 使用技巧与最佳实践（OpenAI、Anthropic、Claude）"
- "RAG系统设计与优化（Chunking、Retrieval、Reranking）"
- "AI Agent 架构模式与实现（LangGraph、Multi-Agent、Tool Use）"
- "LangChain / LangGraph / LlamaIndex 实战教程与案例"
- "向量数据库与 Embedding 技术（Chroma、Pinecone、FAISS）"
- "后端工程师AI转型经验与实战案例"
- "AI开发者工具（Cursor、Claude Code、测试工具）"
- "企业AI落地案例（特别是后端/数据密集型场景）"
- "LLM成本优化与性能监控"
```

**降低优先级的内容**：
- ❌ AI伦理、政策、治理（除非与开发直接相关）
- ❌ 与LLM编程无关的AI新闻（如AI艺术、AI硬件）
- ❌ 纯学术研究且无落地代码

#### ✅ 项目描述增强

为每个项目添加了 **`llm_programming_focus`** 字段：

**mutation-test-killer**:
- 如何设计有效的测试生成 Prompt
- 如何用 RAG 检索代码上下文
- 如何评估 LLM 生成的测试质量

**ai-digest**:
- 如何设计个性化的内容评分 Prompt
- 如何优化 LLM API 调用成本
- 如何实现 LLM 自我进化机制

**rag-practics**:
- 如何优化 Chunking 策略
- 如何提高检索精度（Retrieval Accuracy）
- 如何设计 Hybrid Search（向量+关键词）

---

### 2. 信息源权重调整 (`sources.yaml`)

#### ⬆️ 提升至最高优先级 (Priority: 10)

| 信息源 | 原优先级 | 新优先级 | 理由 |
|--------|---------|---------|------|
| **Simon Willison's Weblog** | 9 | **10** | LLM编程实战专家，Prompt Engineering与API使用技巧 |
| **Eugene Yan** | - | **10** | LLM应用开发与RAG实战专家（新增） |
| **Chip Huyen** | - | **10** | ML系统设计与LLM工程实践（新增） |
| LangChain Blog | 10 | 10 | 保持最高优先级，添加注释 |
| Ben's Bites | 10 | 10 | 保持最高优先级 |
| TLDR AI | 10 | 10 | 保持最高优先级 |

#### ➕ 新增信息源

| 信息源 | 优先级 | 类型 | 说明 |
|--------|--------|------|------|
| **Eugene Yan** | 10 | tech_articles | LLM应用开发与RAG实战专家 |
| **Chip Huyen** | 10 | tech_articles | ML系统设计与LLM工程实践 |
| **Lil'Log (Lilian Weng)** | 9 | tech_articles | OpenAI研究员，LLM与Agent深度解析 |
| Sebastian Raschka | 9 | tech_articles | LLM微调与训练技术（暂时禁用） |

#### ⬇️ 降低优先级

| 信息源 | 原优先级 | 新优先级 | 理由 |
|--------|---------|---------|------|
| **TechCrunch AI** | 9 | **7** | AI行业新闻，技术深度较低 |
| **Sequoia Capital AI** | 8 | **7** | 投资洞察，技术深度较低 |
| **Y Combinator Blog** | 9 | **8** | 关注AI开发者工具公司，但技术深度中等 |

---

## 🎯 预期效果

### 1. 内容质量提升

- ✅ **更多实战代码示例**：Eugene Yan、Chip Huyen、Simon Willison 都以代码驱动的教程著称
- ✅ **更深的技术深度**：从"AI是什么"转向"如何用LLM编程"
- ✅ **更强的可操作性**：每篇文章都应该有可直接应用的技术点

### 2. 报告结构优化

**必看内容（Must-Read）** 将更多包含：
- LLM API 使用技巧
- Prompt Engineering 最佳实践
- RAG 系统优化案例
- Agent 架构设计模式
- LangChain/LangGraph 实战教程

**降低出现频率的内容**：
- AI融资新闻
- AI政策与伦理讨论
- 纯产品发布（无技术细节）
- AI艺术与创意应用

### 3. 个性化评分改进

AI 评分系统将更准确识别：
- ✅ **高价值**：包含代码示例、架构图、实战经验的文章
- ✅ **中价值**：有技术深度但无代码的分析文章
- ❌ **低价值**：纯新闻、融资、政策类内容

---

## 📈 监控指标

### 下次报告生成后，检查以下指标：

1. **必看内容质量**
   - [ ] 是否包含至少 1 篇 LLM 编程实战文章？
   - [ ] 是否减少了融资/政策类新闻？

2. **信息源命中率**
   - [ ] Eugene Yan / Chip Huyen / Simon Willison 的文章是否被识别为高优先级？
   - [ ] TechCrunch / Sequoia 的文章是否被降级？

3. **可操作性**
   - [ ] "建议行动"中是否包含具体的代码实践建议？
   - [ ] 是否有可直接应用于当前项目的技术点？

---

## 🔄 后续优化建议

### 短期（1-2周）

1. **观察新信息源质量**
   - Eugene Yan 和 Chip Huyen 的文章更新频率较低，需要观察实际命中率
   - 如果质量高但频率低，考虑添加更多类似信息源

2. **调整评分阈值**
   - 当前"必看内容"阈值是 `personal_priority >= 8`
   - 如果内容质量提升，可以考虑提高到 9，保证只有最高质量的内容进入

### 中期（1个月）

1. **添加更多 LLM 编程信息源**
   - **Hacker News "Show HN"**：过滤 LLM 相关的开源项目
   - **Reddit r/LangChain**：社区讨论与实战案例
   - **Reddit r/LocalLLaMA**：本地模型部署经验

2. **优化过滤关键词**
   - 当前过滤了 "langchain=="、"llama.cpp" 等版本号新闻
   - 可以考虑添加更多低价值关键词（如 "raises $", "funding", "valuation"）

### 长期（3个月）

1. **实现基于内容的动态权重**
   - 不仅基于信息源，还基于文章内容的技术深度
   - 例如：包含代码示例的文章自动 +2 分

2. **建立个人知识库反馈循环**
   - 记录哪些文章被深入阅读、哪些被跳过
   - 用这些数据训练个性化的评分模型

---

## ✅ 验证清单

在下次生成报告后，请验证：

- [ ] 必看内容中至少有 50% 是 LLM 编程相关的技术文章
- [ ] Eugene Yan / Chip Huyen / Simon Willison 的文章出现在必看内容或建议行动中
- [ ] TechCrunch / Sequoia 的文章不再出现在必看内容中（除非技术深度极高）
- [ ] "建议行动"中包含可直接应用的代码实践建议
- [ ] 报告中减少了融资、政策、伦理类新闻

---

**下次运行命令**：

```bash
cd /Users/david/Documents/ai-workflow/ai-digest
python src/main.py --days-back 1
```

**预期改进**：
- 🎯 更聚焦于 LLM 编程实战
- 📚 更多可操作的技术内容
- 🚀 更少的噪音和低价值信息


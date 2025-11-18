# 技术债清单 (Technical Debt)

## 🔴 高优先级 (High Priority)

### 1. 修复失败的 RSS/Newsletter 源
**问题描述**：
多个高质量的 Newsletter 和个人博客源采集失败，需要逐个修复。

**失败的源列表**：

#### 需要自定义解析器的源（5个）
- [ ] **Ben's Bites** - 每日AI建设者更新（已启用但需要HTML解析器）
- [ ] **The Neuron** - 投资者视角的AI更新
- [ ] **Superhuman AI** - 工具和工程最佳实践
- [ ] **Sebastian Raschka** - LLM训练配方
- [ ] **Yao Fu** - 研究评论

#### URL失败/需要验证的源（11个）
- [x] **The Verge AI** - 消费者科技视角的AI报道（404错误，已改用 https://www.theverge.com/rss/ai-artificial-intelligence/index.xml）
- [x] **Lilian Weng** - OpenAI可解释性深度解析（已修复：https://lilianweng.github.io/index.xml）
- [x] **Jay Alammar** - 图解Transformer讲解（已修复：https://jalammar.github.io/feed.xml）
- [x] **Eugene Yan** - 应用ML产品经验（已修复：https://eugeneyan.com/rss/）
- [x] **Jeremy Howard / fast.ai** - 实用深度学习和LLM文章（已修复：https://www.fast.ai/index.xml）
- [x] **AI Notebooks by Hamel** - 实验日志（已修复：https://hamel.dev/index.xml）
- [ ] **Venture in AI** - 应用AI风险投资洞察（404，可能已停更）
- [ ] **Data Science at Home** - 数据工作流的LLM（404，可能已停更）
- [ ] **Generative AI with Python** - 实践教程（404，可能已停更）
- [ ] **Applied LLMs** - 生产环境LLM案例研究（404，可能已停更）
- [ ] **AI with Vercel** - 边缘部署模式（404，可能已停更）
- [ ] **Coactive AI** - 多模态AI产品更新（404，可能已停更）

#### 超时的源（1个）
- [x] **TLDR AI** - 高质量每日摘要（已验证可用，RSS地址正常）

**修复计划**：
1. 检查每个失败源的URL是否有效
2. 对于需要自定义解析器的源，开发对应的HTML解析器
3. 对于超时的源，增加重试机制或调整超时时间
4. 对于404的源，查找新的RSS地址

**预计工作量**：2-3天

---

## 🟡 中优先级 (Medium Priority)

### 2. Notion 集成
**问题描述**：
实现将每日简报自动保存到 Notion 数据库的功能。

**功能需求**：
- [ ] 配置 Notion API Token
- [ ] 创建 Notion 数据库模板
- [ ] 实现自动推送逻辑
- [ ] 支持富文本格式（标题、列表、链接等）
- [ ] 支持标签和分类
- [ ] 添加错误处理和重试机制

**技术方案**：
- 使用 `notion-client` Python 库
- 在报告生成完成后，调用 Notion API 创建新页面
- 支持 Markdown 到 Notion Blocks 的转换

**参考资源**：
- Notion API 文档：https://developers.notion.com/
- notion-client GitHub：https://github.com/ramnes/notion-sdk-py

**预计工作量**：1-2天

---

### 3. AI 批量处理的分类准确性
**问题描述**：
AI 在批量处理时，会错误地将某些论文分类为 `headline`，导致论文出现在"今日头条"板块。

**当前解决方案**：
- 在 `_select_top_headlines` 中添加了来源过滤，排除论文来源

**更好的解决方案**：
- [ ] 优化 AI 批量处理的提示词，明确论文的分类规则
- [ ] 添加后处理逻辑，强制修正明显错误的分类
- [ ] 考虑使用更强大的模型（如 Claude Sonnet）进行分类

**预计工作量**：0.5天

---

### 4. 摘要内容混乱问题
**问题描述**：
某些条目的标题和摘要不匹配，例如论文标题配上了 Hacker News 的摘要。

**可能原因**：
- AI 批量处理时，条目顺序或匹配逻辑出现问题
- 深度研究功能失败时，使用了错误的备用摘要

**修复计划**：
- [ ] 检查 AI 批量处理器的响应解析逻辑
- [ ] 添加摘要和标题的一致性验证
- [ ] 改进深度研究失败时的错误处理

**预计工作量**：1天

---

## 🟢 低优先级 (Low Priority)

### 5. 健康检查机制优化
**问题描述**：
当前有 56 个数据源被标记为不健康，但没有自动恢复机制。

**改进建议**：
- [ ] 定期重试不健康的源（例如每周一次）
- [ ] 区分临时失败和永久失败
- [ ] 发送健康报告给用户

**预计工作量**：1天

---

### 6. 主流科技媒体的采集优化
**问题描述**：
新增的主流媒体（TechCrunch, VentureBeat等）需要验证采集效果。

**验证项目**：
- [ ] 确认 RSS 地址有效
- [ ] 验证采集到的内容质量
- [ ] 调整优先级和分类

**预计工作量**：0.5天

---

## 📊 技术债统计

| 优先级 | 数量 | 预计工作量 |
|--------|------|------------|
| 高     | 1    | 2-3天      |
| 中     | 4    | 3-4天      |
| 低     | 2    | 1.5天      |
| **总计** | **7** | **6.5-8.5天** |

---

## 🎯 下一步行动

1. **立即处理**：修复 The Verge AI 的 404 错误（高价值源）
2. **本周完成**：修复至少 5 个失败的 Newsletter 源
3. **下周评估**：Notion 集成的必要性和优先级

---

## 📝 修复记录

### 2025-11-17 修复
✅ **成功修复 7 个高价值源**：
1. **The Verge AI** - 更新URL为 `https://www.theverge.com/rss/ai-artificial-intelligence/index.xml`
2. **Lilian Weng** - 更新URL为 `https://lilianweng.github.io/index.xml`
3. **Jay Alammar** - 更新URL为 `https://jalammar.github.io/feed.xml`
4. **Eugene Yan** - 更新URL为 `https://eugeneyan.com/rss/`
5. **Jeremy Howard / fast.ai** - 更新URL为 `https://www.fast.ai/index.xml`
6. **AI Notebooks by Hamel** - 更新URL为 `https://hamel.dev/index.xml`
7. **TLDR AI** - 验证可用，无需修改

📊 **修复进度更新**：
- 已修复：7/17 (41.2%) ⬆️ 从 11.8%
- 需要自定义解析器：4个（Ben's Bites等）
- 可能已停更：6个（Venture in AI等）

---

*最后更新：2025-11-17*


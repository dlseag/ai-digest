# YC 生态信息源集成说明

## ✅ 已集成的 YC 信息源

### 1. **YC 官方博客** (新增)
- **URL**: https://www.ycombinator.com/blog/feed
- **类型**: RSS Feed
- **优先级**: 9/10
- **内容**:
  - YC 新孵化公司发布（Launch Posts）
  - YC 合伙人的行业洞察
  - YC 活动和 Demo Day 信息
  - AI 创业趋势分析

### 2. **Hacker News "Launch HN" 标签** (增强)
- **现有配置**: 已启用 Hacker News 采集
- **新增**: 专门捕获 "Launch HN" 标签
- **优先级**: 9/10
- **内容**:
  - YC 孵化公司的产品发布
  - 创始人直接与社区互动
  - 实时反馈和讨论
  - 技术细节和架构分享

**示例**: 你之前看到的 "Launch HN: Propolis (YC X25)" 就来自这个渠道

### 3. **Sequoia Capital AI** (新增)
- **URL**: https://www.sequoiacap.com/feed/
- **类型**: RSS Feed
- **优先级**: 8/10
- **内容**:
  - 红杉资本的 AI 投资洞察
  - 补充 YC 视角，提供更广泛的 VC 观点
  - AI 市场趋势和战略分析

---

## 🎯 为什么关注 YC 生态？

### 1. **前沿技术信号**
- YC 孵化的 AI 公司通常代表最新的技术趋势
- 例如：Propolis (Browser Agent QA)、LangChain (AI 编排)

### 2. **直接竞品/参考**
- 很多 YC 公司与你的项目方向重叠
- 例如：
  - Propolis → mutation-test-killer 的参考案例
  - 各种 RAG 工具 → rag-practics 的对标对象

### 3. **商业模式验证**
- YC 公司的成功案例可以验证你的产品方向
- 了解市场需求和定价策略

### 4. **技术架构学习**
- Launch HN 帖子通常包含技术细节
- 创始人会分享架构决策和踩坑经验

---

## 📊 AI 简报中的 YC 内容识别

### 自动标记
AI 处理器会自动识别 YC 相关内容并提升优先级：

```yaml
# 高优先级触发条件
- 标题包含 "YC X25", "YC W25", "Launch HN"
- 来源为 YC Blog 或 Hacker News Launch
- 内容涉及开发者工具、测试工具、RAG、AI Agent

# 个人优先级评分
- YC 孵化的 AI 开发者工具：9-10/10
- YC 孵化的其他 AI 公司：6-8/10
- YC 的行业洞察文章：7-9/10
```

### 简报中的展示
- **必看内容**: YC 孵化的与你项目直接相关的公司
- **建议行动**: 推荐深入研究的 YC 公司
- **可选探索**: 其他可能相关的 YC 动态

---

## 🔍 YC 公司分类（AI 自动识别）

### 直接相关（高优先级）
- **测试/QA 工具**: Propolis
- **AI 编排框架**: LangChain
- **RAG 相关**: 各种向量数据库、检索工具
- **开发者工具**: AI 代码助手、调试工具

### 间接相关（中优先级）
- **AI 基础设施**: 推理引擎、模型服务
- **数据工具**: ETL、数据管道
- **监控/可观测性**: AI 应用监控

### 参考价值（低优先级）
- **非技术类 AI 应用**: 营销、销售工具
- **消费级 AI 产品**: 聊天机器人、内容生成

---

## 🚀 下一步建议

### 1. **定期关注 YC Demo Day**
- 每年 2 次（冬季和夏季）
- 集中发布大量新公司
- 建议在 Demo Day 后专门生成一期"YC 特辑"

### 2. **深入研究竞品**
当简报推荐 YC 公司时，可以：
```bash
# 使用研究助手深入分析
cd /Users/david/Documents/ai-workflow/research-assistant
python main.py --url "https://news.ycombinator.com/item?id=XXXXX"
```

### 3. **跟踪关键公司**
建议手动跟踪这些 YC 公司（与你项目相关）：
- **Propolis**: Browser Agent QA（mutation-test-killer 参考）
- **LangChain**: AI 编排框架（你的核心技术栈）
- **Weaviate/Pinecone**: 向量数据库（rag-practics 相关）

### 4. **加入 YC 社区**
- 关注 YC 的 Twitter/X 账号
- 订阅 YC Newsletter
- 参与 Hacker News 讨论

---

## 📝 配置文件位置

所有 YC 相关配置已更新到：
- **信息源配置**: `/Users/david/Documents/ai-workflow/ai-digest/config/sources.yaml`
- **用户画像**: `/Users/david/Documents/ai-workflow/ai-digest/config/user_profile.yaml`

---

## 🎯 预期效果

集成 YC 信息源后，你的简报将：
1. ✅ 自动捕获 YC 新公司发布
2. ✅ 优先展示与你项目相关的 YC 公司
3. ✅ 提供 VC 视角的行业趋势分析
4. ✅ 推荐值得深入研究的 YC 案例

**下次生成简报时，你将看到更多 YC 相关的内容！**


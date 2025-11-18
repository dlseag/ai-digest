# 数据源封存记录 (2025-11-12)

## 封存原因

根据运行日志分析，以下数据源出现错误，已暂时封存（设置为 `enabled: false`），待后续分析修复。

## 封存统计

- **总计封存**: 64 个源
- **新封存**: 3 个源（Azure AI Blog, Digamma AI, Deepchecks）
- **已封存**: 61 个源（之前已禁用）

## 错误分类

### HTTP 404 (Not Found) - 47 个源

这些源的 RSS feed URL 已失效或不存在：

- Google DeepMind Blog
- Google Research
- AWS Generative AI Blog
- IBM Research AI
- Stability AI Blog
- Snowflake ML Blog
- LlamaIndex Blog
- vLLM Blog
- FastChat Blog
- Pinecone Learn
- Milvus Blog
- LanceDB Blog
- Haystack Blog
- Modal Blog
- Flyte Blog
- Supabase AI
- Stanford CRFM
- UW NLP
- ETH AI Center
- MILA Québec
- Naver AI Lab
- EPFL NLP Lab
- TUM AI Lab
- USC Viterbi AI
- LangSmith
- PromptLayer
- Ragas
- Braintrust Data
- Truera AI
- LightOn AI
- Scale Spellbook
- HoneyHive
- Evidently AI
- Semantic Scholar AI
- Open Source AI Radar
- Builder Bytes
- Daily Papers Digest
- Venture in AI
- Data Science at Home
- Applied LLMs
- AI with Vercel
- AI Notebooks by Hamel
- Jeremy Howard / fast.ai
- Eugene Yan
- Lilian Weng
- Jay Alammar
- Coactive AI

### HTTP 403 (Forbidden) - 5 个源

这些源需要认证或禁止访问：

- Arize AI
- Digamma AI ⚠️ **新封存**
- Deepchecks ⚠️ **新封存**
- Product Hunt AI
- Product Hunt Dev Tools

### HTTP 400 (Bad Request) - 1 个源

- FAIR Publications

### 网络错误 - 7 个源

DNS 解析失败或连接超时：

- Azure AI Blog ⚠️ **新封存** (ReadTimeout)
- Chroma Blog (NameResolutionError)
- Oxford Applied AI (NameResolutionError)
- Evals.art (NameResolutionError)
- GitHub Trending AI (NameResolutionError)
- Generative AI with Python (NameResolutionError)
- PromptOps (ConnectTimeout)

### HTTP 500 (Server Error) - 4 个源

服务器返回过多 500 错误：

- Humanloop
- Helicone
- Aporia
- LessWrong AI

## 处理建议

### 短期（立即）

1. ✅ **已完成**: 将所有出错源设置为 `enabled: false`
2. ✅ **已完成**: 在配置文件中添加 `[已禁用：运行日志显示错误]` 标记

### 中期（1-2周）

1. **验证 URL**: 检查 404 错误的源，确认 RSS feed URL 是否已变更
2. **更新 URL**: 如果源已迁移到新 URL，更新配置并重新启用
3. **检查认证**: 对于 403 错误，检查是否需要 API key 或特殊认证
4. **网络诊断**: 对于网络错误，检查 DNS 解析和网络连接

### 长期（1个月）

1. **定期健康检查**: 使用 `scripts/validate_sources.py` 定期检查所有源的健康状态
2. **自动恢复**: 考虑实现自动恢复机制，当源恢复时自动重新启用
3. **替代源**: 寻找替代数据源，特别是对于重要但已失效的源

## 当前状态

- **启用源**: 43 个（RSS: 33, News: 10）
- **禁用源**: 87 个（RSS: 67, News: 20）

## 相关文件

- 配置文件: `config/sources.yaml`
- 封存脚本: `scripts/disable_failed_sources.py`
- 验证脚本: `scripts/validate_sources.py`

---

**封存日期**: 2025-11-12  
**执行者**: AI Assistant  
**依据**: 运行日志分析（2025-11-12 20:15-20:31）


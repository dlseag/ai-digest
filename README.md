# AI Weekly Report Generator

自动化生成AI工程师周报的系统，使用AI智能处理20+核心信息源，生成个性化的技术周报。

## 🎯 功能特点

- **自动化数据采集**: 监控20+核心信息源（行业新闻、技术博客、GitHub、Hacker News、ProductHunt）
- **AI智能处理**: 通过Poe API使用Claude进行内容总结、相关性打分、影响分析
- **智能筛选**: Top 5头条优先行业大事（新模型发布、融资、产品上线等）
- **个性化周报**: 根据用户学习阶段生成定制化建议
- **AWS部署**: 完全无服务器架构，成本极低
- **容器化**: Docker支持，易于部署到Lambda/ECS

## 📋 周报结构

1. **本周头条** - Top 5必知大事（聚焦行业动态）
2. **深度洞察** - 精选技术文章和最佳实践
3. **精选项目** - 开源AI工具推荐
4. **技术参考区** - 框架更新和新模型发布

## 📡 信息源覆盖

### 行业新闻与Newsletter（6个）
- TechCrunch AI - 科技媒体头条
- VentureBeat AI - 行业深度报道
- The Verge AI - 前沿科技动态
- MIT Tech Review - 技术评论
- Import AI - Jack Clark的深度分析（周刊）
- Towards Data Science - Medium技术文章聚合

### 技术博客
- OpenAI、Anthropic、Google AI
- Hugging Face、LangChain

### 开发者社区
- GitHub Releases（8个核心框架）
- Hacker News（AI话题热帖）
- ProductHunt（AI工具热榜，新增）
- Twitter 信号（AI领袖实时观点，可选）

### 未来扩展（可选）
- Reddit（r/LocalLLaMA、r/LangChain）
- 学术论文（Arxiv AI）

## 🚀 快速开始

### 1. 安装依赖

```bash
# 克隆项目
cd /path/to/ai-weekly-report

# 创建虚拟环境（推荐）
python3 -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 安装依赖
make install
```

### 2. 配置环境变量

```bash
# 复制环境变量模板
cp env.template .env

# 编辑 .env 文件
```

**必需配置**：
- `POE_API_KEY` - Poe API密钥（[获取](https://poe.com/api_key)）

**可选配置**（提升功能）：
- `GITHUB_TOKEN` - GitHub Token（提升API限额从60到5000次/小时）
- `PRODUCTHUNT_API_TOKEN` - ProductHunt Token（无token使用RSS fallback）
- `DEVELOPER_MODEL` - Poe模型名称（默认：Claude-Haiku-4.5）
- `TWITTER_API_KEY` - twitterapi.io 接入密钥（启用Twitter采集时必填）

### 3. 本地运行

```bash
# 生成周报
make run-local

# 报告将保存到 output/weekly_report_YYYY-MM-DD.md
```

### 4. 服务管理（推荐）

使用 macOS launchd 管理后台服务，实现自动启动和崩溃恢复：

#### 首次安装

```bash
cd ai-workflow/ai-digest

# 安装服务到 launchd
./scripts/manage_services.sh install

# 启动服务
./scripts/manage_services.sh start
```

#### 日常使用

```bash
# 查看服务状态
./scripts/manage_services.sh status

# 查看实时日志
./scripts/manage_services.sh logs

# 重启服务
./scripts/manage_services.sh restart

# 停止服务
./scripts/manage_services.sh stop
```

#### 健康检查

```bash
# 快速检查服务状态
./scripts/health_check.sh
```

**优势**：
- ✅ 开机自动启动
- ✅ 进程崩溃自动重启
- ✅ 统一的日志管理
- ✅ 简单的命令行管理

**服务说明**：
- **Tracking Server** (端口 8000) - 追踪用户阅读行为，并同步触发"想看更多"深度研究流程  
  _自 2025/11 起，旧版 `deep-dive-worker` 已完全退役，`scripts/manage_services.sh` 会自动卸载遗留的 launchd 配置。_

服务将在系统启动时自动运行，无需手动启动。

### 5. 定时任务（可选）

- 每日自学习、每周自动生成周报，可参考 `docs/cron_jobs.md`

## 📦 项目结构

```
ai-weekly-report/
├── src/                    # 源代码
│   ├── collectors/         # 数据采集器
│   ├── processors/         # AI处理器
│   ├── generators/         # 报告生成器
│   └── main.py            # 主入口
├── config/                # 配置文件
│   ├── sources.yaml       # 信息源配置
│   └── user_profile.yaml  # 用户学习阶段
├── templates/             # 报告模板
├── deployment/            # AWS部署文件
├── tests/                 # 测试
└── output/                # 生成的报告

```

## 🔧 开发

```bash
# 安装开发依赖
make install-dev

# 运行测试
make test

# 代码格式化
make lint

# 类型检查
make type-check
```

## ☁️ AWS部署

### 前置要求

- AWS账号
- AWS CLI配置好
- Docker已安装

### 部署步骤

```bash
# 1. 构建Docker镜像
make build-docker

# 2. 部署到Lambda
make deploy-lambda

# 3. 配置定时任务（每周五下午）
# 详见 deployment/README.md
```

## 💰 成本估算

- **Lambda执行**: ~$0.01/周
- **S3存储**: ~$0.02/月
- **SES邮件**: 免费（前62,000封）
- **Secrets Manager**: $0.40/月
- **总计**: ~$0.50/月

## 📚 信息源

### RSS订阅（5个）
- OpenAI Blog
- Anthropic Blog
- Google AI Blog
- Hugging Face Blog
- LangChain Blog

### GitHub监控（8个）
- langchain-ai/langchain
- langchain-ai/langgraph
- run-llama/llama_index
- openai/openai-python
- anthropics/anthropic-sdk-python
- vllm-project/vllm
- ggerganov/llama.cpp
- ollama/ollama

### 排行榜（2个）
- MTEB Leaderboard
- Chatbot Arena

### Twitter（可选启用）
- Sam Altman（@sama）
- Andrej Karpathy（@karpathy）
- Yann LeCun（@ylecun）
- Ian Goodfellow（@goodfellow_ian）
- John Carmack（@id_aa_carmack）

> Twitter 信息源通过 `config/sources.yaml` 的 `twitter` 节配置，默认关闭。开启后会筛选互动量 ≥500 的原创推文，用于增强头条引用和社区热议分析。

## 🤝 贡献

欢迎提交Issues和Pull Requests！

## 📄 许可证

MIT License


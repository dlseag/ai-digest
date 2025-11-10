# 🚀 快速开始指南

5分钟快速上手AI Weekly Report Generator。

## 📋 前置要求

- Python 3.11+
- Poe API Key ([获取地址](https://poe.com/api_key))
- Git（可选，用于克隆代码）

## ⚡ 快速安装

### 1. 克隆项目（或解压下载的代码）

```bash
cd /Users/david/Documents/ai-weekly-report
```

### 2. 创建虚拟环境（推荐）

```bash
python3 -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
```

### 3. 安装依赖

```bash
make install
# 或手动安装
# pip install -r requirements.txt
```

### 4. 配置API密钥

复制环境变量模板：

```bash
cp env.template .env
```

编辑`.env`文件，填入你的Poe API密钥：

```bash
# 必须配置
POE_API_KEY=your_poe_api_key_here

# 模型配置（可选，默认使用Haiku）
DEVELOPER_MODEL=Claude-Haiku-4.5
# ARCHITECT_MODEL=Claude-Sonnet-4.5  # 如需更强的分析能力

# 可选配置（提高GitHub API限制）
GITHUB_TOKEN=ghp_xxxxx

# 用户信息（可选）
USER_NAME=David
CURRENT_LEARNING_MONTH=3
CURRENT_LEARNING_TOPIC=LLM编排和LangChain
```

## 🎉 运行第一个周报

```bash
make run-local
```

或者：

```bash
python -m src.main
```

## 📄 查看结果

生成的周报保存在：

```bash
output/weekly_report_2024-11-04.md
```

用任意Markdown编辑器打开查看，推荐：
- VS Code（Markdown Preview）
- Typora
- Obsidian

## 🔧 自定义配置

### 修改用户学习阶段

编辑 `config/user_profile.yaml`:

```yaml
learning_roadmap:
  current_month: 3
  current_topic: "LLM编排和LangChain"
  current_focus:
    - "OpenAI API编排"
    - "LangChain组件使用"
```

### 修改信息源

编辑 `config/sources.yaml`，添加或删除RSS源和GitHub仓库。

### 修改周报模板

编辑 `templates/report_template.md.jinja`，自定义周报格式。

## 📊 理解输出

运行时会看到4个步骤：

```
步骤 1/4: 数据采集
  ✓ RSS采集完成: 15 条目
  ✓ GitHub采集完成: 8 个Release

步骤 2/4: AI智能处理
  🤖 开始AI处理 23 条目...
  ✓ AI处理完成：23/23 条目

步骤 3/4: 生成行动清单
  📋 行动清单:
    - 必做任务: 2 项
    - 可选任务: 5 项

步骤 4/4: 生成周报
  📝 生成Markdown报告...
  ✓ 周报生成完成！
```

## ⚙️ 高级选项

### 采集更长时间范围

修改 `src/main.py` 的 `days_back` 参数：

```python
generator.run(days_back=14)  # 采集14天内容
```

### 只采集特定类别

在 `config/sources.yaml` 中注释掉不需要的源。

### 使用不同的Claude模型

在`.env`文件中配置：

```bash
# 使用更强的Sonnet模型
DEVELOPER_MODEL=Claude-Sonnet-4.5

# 或在代码中指定
# AIProcessor(model="Claude-Sonnet-4.5")
```

可用的Poe模型：
- `Claude-Haiku-4.5` - 最快最便宜
- `Claude-Sonnet-4.5` - 平衡性能和成本
- `Claude-Opus-4.5` - 最强但最贵（如果可用）

## 🐛 常见问题

### 问题1：`POE_API_KEY not found`

**解决**：确保创建了`.env`文件并填写了Poe API密钥。
- 获取密钥：访问 https://poe.com/api_key

### 问题2：GitHub API限制

**解决**：在`.env`中添加`GITHUB_TOKEN`，提高限制从60次/小时到5000次/小时。

### 问题3：AI处理很慢

**原因**：正常现象，处理20+条目需要2-5分钟。

**优化**：使用更快的模型（Haiku已经是最快的）。

### 问题4：RSS采集失败

**解决**：
1. 检查网络连接
2. 某些源可能暂时不可用，系统会跳过并继续

## 📚 下一步

✅ 本地运行成功后，可以：

1. **定时运行**：设置cron job每周自动生成
   ```bash
   # 每周五下午2点
   0 14 * * 5 cd /path/to/ai-weekly-report && make run-local
   ```

2. **部署到AWS**：查看 `deployment/README.md`

3. **集成到工作流**：
   - 发送到Notion
   - 推送到GitHub
   - 邮件通知（需配置SMTP）

## 💡 提示

- **首次运行**可能较慢（构建缓存）
- **API成本**约$0.10/次（使用Haiku模型）
- **报告质量**与用户画像配置直接相关

## 🆘 获取帮助

遇到问题？
1. 查看日志：`weekly_report_generator.log`
2. 运行测试：`make test`
3. 查看详细文档：`README.md`

---

**恭喜！你已经成功运行了AI Weekly Report Generator！** 🎉


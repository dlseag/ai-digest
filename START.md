# 🚀 AI 简报快速启动指南

## 一键启动

```bash
cd /Users/david/Documents/ai-workflow/ai-digest && make run-local
```

## 服务管理

### 查看后台服务状态
```bash
./scripts/manage_services.sh status
```

### 启动/停止追踪服务器（用于深度研究功能）
```bash
./scripts/manage_services.sh start   # 启动
./scripts/manage_services.sh stop    # 停止
./scripts/manage_services.sh restart # 重启
./scripts/manage_services.sh logs    # 查看实时日志
```

### 健康检查
```bash
./scripts/health_check.sh
```

## 输出位置

### 每日简报
- **Markdown**: `output/weekly_report_YYYY-MM-DD.md`
- **HTML**: `output/weekly_report_YYYY-MM-DD.html` （可在浏览器中打开，支持评分和深度研究）

### 深度研究报告
- **目录**: `/Users/david/Documents/ai-workflow/output/deep_dive_reports/`
- **格式**: `YYYYMMDD_HHMMSS_architect_标题.md`

## 常用命令

### 生成简报
```bash
make run-local              # 生成今天的AI简报
```

### 开发相关
```bash
make install                # 安装依赖
make test                   # 运行测试
make lint                   # 代码格式化
make clean                  # 清理缓存文件
```

## 配置文件

- **环境变量**: `.env` （需要配置 POE_API_KEY）
- **信息源配置**: `config/sources.yaml`
- **用户画像**: `config/user_profile.yaml`
- **学习配置**: `config/learning_config.yaml`

## 服务端口

- **追踪服务器**: http://localhost:8000
  - API 端点: http://localhost:8000/api/track
  - 健康检查: http://localhost:8000/health

## 注意事项

1. 首次使用前确保已配置 `.env` 文件中的 `POE_API_KEY`
2. 深度研究功能需要追踪服务器运行
3. 服务器已配置为开机自动启动（使用 launchd）
4. 生成简报大约需要 3-5 分钟

## 项目结构

```
ai-digest/
├── src/              # 核心代码
│   ├── collectors/   # 数据采集器
│   ├── processors/   # AI处理器
│   ├── generators/   # 报告生成器
│   ├── learning/     # 学习引擎
│   └── tracking/     # 追踪服务器
├── config/           # 配置文件
├── templates/        # 报告模板
├── scripts/          # 管理脚本
├── output/           # 生成的报告
├── logs/             # 日志文件
└── data/             # 数据库和缓存

```

## 快速链接

- [完整文档](README.md)
- [快速开始指南](QUICK_START.md)
- [项目概述](PROJECT_SUMMARY.md)
- [测试指南](TEST_GUIDE.md)

---

💡 **提示**: 推荐将 HTML 报告设为浏览器书签，每天打开查看最新简报！


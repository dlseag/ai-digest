# 网页版周报使用指南

## 🎯 功能说明

网页版周报提供了交互式界面和评分功能，可以自动追踪你的阅读行为，帮助AI助手更好地学习你的偏好。

## 🚀 快速开始

### 1. 生成报告

运行报告生成命令，系统会自动生成HTML版本：

```bash
python src/main.py --days-back 1
```

生成的文件：
- `output/weekly_report_2025-11-12.md` - Markdown版本
- `output/weekly_report_2025-11-12.html` - HTML版本（带评分功能）

### 2. 启动追踪服务器

在另一个终端启动追踪服务器（用于保存评分和行为数据）：

```bash
python src/tracking/tracking_server.py
```

服务器会在 `http://localhost:8000` 启动。

### 3. 打开HTML报告

用浏览器打开HTML文件：

```bash
open output/weekly_report_2025-11-12.html
```

或者直接双击HTML文件。

## 📊 功能说明

### 评分功能

每个内容条目都有三个评分按钮：

- **👍 喜欢** - 表示这个内容对你有价值
- **👎 不喜欢** - 表示这个内容不相关或质量低
- **➖ 不评价** - 表示中立或跳过

**使用方法**：
1. 阅读内容后，点击相应的评分按钮
2. 按钮会高亮显示你的选择
3. 系统会自动保存你的评分

### 自动追踪

系统会自动追踪以下行为：

1. **点击追踪** - 当你点击"阅读详情"链接时
2. **可见性追踪** - 当你滚动到某个内容时（50%可见）
3. **阅读时长** - 你在报告页面的总阅读时间
4. **评分追踪** - 你的评分选择

## 🔍 数据查看

### 查看追踪数据

使用Python脚本查看追踪数据：

```python
from src.storage.feedback_db import FeedbackDB

db = FeedbackDB()
behaviors = db.get_behaviors(days=7)

for behavior in behaviors:
    print(f"{behavior['timestamp']} - {behavior['action']} - {behavior.get('item_id', 'N/A')}")
```

### 分析行为模式

系统会根据你的行为自动学习：

- **喜欢的源** - 提升相似源的优先级
- **不喜欢的源** - 降低相似源的优先级
- **点击模式** - 优化内容推荐
- **阅读时长** - 判断内容质量

## ⚙️ 配置

### 修改追踪服务器端口

```bash
python src/tracking/tracking_server.py --port 8080
```

### 修改HTML中的API地址

编辑 `templates/report_template.html.jinja`，修改：

```javascript
const TRACKING_API = 'http://localhost:8000/api/track';
```

## 🐛 故障排除

### 问题：评分按钮点击后没有反应

**解决方案**：
1. 确认追踪服务器正在运行
2. 检查浏览器控制台是否有错误
3. 确认API地址正确

### 问题：数据没有保存

**解决方案**：
1. 检查 `data/feedback.db` 文件是否存在
2. 确认追踪服务器日志没有错误
3. 检查数据库权限

### 问题：CORS错误

**解决方案**：
追踪服务器已经配置了CORS，如果仍有问题，检查浏览器控制台错误信息。

## 📈 数据使用

系统会使用追踪数据：

1. **自动调整评分模型** - 根据你的评分优化内容匹配
2. **优化源优先级** - 提升你喜欢的源的优先级
3. **改进推荐算法** - 推荐更符合你偏好的内容
4. **学习你的偏好** - 持续改进个性化程度

## 🔒 隐私说明

- 所有数据存储在本地 `data/feedback.db`
- 不会上传到任何服务器
- 数据仅用于改进你的个人简报体验

---

**创建日期**: 2025-11-12  
**版本**: 1.0.0


# 网页版周报快速开始

## 🚀 三步开始使用

### 1. 生成报告（自动生成HTML版本）

```bash
cd /Users/david/Documents/ai-workflow/ai-digest
python src/main.py --days-back 1
```

**输出**：
- `output/weekly_report_2025-11-12.md` - Markdown版本
- `output/weekly_report_2025-11-12.html` - **HTML版本（带评分功能）** ⭐

### 2. 启动追踪服务器（保存评分数据）

在**新终端**运行：

```bash
cd /Users/david/Documents/ai-workflow/ai-digest
python src/tracking/tracking_server.py
```

或者使用脚本：

```bash
./scripts/start_tracking_server.sh
```

**服务器地址**：`http://localhost:8000`

### 3. 打开HTML报告

```bash
open output/weekly_report_2025-11-12.html
```

或者直接双击HTML文件。

## 📊 使用评分功能

1. **阅读内容** - 浏览报告中的各个条目
2. **点击评分** - 每个条目下方有三个按钮：
   - 👍 **喜欢** - 这个内容对你有价值
   - 👎 **不喜欢** - 这个内容不相关或质量低
   - ➖ **不评价** - 中立或跳过
3. **自动保存** - 点击后会自动保存，显示"✓ 已保存"

## 🔍 追踪的数据

系统会自动追踪：

- ✅ **点击行为** - 你点击了哪些链接
- ✅ **评分行为** - 你的喜欢/不喜欢/不评价选择
- ✅ **可见性** - 你看到了哪些内容（滚动到50%可见时记录）
- ✅ **阅读时长** - 你在报告页面的总阅读时间

## 💡 数据用途

系统会使用这些数据：

1. **自动调整评分模型** - 根据你的评分优化内容匹配
2. **优化源优先级** - 提升你喜欢的源的优先级
3. **改进推荐算法** - 推荐更符合你偏好的内容
4. **学习你的偏好** - 持续改进个性化程度

## 🐛 常见问题

### Q: 评分按钮点击后没有反应？

**A**: 确认追踪服务器正在运行：
```bash
# 检查服务器是否运行
curl http://localhost:8000
# 应该返回: {"status": "ok", "message": "Tracking server is running"}
```

### Q: 如何查看追踪的数据？

**A**: 使用Python脚本：
```python
from src.storage.feedback_db import FeedbackDB

db = FeedbackDB()
behaviors = db.get_behaviors(days=7)

for behavior in behaviors[:10]:  # 显示最近10条
    print(f"{behavior['timestamp']} - {behavior['action']} - {behavior.get('item_id', 'N/A')}")
```

### Q: 数据存储在哪里？

**A**: 本地SQLite数据库：`data/feedback.db`

---

**提示**：追踪服务器需要一直运行才能保存数据。建议在后台运行或使用 `screen`/`tmux`。


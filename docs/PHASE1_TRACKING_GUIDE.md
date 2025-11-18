# Phase 1.1: 阅读行为追踪系统 - 使用指南

## ✅ 已实现功能

### 1. 追踪服务器 (`src/tracking/tracking_server.py`)
- ✅ HTTP服务器监听端口 8000
- ✅ API 端点: `POST /api/track`
- ✅ CORS 支持（跨域请求）
- ✅ 自动保存到数据库

### 2. 数据库支持 (`src/storage/feedback_db.py`)
- ✅ `reading_behaviors` 表
- ✅ `save_reading_behavior()` 方法
- ✅ `get_behaviors()` 查询方法
- ✅ 索引优化（item_id, report_id, action）

### 3. HTML 集成 (`templates/report_template.html.jinja`)
- ✅ 点击追踪（用户点击阅读链接）
- ✅ 浏览追踪（内容进入可见区域）
- ✅ 反馈追踪（👍/👎/➖）
- ✅ 阅读时长追踪（页面停留时间）

### 4. 分析工具 (`scripts/analyze_reading_behaviors.py`)
- ✅ 行为类型分布
- ✅ 用户反馈统计
- ✅ 内容区域热度
- ✅ 关键指标计算（参与率、点击率、反馈率）
- ✅ 内容偏好洞察

## 🚀 快速开始

### 步骤 1: 启动追踪服务器

```bash
cd /Users/david/Documents/ai-workflow/ai-digest

# 启动服务器（后台运行）
./scripts/start_tracking_server.sh

# 检查服务器状态
curl http://localhost:8000
# 应返回: {"status": "ok", "message": "Tracking server is running"}
```

### 步骤 2: 生成 HTML 报告

```bash
# 生成报告
python src/main.py --days-back 1

# 报告位置
open output/weekly_report_2025-11-12.html
```

### 步骤 3: 与报告互动

1. **浏览内容**: 滚动页面，内容进入视野时自动记录
2. **点击链接**: 点击"🔗 阅读全文"时记录
3. **提供反馈**: 点击 👍/👎/➖ 按钮
4. **阅读时长**: 页面关闭时自动记录停留时间

### 步骤 4: 分析行为数据

```bash
# 分析最近 7 天的数据
python scripts/analyze_reading_behaviors.py

# 分析最近 30 天的数据
python scripts/analyze_reading_behaviors.py --days 30
```

### 步骤 5: 停止追踪服务器

```bash
./scripts/stop_tracking_server.sh
```

## 📊 追踪的数据字段

```json
{
  "report_id": "2025-11-12",
  "item_id": "abc123def456",
  "action": "click|view|feedback|read_time",
  "feedback_type": "like|dislike|neutral",
  "section": "must_read|headlines",
  "read_time": 120000,
  "url": "https://example.com/article",
  "timestamp": "2025-11-12T10:30:00Z"
}
```

## 📈 衡量标准实现

### ✅ 已实现指标

1. **阅读率** = 点击数 / 曝光数
   - 通过 `view` 和 `click` 行为计算

2. **点击率 (CTR)** = 点击数 / 浏览数
   - 衡量内容吸引力

3. **反馈率** = 反馈数 / 互动数
   - 衡量用户参与度

4. **内容偏好** = 👍 / (👍 + 👎)
   - 衡量内容质量

5. **阅读时长**
   - 衡量用户投入程度

## 🔧 下一步（Phase 1.2 & 1.3）

### Phase 1.2: 个性化权重自动调整
- [ ] 基于 `feedback_type` 调整内容类型权重
- [ ] 实现 EMA（指数移动平均）动态更新
- [ ] 自动降低低评分来源的权重

### Phase 1.3: 相关性重排
- [ ] 基于用户行为构建"用户画像向量"
- [ ] 实现 Re-ranking 算法
- [ ] 集成项目活跃度

## 🐛 故障排查

### 问题 1: 追踪服务器无法启动

```bash
# 检查端口是否被占用
lsof -i :8000

# 如果被占用，杀死进程
kill -9 <PID>

# 重新启动
./scripts/start_tracking_server.sh
```

### 问题 2: HTML 报告无法连接追踪服务器

```bash
# 确认服务器运行
curl http://localhost:8000

# 检查浏览器控制台
# 打开 F12 -> Console
# 查看是否有 CORS 错误
```

### 问题 3: 数据库找不到

```bash
# 确认数据库存在
ls -lh data/feedback.db

# 如果不存在，运行任意追踪即可自动创建
```

## 📝 技术实现细节

### 追踪原理

1. **Intersection Observer API**
   - 自动检测内容何时进入视野
   - 50% 可见时触发 `view` 事件

2. **sendBeacon API**
   - 页面关闭时发送阅读时长
   - 保证数据不丢失

3. **Fetch API**
   - 实时发送点击和反馈数据
   - 支持异步处理

### 数据库表结构

```sql
CREATE TABLE reading_behaviors (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    report_id TEXT,
    item_id TEXT,
    action TEXT,
    feedback_type TEXT,
    section TEXT,
    read_time INTEGER,
    url TEXT,
    metadata TEXT,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_reading_behaviors_item ON reading_behaviors(item_id, timestamp DESC);
CREATE INDEX idx_reading_behaviors_report ON reading_behaviors(report_id, timestamp DESC);
CREATE INDEX idx_reading_behaviors_action ON reading_behaviors(action, timestamp DESC);
```

## ✨ 完成状态

### Phase 1.1: 阅读行为追踪系统 ✅

- ✅ 追踪服务器启动/停止脚本
- ✅ API 端点 (`/api/track`)
- ✅ 数据库表和方法
- ✅ HTML 模板集成
- ✅ 行为分析工具
- ✅ 衡量标准实现
- ✅ 使用文档

**估计时间**: 1-2 天 → **实际时间**: 完成（代码已存在，优化和文档化）

---

_创建时间: 2025-11-12_
_负责人: AI Assistant_
_状态: ✅ 已完成_


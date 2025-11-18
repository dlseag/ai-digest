# 阅读行为追踪设计方案

## 🎯 问题分析

**挑战**：报告是静态 Markdown 文件，无法直接追踪用户行为。

**需求**：追踪用户点击、阅读时长、跳过等行为，为学习提供数据基础。

---

## 💡 可行方案对比

### 方案A：URL重定向追踪（推荐 ⭐⭐⭐⭐⭐）

**原理**：将所有外部链接改为追踪链接，点击时先记录行为，再跳转到原链接。

**实现**：
```python
# 生成追踪链接
def generate_tracking_url(original_url: str, item_id: str, report_id: str) -> str:
    """生成追踪URL"""
    base_url = "http://localhost:8000/track"  # 本地追踪服务
    params = {
        'item_id': item_id,
        'report_id': report_id,
        'redirect': original_url,
        'timestamp': datetime.now().isoformat(),
    }
    return f"{base_url}?{urlencode(params)}"
```

**优点**：
- ✅ 实现简单，只需修改链接生成
- ✅ 不改变报告格式
- ✅ 可以追踪所有点击行为
- ✅ 用户无感知（自动跳转）

**缺点**：
- ⚠️ 需要运行本地追踪服务
- ⚠️ 只能追踪点击，无法追踪阅读时长

**实施难度**：低（1-2天）

---

### 方案B：Web版本报告 + JavaScript追踪（推荐 ⭐⭐⭐⭐）

**原理**：生成HTML版本报告，使用JavaScript追踪行为。

**实现**：
```html
<!-- 在HTML报告中嵌入追踪脚本 -->
<script>
// 追踪点击
document.querySelectorAll('a[data-item-id]').forEach(link => {
    link.addEventListener('click', (e) => {
        const itemId = e.target.dataset.itemId;
        fetch('/api/track', {
            method: 'POST',
            body: JSON.stringify({
                action: 'click',
                item_id: itemId,
                timestamp: new Date().toISOString()
            })
        });
    });
});

// 追踪阅读时长（可见性API）
let startTime = Date.now();
document.addEventListener('visibilitychange', () => {
    if (document.hidden) {
        const readTime = Date.now() - startTime;
        fetch('/api/track', {
            method: 'POST',
            body: JSON.stringify({
                action: 'read_time',
                read_time: readTime,
                timestamp: new Date().toISOString()
            })
        });
    } else {
        startTime = Date.now();
    }
});

// 追踪滚动（判断是否阅读到某个位置）
let viewedItems = new Set();
const observer = new IntersectionObserver((entries) => {
    entries.forEach(entry => {
        if (entry.isIntersecting) {
            const itemId = entry.target.dataset.itemId;
            if (!viewedItems.has(itemId)) {
                viewedItems.add(itemId);
                fetch('/api/track', {
                    method: 'POST',
                    body: JSON.stringify({
                        action: 'view',
                        item_id: itemId,
                        timestamp: new Date().toISOString()
                    })
                });
            }
        }
    });
}, { threshold: 0.5 });
```

**优点**：
- ✅ 可以追踪点击、阅读时长、滚动位置
- ✅ 用户体验好（Web界面）
- ✅ 可以添加交互功能（点赞、收藏等）

**缺点**：
- ⚠️ 需要生成HTML版本
- ⚠️ 需要Web服务器
- ⚠️ 用户需要访问Web版本

**实施难度**：中（3-5天）

---

### 方案C：简单反馈机制（推荐 ⭐⭐⭐）

**原理**：在Markdown中添加简单的反馈标记，用户手动标记。

**实现**：
```markdown
- **{{ item.title }}** (⭐️ {{ item.personal_priority }}/10)
  - 🎯 对你的价值：{{ item.why_matters_to_you }}
  - 🔗 [阅读详情]({{ item.url }})
  - 💬 反馈：✅ 有用 | ❌ 无用 | ⏭️ 已跳过
```

用户编辑Markdown文件，添加反馈标记，系统定期扫描文件提取反馈。

**优点**：
- ✅ 最简单，无需额外服务
- ✅ 用户完全控制
- ✅ 可以表达复杂反馈

**缺点**：
- ⚠️ 依赖用户主动反馈
- ⚠️ 无法自动追踪
- ⚠️ 反馈率可能较低

**实施难度**：低（1天）

---

### 方案D：混合方案（最佳 ⭐⭐⭐⭐⭐）

**原理**：结合多种方案，提供多种追踪方式。

**实现**：
1. **URL重定向追踪**（自动，所有链接）
2. **简单反馈机制**（手动，关键内容）
3. **可选Web版本**（高级用户）

---

## 🚀 推荐实施方案：混合方案

### Phase 1: URL重定向追踪（立即实施）

**步骤**：

1. **创建追踪服务**（简单的HTTP服务器）
```python
# src/tracking/tracking_server.py
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
import json
from datetime import datetime

class TrackingHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        """处理追踪请求并重定向"""
        parsed = urlparse(self.path)
        params = parse_qs(parsed.query)
        
        # 记录行为
        behavior = {
            'item_id': params.get('item_id', [''])[0],
            'report_id': params.get('report_id', [''])[0],
            'action': 'click',
            'timestamp': datetime.now().isoformat(),
        }
        
        # 保存到数据库
        self.save_behavior(behavior)
        
        # 重定向到原始URL
        redirect_url = params.get('redirect', [''])[0]
        self.send_response(302)
        self.send_header('Location', redirect_url)
        self.end_headers()
    
    def save_behavior(self, behavior):
        """保存行为数据"""
        # 保存到SQLite数据库
        db = FeedbackDB()
        db.save_reading_behavior(behavior)
```

2. **修改报告生成器**，添加追踪链接
```python
# src/generators/report_generator.py
def _generate_tracking_url(self, original_url: str, item_id: str) -> str:
    """生成追踪URL"""
    report_id = self.report_id  # 当前报告ID
    tracking_base = "http://localhost:8000/track"
    params = {
        'item_id': item_id,
        'report_id': report_id,
        'redirect': original_url,
    }
    return f"{tracking_base}?{urlencode(params)}"
```

3. **在模板中使用追踪链接**
```jinja
{# templates/report_template.md.jinja #}
- 🔗 [阅读详情]({{ generate_tracking_url(item.url, item.id) }})
```

### Phase 2: 简单反馈机制（1周后）

在报告中添加反馈标记，用户可以在Markdown中标记：

```markdown
- **{{ item.title }}** (⭐️ {{ item.personal_priority }}/10)
  - 🔗 [阅读详情]({{ item.url }})
  - 💬 反馈：`<!-- ✅ 有用 -->` 或 `<!-- ❌ 无用 -->` 或 `<!-- ⏭️ 跳过 -->`
```

系统定期扫描报告文件，提取反馈：

```python
def extract_feedback_from_report(report_path: Path) -> List[dict]:
    """从报告文件中提取反馈"""
    content = report_path.read_text()
    
    # 使用正则表达式提取反馈
    pattern = r'<!--\s*([✅❌⏭️])\s*(有用|无用|跳过)\s*-->'
    matches = re.findall(pattern, content)
    
    feedbacks = []
    for emoji, action in matches:
        feedbacks.append({
            'action': action,
            'emoji': emoji,
            'timestamp': datetime.now().isoformat(),
        })
    
    return feedbacks
```

### Phase 3: Web版本（可选，2周后）

生成HTML版本报告，提供更丰富的追踪能力。

---

## 📊 数据收集示例

### 追踪到的数据

```json
{
  "item_id": "item_123",
  "report_id": "report_2025-11-12",
  "action": "click",
  "timestamp": "2025-11-12T20:30:00",
  "metadata": {
    "section": "must_read",
    "priority": 9,
    "source": "Hacker News"
  }
}
```

### 行为分析

```python
class BehaviorAnalyzer:
    """分析用户行为"""
    
    def analyze_click_patterns(self, days: int = 7):
        """分析点击模式"""
        behaviors = self.db.get_behaviors(days=days)
        
        # 分析哪些内容被点击了
        clicked_items = [b for b in behaviors if b['action'] == 'click']
        
        # 分析哪些内容被跳过了
        all_items = self.db.get_all_items(days=days)
        clicked_ids = {b['item_id'] for b in clicked_items}
        skipped_items = [item for item in all_items if item['id'] not in clicked_ids]
        
        return {
            'click_rate': len(clicked_items) / len(all_items),
            'preferred_sources': self._analyze_source_preferences(clicked_items),
            'preferred_topics': self._analyze_topic_preferences(clicked_items),
            'skip_patterns': self._analyze_skip_patterns(skipped_items),
        }
```

---

## 🛠️ 实施计划

### Week 1: URL重定向追踪

- [ ] 创建追踪服务器 (`src/tracking/tracking_server.py`)
- [ ] 创建行为数据库表
- [ ] 修改报告生成器，添加追踪链接
- [ ] 测试追踪功能

### Week 2: 简单反馈机制

- [ ] 在模板中添加反馈标记
- [ ] 实现反馈提取功能
- [ ] 集成到学习循环

### Week 3: 行为分析

- [ ] 实现 `BehaviorAnalyzer`
- [ ] 集成到学习引擎
- [ ] 生成行为报告

---

## 📈 预期效果

### 可追踪的行为

1. **点击行为** ✅
   - 哪些内容被点击了
   - 点击时间
   - 点击位置（必看/头条/附录）

2. **跳过行为** ✅
   - 哪些内容没有被点击
   - 跳过模式分析

3. **反馈行为** ✅（Phase 2）
   - 用户主动标记的有用/无用
   - 跳过标记

4. **阅读时长** ⚠️（需要Web版本）
   - 报告总阅读时长
   - 每个部分的阅读时长

---

## 🎯 推荐方案

**立即实施**：**方案A（URL重定向追踪）**

**理由**：
- ✅ 实现简单快速（1-2天）
- ✅ 可以追踪所有点击行为
- ✅ 用户无感知
- ✅ 为后续学习提供数据基础

**后续优化**：
- 添加简单反馈机制（用户主动反馈）
- 可选Web版本（高级追踪）

---

**创建日期**: 2025-11-12  
**状态**: 设计阶段  
**优先级**: P0


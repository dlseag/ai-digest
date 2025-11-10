# TLDR AI 邮件订阅转 RSS 设置指南

## 背景

TLDR AI (https://tldr.tech/ai) 只提供邮件订阅，没有公开 RSS feed。
为了将其集成到 ai-digest 中，我们需要将邮件订阅转换为 RSS。

## 推荐方案：Kill the Newsletter

### 步骤 1：创建邮件转 RSS 订阅

1. 访问 https://kill-the-newsletter.com/
2. 在输入框中输入：`TLDR AI`
3. 点击 **"Create feed"** 按钮
4. 你会获得：

   - **邮箱地址**：类似 `zv5vv6p5u4jiwj6e1lzx@kill-the-newsletter.com`
   - **RSS Feed URL**：类似 `https://kill-the-newsletter.com/feeds/zv5vv6p5u4jiwj6e1lzx.xml`

   💡 **重要**：请保存这两个信息，特别是 RSS Feed URL

### 步骤 2：订阅 TLDR AI

1. 访问 https://tldr.tech/ai
2. 输入刚才获得的邮箱地址（如 `zv5vv6p5u4jiwj6e1lzx@kill-the-newsletter.com`）
3. 点击 "Sign Up"

### 步骤 2.5：确认订阅（重要！）

TLDR AI 会发送一封确认邮件到你的 Kill the Newsletter 邮箱。你需要点击确认链接才能激活订阅。

**如何查看确认邮件：**

1. **方法 A：通过 RSS Feed 查看**

   - 在浏览器中打开你的 RSS Feed URL：
     ```
     https://kill-the-newsletter.com/feeds/zv5vv6p5u4jiwj6e1lzx.xml
     ```
   - 你会看到一封来自 TLDR 的确认邮件
   - 找到邮件中的确认链接（类似 "Click here to confirm your subscription"）
   - 点击链接完成确认

2. **方法 B：通过网页版查看**
   - 访问 Kill the Newsletter 首页：https://kill-the-newsletter.com/
   - 在底部的 "Existing Inbox" 输入框中输入你的 Feed ID：`zv5vv6p5u4jiwj6e1lzx`
   - 点击 "Open"
   - 你会看到所有收到的邮件列表
   - 打开 TLDR 的确认邮件，点击确认链接

**验证订阅成功：**

- 确认后，TLDR AI 会发送一封欢迎邮件
- 从第二天开始，你会每天收到 TLDR AI 的邮件
- 这些邮件会自动出现在你的 RSS Feed 中

### 步骤 3：更新 ai-digest 配置

编辑 `config/sources.yaml`：

```yaml
- name: TLDR AI
  url: https://kill-the-newsletter.com/feeds/YOUR_FEED_ID.xml # 替换为你的 RSS URL
  category: newsletter
  priority: 10
  note: 每日精选AI新闻摘要（最高优先级，通过 Kill the Newsletter 转换）
  enabled: true
```

### 步骤 4：测试采集

运行以下命令测试：

```bash
cd /Users/david/Documents/ai-workflow/ai-digest
python src/main.py --days-back 3
```

检查日志中是否成功采集到 TLDR AI 的内容。

## 备选方案

### Blogtrottr

如果 Kill the Newsletter 不可用，可以使用 Blogtrottr：

1. 访问 https://blogtrottr.com/
2. 输入订阅邮箱
3. 选择 RSS feed 频率
4. 获得 RSS URL

### 自建方案（高级）

如果需要更高的可控性，可以：

1. 使用 Gmail + Google Apps Script
2. 设置过滤器自动转发 TLDR AI 邮件
3. 用脚本解析邮件并生成 RSS

## 注意事项

1. **延迟**：邮件转 RSS 可能有 5-15 分钟延迟
2. **保留期**：Kill the Newsletter 免费版保留最近 30 封邮件
3. **隐私**：不要用个人邮箱，使用转发服务的临时邮箱
4. **备份**：定期检查 RSS feed 是否正常工作

## 故障排查

### 问题：RSS feed 返回 404

**原因**：Kill the Newsletter 的 feed ID 可能过期

**解决**：重新创建一个新的 inbox

### 问题：采集不到内容

**原因**：TLDR AI 邮件尚未到达

**解决**：

1. 检查 Kill the Newsletter 网页版是否收到邮件
2. 确认 TLDR AI 订阅已激活
3. 等待下一期 TLDR AI 发送（通常每日发送）

## 更新日期

2025-11-10

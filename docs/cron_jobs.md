# ⏱️ 定时任务配置指南

本指南说明如何通过 `cron`（或 macOS 的 `launchd`）自动运行 AI Digest：

- **每日简报 + 自学习**：整合采集→AI处理→学习→报告生成→（可选）邮件发送。

---

## 1. 使用 cron（Linux / macOS）

首先确保脚本可执行并存在日志目录（项目已默认提供）：

```bash
cd /Users/david/Documents/ai-workflow/ai-digest
chmod +x scripts/nightly_digest.sh
mkdir -p logs
```

然后编辑当前用户的 crontab：

```bash
crontab -e
```

追加以下任务（每日 19:00 执行一次完整流程）：

```cron
0 19 * * * /usr/bin/env bash /Users/david/Documents/ai-workflow/ai-digest/scripts/nightly_digest.sh
```

> 日志位于 `logs/nightly_digest.log`。脚本会自动加载 `.env`，优先使用 `uv` 或 `poetry`，若未配置 SMTP 会跳过邮件发送。

---

## 2. macOS 使用 launchd（可选）

若希望更符合 macOS 习惯，可使用 `launchd`，流程示例：

1. 创建 `~/Library/LaunchAgents/tech.david.ai-digest.digest.plist`
2. 填入如下模板（请按需调整路径和时间）：

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
  <dict>
    <key>Label</key>
    <string>tech.david.ai-digest.digest</string>
    <key>ProgramArguments</key>
    <array>
      <string>/usr/bin/env</string>
      <string>bash</string>
      <string>/Users/david/Documents/ai-workflow/ai-digest/scripts/nightly_digest.sh</string>
    </array>
    <key>StartCalendarInterval</key>
    <dict>
      <key>Hour</key>
      <integer>19</integer>
      <key>Minute</key>
      <integer>0</integer>
    </dict>
    <key>StandardOutPath</key>
    <string>/Users/david/Documents/ai-workflow/ai-digest/logs/nightly_digest.log</string>
    <key>StandardErrorPath</key>
    <string>/Users/david/Documents/ai-workflow/ai-digest/logs/nightly_digest.err.log</string>
    <key>WorkingDirectory</key>
    <string>/Users/david/Documents/ai-workflow/ai-digest</string>
  </dict>
</plist>
```

3. 载入任务：

```bash
launchctl load ~/Library/LaunchAgents/tech.david.ai-digest.digest.plist
```

---

## 3. 常见问题

| 问题 | 解决建议 |
| --- | --- |
| 任务没有执行 | 手动执行 `scripts/nightly_digest.sh` 检查是否报错；确认 `python/uv/poetry` 在 PATH 中 |
| 没有日志输出 | 确认 `logs` 目录存在，或检查 cron/launchd 写入权限 |
| 想要临时暂停 | `crontab -e` 注释对应行，或 `launchctl unload <plist>` |
| 需要自定义频率 | 调整 cron 表达式即可（例如 `0 */6 * * *` 表示每 6 小时一次） |

---

若后续启用邮件推送，请在 `.env` 中补充 SMTP 配置，脚本会自动检测。

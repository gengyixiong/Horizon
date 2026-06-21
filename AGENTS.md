# 仓库维护入口（先读）

本仓库不是上游 Horizon 的默认配置，而是 `gengyixiong/Horizon` 的定制部署：每天生成一份只关注人形机器人及紧密相关具身智能技术的中英双语日报，并发布到 GitHub Pages，同时向 Telegram 推送一条中文精简版。

任何维护者或 AI 助手收到仓库链接后，应先阅读本文件，再阅读 [HUMANOID_DIGEST.md](HUMANOID_DIGEST.md)。不要在未理解现有定制逻辑时，用上游示例配置覆盖本仓库。

## 当前生产环境

- 仓库：`https://github.com/gengyixiong/Horizon`
- 站点：`https://gengyixiong.github.io/Horizon/`
- 主分支：`main`
- Pages 发布分支：`gh-pages`
- 调度：每天 `08:00`，时区 `Asia/Shanghai`
- AI：DeepSeek `deepseek-chat`
- 输出：中文日报、英文日报，以及一条中文 Telegram 推送
- 新闻窗口：48 小时；新闻最多 15 条
- YouTube/Podcast 窗口：30 天；深度内容最多 3 条，不占新闻名额

## 必须保留的行为

1. 主题必须垂直于人形机器人。泛 AI、普通工业机械臂、自动驾驶、无人机和泛机器人内容，若没有明确的人形机器人联系，不应进入日报。
2. 中文和英文来源必须同时检索。中文日报会翻译英文来源，但不能因此删掉英文检索源。
3. 快讯与 YouTube/Podcast 深度内容位于同一篇日报的不同区块，使用独立数量上限。
4. YouTube 优先依据字幕摘要；无字幕时只能依据简介，并在页面标明摘要依据。
5. Podcast RSS 通常没有可靠播放量，不能声称按播放量排名。
6. Telegram 每天只推送中文版本的一条精简消息，并提供完整日报按钮；不要发送 15 条以上的逐条轰炸式消息。
7. 所有密钥只能存放在 GitHub Actions Secrets 或本地环境变量中，绝不能写入代码、配置、文档、测试数据或日志。

## 数据流与修改入口

```text
GitHub Actions
  -> data/config.github.json
  -> RSS / GitHub Releases / OSSInsight / YouTube
  -> AI 相关性评分与中英双语 enrichment
  -> 新闻与长访谈分别去重、排序和限额
  -> data/summaries + docs/_posts
  -> GitHub Pages + Telegram webhook
```

| 要修改的内容 | 首选文件 |
| --- | --- |
| 来源、查询词、时间窗、阈值、数量上限 | `data/config.github.json` |
| 人形机器人相关性边界和评分准则 | `src/ai/prompts.py` |
| 新闻/长访谈分流、去重和最终限额 | `src/orchestrator.py` |
| 日报区块、标题、摘要展示 | `src/ai/summarizer.py` |
| YouTube API、播放量、时长、字幕抽样 | `src/scrapers/youtube.py` |
| Podcast RSS 关键词预过滤 | `src/scrapers/rss.py` 与 `data/config.github.json` |
| 定时任务、Secrets、smoke test、Pages | `.github/workflows/daily-summary.yml` |
| Telegram 请求体与正文长度 | `data/config.github.json` 的 `webhook` |
| Telegram/通用 webhook 发送与日志脱敏 | `src/services/webhook.py` |
| 完整来源清单和配置理由 | `HUMANOID_DIGEST.md` |

`data/config.github.json` 是严格 JSON，不能写注释。所有“为什么这样配置”的说明应写在 `HUMANOID_DIGEST.md`；工作流和安全敏感逻辑附近保留简短英文代码注释。

## GitHub Actions Secrets

生产工作流需要以下 Secret 名称：

- `DEEPSEEK_API_KEY`
- `YOUTUBE_API_KEY`
- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_CHAT_ID`

只能检查 Secret 是否存在，不能尝试读取、输出或提交它的值。Telegram Token 会被拼入 Bot API URL；`src/services/webhook.py` 必须继续遮盖 URL 路径中的 Token。

## 验证要求

修改后至少执行：

```powershell
.\.venv\Scripts\python.exe -m pytest
```

如果改了 `data/config.github.json`，还要用 `src.models.Config` 做 schema 校验。推送 `main` 后按改动范围选择 GitHub Actions 手动测试：

- `youtube_smoke_only=true`：只验证 YouTube API，不调用 DeepSeek、不发布页面。
- `telegram_smoke_only=true`：只发送 Telegram 测试消息，不调用 DeepSeek、不发布页面。
- 两个 smoke 选项均为 `false`：运行完整日报，验证中英文页面、深度访谈区块、Pages 和 Telegram。

两个 smoke 选项不要同时设为 `true`。修改来源或筛选逻辑时，仅跑 smoke test 不算完成，必须再检查一次完整日报结果。

## 文档同步规则

只要发生以下变化，必须同步更新 `HUMANOID_DIGEST.md`：来源增删、检索词变化、阈值或限额变化、模型变化、Secrets 变化、工作流调度变化、Telegram 展示方式变化。若新增关键入口文件，也要更新本文件的“数据流与修改入口”表。


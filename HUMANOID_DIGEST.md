# 人形机器人日报维护说明

> 修改本 fork 的数据源、筛选逻辑或 GitHub Actions 前，请先阅读本文。本文是当前部署配置的维护入口；API Key 不得写入仓库。

## 当前用途

本 fork 部署在 `gengyixiong/Horizon`，用于生成只关注人形机器人及紧密相关具身智能技术的中英双语日报。

- 站点：<https://gengyixiong.github.io/Horizon/>
- 定时：每天北京时间 08:00
- 模型：DeepSeek `deepseek-chat`
- Secret：仓库 Actions Secret `DEEPSEEK_API_KEY`
- YouTube Secret：仓库 Actions Secret `YOUTUBE_API_KEY`
- Telegram Secrets：仓库 Actions Secrets `TELEGRAM_BOT_TOKEN` 和 `TELEGRAM_CHAT_ID`
- 新闻检索窗口：最近 48 小时
- 深度访谈检索窗口：最近 30 天
- 输出语言：简体中文和英文
- 新闻上限：15 条；深度访谈/Podcast 另设上限 3 条
- 发布分支：`gh-pages`

## 配置入口

| 文件 | 用途 |
| --- | --- |
| `data/config.github.json` | GitHub Actions 使用的数据源、模型、语言、阈值与来源配额 |
| `.github/workflows/daily-summary.yml` | 定时任务、Secret 映射、运行窗口与 Pages 发布 |
| `src/ai/prompts.py` | `CONTENT_ANALYSIS_SYSTEM` 中的人形机器人相关性硬门槛 |
| `src/scrapers/youtube.py` | YouTube 官方搜索、播放量/时长过滤、字幕抽样与降级逻辑 |
| `scripts/check_youtube_api.py` | 用一次最小长视频检索验证 YouTube Key 与 API 限制，不输出 Key |
| `scripts/check_telegram_api.py` | 向目标 Chat 发送一条测试消息；不输出 Bot Token 或 Chat ID |
| `docs/` | GitHub Pages 模板；生成的文章会发布到 `docs/_posts/` |

手动运行 `Daily Horizon Summary` 时可把 `youtube_smoke_only` 设为 `true`；此模式只检查 YouTube API，不调用 DeepSeek，也不发布日报。

把 `telegram_smoke_only` 设为 `true` 时，只发送 Telegram 测试消息，不调用 DeepSeek，也不发布日报。两个 smoke 选项不要同时启用。

`data/config.github.json` 是严格 JSON，不能加入 `//` 或 `#` 注释。配置意图统一记录在本文。

## Telegram 推送

- 每次日报只推送中文版本，避免中英文各发一条造成重复提醒。
- 推送内容是一条精简日报，并附带“阅读完整日报”按钮；完整文章仍在 GitHub Pages。
- Telegram `sendMessage` 的文本上限为 4096 字符，因此配置把日报正文安全限制在 3500 字符以内。
- 不设置 Telegram `parse_mode`。AI 生成的 Markdown 可能包含需要额外转义的字符；使用纯文本可以避免整条消息因格式解析失败而被拒绝。
- `TELEGRAM_BOT_TOKEN` 仅用于在工作流环境中构造 Bot API URL，`TELEGRAM_CHAT_ID` 仅注入请求体，两者都不得提交到仓库。
- `src/services/webhook.py` 会额外遮盖 Telegram URL 路径里的 Bot Token，防止它出现在日志或 dry-run 预览里。

## 英文来源与检索式

### Google News 英文检索

Feed 名称：`Humanoid Robotics News`

```text
"humanoid robot" OR "bipedal robot" OR "dexterous manipulation"
```

### 英文机器人媒体与论文

- The Robot Report：`https://www.therobotreport.com/feed/`
- IEEE Spectrum Robotics：`https://spectrum.ieee.org/feeds/topic/robotics.rss`
- arXiv Atom API：

```text
all:"humanoid robot" OR all:"bipedal locomotion" OR all:"whole-body control"
```

arXiv 按提交时间倒序，最多读取 30 条，再应用全局 48 小时窗口。

### GitHub Release

- `huggingface/lerobot`
- `isaac-sim/IsaacLab`
- `unitreerobotics/unitree_ros2`

### OSSInsight 开源趋势

- 语言：`All`、`Python`、`C++`
- 时间：`past_24_hours`
- 最低 Star：5
- 最多读取：20
- 关键词：

```text
humanoid, robot, robotics, embodied, bipedal, locomotion,
dexterous, manipulation, VLA
```

## 中文来源与检索式

Google News 中文 Feed：

```text
人形机器人 OR 具身智能 OR 双足机器人
```

中文 Feed 的分类为 `humanoid-zh`；英文 RSS/Atom Feed 的分类为 `humanoid-en`。

## 深度访谈 / Podcast

深度内容与快讯显示在同一篇日报，但使用独立区块和独立的 3 条上限，不占用 15 条新闻名额。

### YouTube 检索词

```text
"humanoid robot" interview
"humanoid robotics" podcast
"embodied AI" interview robotics
"bipedal robot" talk
"robot foundation model" interview
"dexterous manipulation" podcast
人形机器人 访谈
具身智能 深度对话
双足机器人 访谈
灵巧手 访谈
```

YouTube 规则：

- 最近 30 天、时长 20–180 分钟。
- 总播放量至少 2,000，或日均播放量至少 200。
- 每个检索词最多读取 8 条，去重后最多送 12 条给 AI，最终最多保留 3 条。
- 新闻使用 5.0 分门槛；长访谈因不一定具有突发性，使用独立的 4.0 分门槛。人形机器人相关性硬门槛不变。
- 排序先看 AI 相关性和内容质量，再以日均播放增速、总播放量打破同分。
- 尽可能抽取公开视频字幕，并在整段时间线上均匀取样，而不是只看开头。
- GitHub 托管 Runner 可能被 YouTube 字幕端点限制；失败时只根据视频简介摘要，并在页面明确标注“仅视频或节目简介”。
- YouTube Key 通过 `X-Goog-Api-Key` 请求头发送，避免出现在异常 URL 和日志中。

### Podcast RSS

- The Robot Report Podcast
- The Robot Brains Podcast
- Lex Fridman Podcast
- NVIDIA AI Podcast

Podcast 使用 30 天窗口，并先按 `humanoid`、`bipedal`、`whole-body`、`dexterous hand`、人形机器人产品名和主要公司名预过滤。不要加入泛化的 `robot`、`robotics` 或 `embodied` 单词，否则会混入普通机械臂内容。Podcast RSS 通常不公开真实播放量，因此不声称按播放量排名；若无公开字幕，摘要只基于节目简介。

## 筛选和配额语义

- AI 相关性阈值：5.0。
- 中文来源组上限：8 条。
- 英文来源组上限：8 条。
- GitHub/OSSInsight 等未带 RSS 分类的开源来源上限：4 条。
- 新闻全局上限：15 条；长访谈/Podcast 独立上限：3 条。
- 这些数值是上限，不是保底数量；没有足够的高相关英文内容时，不会用低质量内容凑数。
- 同一事件的中英文报道会进行语义去重，因此最终来源数量不等于抓取数量。
- 中文日报会把英文内容翻译成中文标题和摘要；来源行仍显示英文 Feed 名称。

## 人形机器人相关性边界

AI 评分优先保留：

- 人形机器人平台、公司、产品发布和真实部署
- 双足运动、平衡、全身控制和运动规划
- 灵巧手、灵巧操作、遥操作和人类动作数据
- 用于人形机器人的机器人基础模型、VLA 和世界模型
- 仿真、数据集、训练方法、安全、制造、供应链、融资和监管

以下内容如果没有明确的人形机器人应用，应评为 0–2 分：泛 AI、普通工业机械臂、自动驾驶、无人机、通用计算机视觉。

## 修改与验证清单

1. 修改 `data/config.github.json` 后，用 `src.models.Config` 做 schema 校验。
2. 新增 RSS/Atom Feed 前，先验证 HTTP 200、内容类型和发布日期字段。
3. 修改相关性范围时，同步更新 `src/ai/prompts.py` 与本文。
4. 不得把 DeepSeek Key 或其他凭据写入代码、日志或文档。
5. 推送 `main` 后，手动运行 `Daily Horizon Summary`。
6. 确认 `Run Horizon` 和 `Deploy to GitHub Pages` 均成功。
7. 验证中文、英文文章均生成，并统计实际来源分布与主题相关性。
8. 检查“深度访谈 / Podcast”区块是否显示时长、播放量和摘要依据；没有字幕时不得把简介摘要描述成完整访谈摘要。

## 给后续维护者

收到本仓库链接后，先读取本文、`data/config.github.json`、工作流和 `CONTENT_ANALYSIS_SYSTEM`，再修改。不要根据上游 Horizon 默认配置覆盖本 fork 的人形机器人专刊设置。

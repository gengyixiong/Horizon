# 人形机器人日报维护说明

> 修改本 fork 的数据源、筛选逻辑或 GitHub Actions 前，请先阅读本文。本文是当前部署配置的维护入口；API Key 不得写入仓库。

## 当前用途

本 fork 部署在 `gengyixiong/Horizon`，用于生成只关注人形机器人及紧密相关具身智能技术的中英双语日报。

- 站点：<https://gengyixiong.github.io/Horizon/>
- 定时：每天北京时间 08:00
- 模型：DeepSeek `deepseek-chat`
- Secret：仓库 Actions Secret `DEEPSEEK_API_KEY`
- YouTube Secret：仓库 Actions Secret `YOUTUBE_API_KEY`
- 检索窗口：最近 48 小时
- 输出语言：简体中文和英文
- 最终上限：15 条
- 发布分支：`gh-pages`

## 配置入口

| 文件 | 用途 |
| --- | --- |
| `data/config.github.json` | GitHub Actions 使用的数据源、模型、语言、阈值与来源配额 |
| `.github/workflows/daily-summary.yml` | 定时任务、Secret 映射、运行窗口与 Pages 发布 |
| `src/ai/prompts.py` | `CONTENT_ANALYSIS_SYSTEM` 中的人形机器人相关性硬门槛 |
| `scripts/check_youtube_api.py` | 用一次最小长视频检索验证 YouTube Key 与 API 限制，不输出 Key |
| `docs/` | GitHub Pages 模板；生成的文章会发布到 `docs/_posts/` |

手动运行 `Daily Horizon Summary` 时可把 `youtube_smoke_only` 设为 `true`；此模式只检查 YouTube API，不调用 DeepSeek，也不发布日报。

`data/config.github.json` 是严格 JSON，不能加入 `//` 或 `#` 注释。配置意图统一记录在本文。

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

## 筛选和配额语义

- AI 相关性阈值：5.0。
- 中文来源组上限：8 条。
- 英文来源组上限：8 条。
- GitHub/OSSInsight 等未带 RSS 分类的开源来源上限：4 条。
- 全局最终上限：15 条。
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

## 给后续维护者

收到本仓库链接后，先读取本文、`data/config.github.json`、工作流和 `CONTENT_ANALYSIS_SYSTEM`，再修改。不要根据上游 Horizon 默认配置覆盖本 fork 的人形机器人专刊设置。

# 🔭 AppWatch · 券商 App 竞品追踪

> 追踪主要券商 App 在 App Store 上的版本更新节奏、更新日志、评分变化和财经榜排名，每天自动更新

**🌐 在线访问：[https://climb0516.github.io/appstore-tracker/](https://climb0516.github.io/appstore-tracker/)**

---

## 追踪的 App

| 港区 | 美区 |
|---|---|
| Longbridge、LongPort、富途牛牛、Tiger Trade、Webull、盈立 uSmart、雪球、IBKR Mobile | moomoo、Webull、Robinhood、Tiger Trade、IBKR Mobile |

列表在 `scraper.py` 开头的 `APPS` 里，增删直接改这一处（App ID 可以从 App Store 链接里的 `id` 后面那串数字拿到）。

---

## 功能

- **总览**：每个 App 一张卡片，显示当前版本、距上次更新天数（7 天内高亮）、评分与人数、财经榜排名、最新更新说明，以及排名 / 评分人数的迷你走势线
- **更新时间线**：所有 App 的版本更新按时间排列，带完整更新说明，可按 App 筛选
- **对比表**：版本、距上次更新、评分、评分人数、榜单排名、包体大小、最低系统版本横向对比，点表头排序
- **财经榜**：港区 / 美区财经类免费榜前 100，追踪的 App 高亮，显示较前一天的升降
- 港区 / 美区切换、全文搜索（`⌘K` / `Ctrl K`）、深浅色主题、手机适配
- 右上角：↻ 重新读取数据，⚡ 跳转 GitHub Actions 手动触发抓取

---

## 数据来源

| 接口 | 用途 |
|---|---|
| `itunes.apple.com/lookup` | 版本号、上线时间、更新说明、评分、评分人数、包体大小、最低系统版本、图标 |
| `itunes.apple.com/{hk,us}/rss/topfreeapplications/genre=6015` | 财经类免费榜前 100 |

均为苹果公开接口，不需要密钥。

**注意**：App Store 只提供**当前版本**，查不到历史版本。所以版本历史、评分走势、排名走势都是从开始追踪那天起，每天记录一次慢慢累积的。

---

## 技术架构

```
GitHub Actions（每天 09:00 / 手动 / 修改爬虫后 push）
  ↓ python scraper.py（只用标准库，无需安装依赖）
  ↓ 查询 App 详情 + 财经榜 → 版本变化时追加历史记录，每天追加一条快照
  ↓ 写入 data.json 并 commit
       ↓
GitHub Pages（index.html）
  ↓ 前端读取同目录 data.json 渲染
```

- 版本记录每个 App 最多保留 60 条，每日快照最多保留 365 天
- 某个 App 本次没查到时沿用上一次的数据，页面上标注「旧数据」
- 每次运行都会产生提交，仓库保持活跃，定时任务不会因 60 天无活动被 GitHub 停用

本地预览：

```
python3 scraper.py
python3 -m http.server
```

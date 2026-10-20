# 🔭 AppWatch · 券商 App 竞品追踪

> 券商 App 竞品画像：每个 App 的定位、主要功能、突出卖点、用户评价、媒体评价和市场可见度，外加版本更新节奏与财经榜排名，每天自动更新

**🌐 在线访问：[https://climb0516.github.io/appstore-tracker/](https://climb0516.github.io/appstore-tracker/)**

---

## 追踪的 App

| 港区 | 美区 |
|---|---|
| Longbridge、LongPort、富途牛牛、Tiger Trade、Webull、盈立 uSmart、雪球、IBKR Mobile | moomoo、Webull、Robinhood、Tiger Trade、IBKR Mobile |

列表在 `scraper.py` 开头的 `APPS` 里，增删直接改这一处（App ID 可以从 App Store 链接里的 `id` 后面那串数字拿到）；新增 App 时同时在 `NEWS` 里加上它的媒体搜索词和自家渠道名。

---

## 视图

| 视图 | 内容 |
|---|---|
| **总览** | 每个 App 一张卡片：当前版本、距上次更新、评分、财经榜排名、最新更新说明、走势线，以及近期口碑、最多吐槽、功能数、报道数 |
| **竞品画像** | 单个 App 的全部维度：定位、主要功能标签、突出卖点（商店描述原文）、商店截图、用户评价（星级分布 / 差评主题 / 版本口碑 / 最新差评好评）、媒体评价、搜索可见度、最近版本 |
| **功能矩阵** | 所有 App 的功能标签横向对比（市场 / 产品 / 交易 / 工具 / 费用 五组共 26 项） |
| **用户评价** | 各 App 近期口碑卡片、差评主题对比热力表、评论流（差评 / 中评 / 好评筛选，可搜索） |
| **媒体报道** | 近 30 天第三方媒体报道，可只看评测 / 对比类文章 |
| **排名** | App Store 关键词搜索排名表 + 财经类免费榜前 100（较前一天升降） |
| **更新** | 所有 App 的版本更新时间线，带完整更新说明 |
| **对比表** | 版本、评分、评分人数、榜单排名、包体、最低系统等横向对比，点表头排序 |

港区 / 美区切换、全文搜索（`⌘K` / `Ctrl K`）、深浅色主题、手机适配；右上角 ↻ 重新读取数据，⚡ 跳转 GitHub Actions 手动触发抓取。

---

## 数据来源

| 来源 | 用途 |
|---|---|
| `itunes.apple.com/lookup` | 版本、更新说明、评分、包体、最低系统、**商店描述、截图** |
| `itunes.apple.com/{hk,us}/rss/topfreeapplications/genre=6015` | 财经类免费榜前 100 |
| `itunes.apple.com/{hk,us}/rss/customerreviews` | **用户评论**（每个 App 每个地区最近 500 条，每天累积，最多保留 600 条） |
| `itunes.apple.com/search` | **关键词搜索排名**（结果顺序近似真机 App Store 搜索） |
| Google News RSS | **媒体报道**（近 30 天，排除各家自己的资讯频道和官网） |

均为公开接口，不需要密钥。

**说明与限制**

- 功能标签、差评主题都是**关键词规则**自动识别的（规则在 `scraper.py` 的 `FEATURES`、`TOPICS`），会有误判和漏判，可以持续调整
- 功能和卖点来自各家**自己的商店描述**，代表「他们想让用户看到什么」，「没提到」不等于「不支持」
- App Store 只提供当前版本，版本历史、评分 / 排名走势从开始追踪那天起每天累积
- 评论接口限流很严，爬虫串行抓取、每页间隔 2.5 秒；某天被限流只拿到部分评论时，之后每天会继续补抓
- 下载量、收入、日活等数据只有付费服务（Sensor Tower、data.ai）才有，不在本站范围内

---

## 技术架构

```
GitHub Actions（每天 09:00 / 手动 / 修改爬虫后 push）
  ↓ python scraper.py（只用标准库，无需安装依赖，单次约 6 分钟）
  ↓ App 详情 + 财经榜 + 关键词排名 + 评论 + 媒体报道
  ↓ 识别功能标签 / 卖点 / 差评主题，计算评论统计
  ↓ 写入 data.json（主数据）、reviews.json（评论原文）并 commit
       ↓
GitHub Pages（index.html）
  ↓ 首页读取 data.json；进入画像 / 用户评价视图时才加载 reviews.json
```

- 某个来源本次失败时沿用上一次的数据，页面上标注「旧数据」
- 每次运行都会产生提交，仓库保持活跃，定时任务不会因 60 天无活动被 GitHub 停用

本地预览：

```
python3 scraper.py
python3 -m http.server
```

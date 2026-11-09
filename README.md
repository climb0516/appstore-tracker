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

## 技术架构

```
GitHub Actions（每天 09:00 北京时间定时 / 手动 dispatch / push 修改了 scraper.py 或 workflow）
  ↓ python scraper.py（Python 3.12，只用标准库，无需安装依赖）
  ↓ 按地区（港区 hk / 美区 us）依次抓取：
  ↓   财经免费榜 → 关键词搜索排名 → App 详情（lookup 一次查完）
  ↓   → 评论（串行，单独线程）‖ 媒体报道（Google News，并行线程）
  ↓ 识别功能标签 / 卖点 / 定位语 / 差评主题，计算评论统计、榜单升降
  ↓ 与上次的 data.json / reviews.json 合并（版本历史、每日快照、评论、报道累积）
  ↓ 写入 data.json（主数据）+ reviews.json（评论原文）
  ↓ git commit "data: snapshot <北京时间>" 并 push
       ↓
GitHub Pages（index.html）
  ↓ 首页读取 data.json；进入画像 / 用户评价视图或打开评论详情时才加载 reviews.json
  ↓ 8 个视图（总览 / 竞品画像 / 功能矩阵 / 用户评价 / 媒体报道 / 排名 / 更新 / 对比表）
  ↓ 详情抽屉 #/item/<类型>/<id> + 列表页 #/list/<key>（通用组件 kit）
```

- 每个来源用 `run()` 包一层，失败只记录到 `sources`（ok / error / count），不影响其它来源
- 某个来源本次失败时沿用上一次的数据：榜单、关键词排名直接取旧值；App 详情没返回时沿用上次的 App 记录并标 `stale: true`，页面上标注「旧数据」（评论和报道照常更新）

---

## 数据来源

| 来源 | 方式 | 每次条数 / 范围 | 备注 |
|---|---|---|---|
| `itunes.apple.com/lookup?id=…&country={hk,us}` | 接口（JSON） | 每个地区 1 次请求查完 `APPS` 里全部 App | 版本、更新说明、评分、评分人数、包体、最低系统、语言数、上架日期、**商店描述、截图（最多 10 张）**，见 `lookup()` |
| `itunes.apple.com/{hk,us}/rss/topfreeapplications/limit=100/genre=6015/json` | 接口（RSS JSON） | 每个地区财经类免费榜前 100 | `FINANCE_GENRE = 6015`，见 `chart()` |
| `itunes.apple.com/search?term=…&entity=software&limit=100` | 接口（JSON） | 港区 8 个、美区 5 个关键词，每个取前 100 名 | **关键词搜索排名**，结果顺序近似真机搜索；关键词在 `KEYWORDS`，每次请求间隔 1 秒，见 `keyword_ranks()` |
| `itunes.apple.com/{hk,us}/rss/customerreviews/page=N/id=…/sortby=mostrecent/json` | 接口（RSS JSON） | 每个 App 每个地区最多 10 页 × 50 = 500 条（`REVIEW_PAGES`），累积后保留 600 条（`REVIEW_KEEP`） | **用户评论**，见 `reviews()` / `review_page()` |
| Google News RSS（`news.google.com/rss/search`） | RSS | 每个 App 搜 2 次（原搜索词 + 评测类追加词），限定近 30 天，每个 App 保留 30 条（`NEWS_KEEP`） | **媒体报道**，港区 `zh-HK`、美区 `en-US`；搜索词和自家渠道在 `NEWS`，见 `news()` |

均为公开接口，不需要密钥。

**增删追踪的 App**：改 `scraper.py` 开头的 `APPS`（地区 → `(App Store ID, 简称)` 列表），App ID 是 App Store 链接里 `id` 后面那串数字；同时在 `NEWS` 里按 `"地区:App ID"` 加上它的媒体搜索词和要排除的自家渠道名（没配 `NEWS` 的 App 不抓报道）。

**增删关键词**：改 `KEYWORDS`（`hk` / `us` 两组），搜索名次上限是 `SEARCH_LIMIT = 100`。

**说明与限制**

- 功能标签、差评主题都是**关键词规则**自动识别的（规则在 `scraper.py` 的 `FEATURES`、`TOPICS`），会有误判和漏判，可以持续调整
- 功能和卖点来自各家**自己的商店描述**，代表「他们想让用户看到什么」，「没提到」不等于「不支持」
- App Store 只提供当前版本，版本历史、评分 / 排名走势从开始追踪那天起每天累积
- 评论接口限流很严，爬虫串行抓取、每页间隔 2.5 秒；某天被限流只拿到部分评论时，之后每天会继续补抓
- 下载量、收入、日活等数据只有付费服务（Sensor Tower、data.ai）才有，不在本站范围内

---

## 数据处理规则

**功能标签** `features(desc, history, tracked_since, region)`

- 规则表 `FEATURES`：`(id, 分组, 名称, 正则)`，5 组共 26 项：市场（港股 / 美股 / A 股 / 日股 / 新加坡股）、产品（加密货币 / 期权 / 期货 / 基金 / 债券 / 外汇 / 新股认购）、交易（夜盘/24 小时 / 碎股 / 条件单/止盈止损 / 融资/保证金 / 模拟交易 / 定投/月供）、工具（AI 助手 / 社区 / Level 2 行情 / 资讯/研报 / 选股器 / 专业图表）、费用（免佣/0 佣金 / 现金管理/理财）
- 正则示例：夜盘 `夜盤|夜盘|24\s*小時|5\s*[x×]\s*24|24/5|24-hour|overnight`；条件单 `條件單|条件单|止盈|止損|stop[- ]loss|take[- ]profit|trailing stop`；免佣 `免佣|0\s*佣金|零佣金|commission[- ]free|zero commission`
- 识别顺序：先按日期从旧到新扫历次**更新说明**，命中则记 `src: "notes"` 和首次出现的版本日期 / 版本号；再扫**商店描述**，命中记 `src: "desc"`、`since` 为开始追踪日期
- 特例：美区 App 描述里只要出现 `\bstocks?\b` 就默认算「美股」

**卖点与定位语**

- `highlights(desc, limit=12)`：逐行匹配列表符号 `BULLET`（`1.` / `1、` / `a)` / `•●▪◆★✓➤▶·-–—*` / `【…】` 等开头），去掉符号后长度 6–160 字的行作为卖点，去重，最多 12 条
- `intro(desc, n=220)`：取描述里第一个长度 ≥ 20 字、不是列表行、且不命中 `LEGAL`（订阅价格 `/月`、`訂閱`、`auto-renew`、`privacy`、`terms`、`免責`、`風險`、`member SIPC`、`FINRA`、`證監會` 等）的段落，截断到 220 字

**差评主题** `topics_of(text)` / `review_stats(revs, now)`

- 只在 1–2 星评论（标题 + 正文）里统计，规则表 `TOPICS` 共 11 个主题，繁 / 简 / 英三语：
  - 闪退卡顿 `閃退|闪退|崩潰|卡頓|卡死|好卡|很卡|慢|lag|crash|freez|frozen|slow|bug`
  - 耗电发热 `耗電|發熱|發燙|電量|battery|heat|hot\b|drain`
  - 登录验证 `登入|登录|驗證|密碼|log ?in|sign ?in|2fa|otp|verification|password|locked out`
  - 行情数据 `行情|報價|延遲|數據|圖表|quote|delay|data|chart|price`
  - 入金出金 `入金|出金|存款|提款|轉賬|資金|deposit|withdraw|transfer|fund`
  - 费用佣金 `收費|佣金|手續費|費用|fee|commission|charge|subscription`
  - 客服 `客服|服務態度|support|customer service|help ?desk|no response|回覆`
  - 下单交易 `下單|成交|落單|交易失敗|order|execution|filled|trade fail`
  - 界面更新 `介面|界面|改版|更新後|新版|舊版|UI\b|interface|layout|update|redesign`
  - 开户审核 `開戶|审核|KYC|account (opening|approval)|verify (my )?identity`
  - 广告推送 `廣告|推送|通知太多|\bads?\b|\badvert|spam|too many notifications|push notification`
  - （以上为节选，完整正则以 `scraper.py` 为准；一条评论可命中多个主题）
- 统计窗口：近 90 天（`RECENT_DAYS`）的评论 ≥ 20 条时只用近期样本（`window: "recent"`），否则用全部评论（`window: "all"`）
- 输出：星级分布 `dist`、均分 `avg`、差评数 `neg`、各主题差评数 `topics`、版本口碑 `versions`（每个版本至少 3 条评论才列出，按该版本最新评论时间倒序，最多 10 个；含条数、均分、差评数）

**去重与合并**

- 评论：按评论 `id` 与上次 `reviews.json` 合并，新的覆盖旧的，按时间倒序保留 600 条
- 评论抓取防限流 `review_page()`：苹果被限流时不报错而是返回空列表 / 非 JSON，所以空页退避重试 3 次（间隔 5 / 10 / 15 秒），确认为空才认为没有更多；某页不足 50 条即停止翻页
- 媒体报道：标题去掉末尾的「 - 来源名」后，取小写、去掉非字母数字字符的前 60 位作为去重键；与上次结果合并后只保留近 30 天（`NEWS_DAYS`），按时间倒序最多 30 条
- 过滤自家渠道：报道来源名包含 `NEWS` 里该 App 的自家渠道词（如 Longbridge / 長橋 / 长桥 / LongPort，富途 / Futu / moomoo）即丢弃
- 评测类识别：标题命中 `REVIEW_HINT`（`review|評測|评测|評價|比較|\bvs\.?\b|pros|cons|best .*app|哪個好|點揀|测评`）标 `review: true`
- 搜索词：美区在原词后追加 ` review`，港区追加 ` 評價 OR 評測 OR 比較`，两次结果合并

**版本历史与快照**

- 当前版本号与上次记录的最新版本不同时，在 `history` 头部插入一条（版本、发版时间、更新说明、首次看到时间），保留 60 条（`HISTORY_KEEP`）；更新说明截断 1500 字（`NOTES_MAX`），商店描述截断 4000 字（`DESC_MAX`），评论正文截断 400 字（`REVIEW_MAX`）
- 每日快照 `daily`：评分、评分人数、财经榜排名、各关键词名次；同一天多次运行只保留最后一次，保留 365 天（`DAILY_KEEP`）
- 财经榜升降：`charts.<地区>.days` 记录每天榜单的 App ID 顺序，只保留最近 3 天；`prev_rank` 取今天之前最近一天的名次

---

## 数据结构

`data.json` 顶层：

```
{
  "updated":  "2026-10-22T12:47:58+08:00",  // 北京时间，每次运行都变
  "regions":  [{ "id": "hk", "name": "港区" }, { "id": "us", "name": "美区" }],
  "features": [{ "id", "group", "name" }],   // 26 项功能标签定义
  "topics":   [{ "id", "name" }],            // 11 个差评主题定义
  "keywords": { "hk": { "港股": { "<App ID>": 名次或 null } }, "us": { … } },
  "sources":  [{ "id", "name", "ok", "error", "count" }],  // 各来源本次抓取状态
  "apps":     [ … ],                         // 见下
  "charts":   { "hk": { "entries", "days", "prev_day", "updated" }, "us": { … } }
}
```

单个 App（`apps[]`）：

```
{
  "key": "hk:1470042146", "region": "hk", "id": 1470042146,
  "name": "Longbridge", "title": "商店全名", "seller": "开发商",
  "icon", "url",
  "version", "version_date", "notes",          // 当前版本、发版时间、更新说明
  "rating", "rating_count", "size", "min_os", "languages", "released",
  "rank",                                       // 财经免费榜名次，不在榜为 null
  "tracked_since", "stale",                     // 开始追踪日期；本次是否沿用旧数据
  "intro", "description", "highlights", "screenshots",
  "features":     { "<功能 id>": { "src": "notes|desc", "since", "version"? } },
  "review_stats": { "total", "window", "sample", "avg", "dist", "neg", "topics", "versions", "oldest", "newest" },
  "news":    [{ "title", "source", "url", "date", "review" }],
  "history": [{ "version", "date", "notes", "seen" }],
  "daily":   [{ "d": "2026-10-22", "rating", "count", "rank", "kw": { "港股": 5, … } }]
}
```

财经榜单条（`charts.<地区>.entries[]`）：

```
{ "rank": 1, "id": 6480176219, "name", "seller", "icon", "url", "prev_rank": 1 }
```

`reviews.json`（评论原文，单独存放以减小首页加载量，紧凑 JSON 无缩进）：

```
{
  "updated": "…",
  "apps": {
    "hk:1470042146": [{ "id", "rating", "version", "date", "author", "title", "content", "votes" }]
  }
}
```

---

## 前端

**详情抽屉 + 列表页（通用组件 kit）**：电脑上从右侧滑出，手机上从底部升起；地址分别是 `#/item/<类型>/<id>` 和 `#/list/<key>`，分享链接可以直接打开对应详情或列表。条目已经下榜 / 过期 / 链接来自旧数据时，弹出「这条内容已不在当前数据里」的提示，而不是什么都不显示。

列表页是新开的一层：从右侧滑入盖在首页上，返回时滑走；首页一直在底下不动，滚动位置不变。在列表里点开的详情盖在这一层之上；直接打开列表链接时不播进场动画；安卓手机可从左边缘右滑返回（iOS 用系统自带手势）。

| 条目类型 | 地址 | 内容 |
|---|---|---|
| `app` | `#/item/app/<地区:App ID>` | 追踪 App 概况、排名 / 评分人数走势、最新更新说明、简介与卖点、商店截图、差评主题、最近报道 |
| `rank` | `#/item/rank/<地区:App ID>` | 财经榜里未追踪的 App：当前 / 昨日排名、每日排名、同开发商上榜、榜单前后 |
| `news` | `#/item/news/<App key>/<下标>` | 媒体报道，附该 App 其它报道 |
| `review` | `#/item/review/<App key>/<评论 ID>` | 评论全文，附同版本其它评论 |
| `version` | `#/item/version/<App key>/<版本号>` | 版本更新说明、该版本评论口碑、其它版本 |

| 列表 key | 地址 | 内容 |
|---|---|---|
| `reviews` | `#/list/reviews[/<App key>]` | 用户评论，可按星级筛选（全部 / 差评 1–2★ / 好评 4–5★ / 单个星级），排序：最新 / 最有用 / 评分低→高 / 评分高→低 |
| `news` | `#/list/news[/<App key>]` | 媒体报道，可只看评测 / 对比 |
| `versions` | `#/list/versions[/<App key>]` | 版本记录 |

列表页每页 30 条，点「加载更多」继续；不带 App key 时是当前地区全部 App。

**本项目特有**

- 8 个视图用单段 hash 切换（`#overview` / `#profile` / `#features` / `#reviews` / `#media` / `#chart` / `#timeline` / `#compare`）
- `reviews.json` 按需懒加载：只有进入画像 / 用户评价视图、或打开评论 / 版本详情时才请求（`ensureReviews()`）
- 地区、视图、排序、主题偏好存在 `localStorage`（键前缀 `aw.`）
- 打开评论列表页 `#/list/reviews` 时也会按需加载评论
- 数据请求带时间戳并 `cache: 'no-store'`，右上角 ↻ 重新读取，⚡ 跳转 GitHub Actions 手动触发
- 外部图片统一加 `referrerpolicy="no-referrer"`

---

## 本地运行

```
python3 scraper.py
python3 -m http.server
```

- 依赖：Python 3（CI 用 3.12），只用标准库，无需 `pip install`
- 环境变量：无，不需要任何密钥
- 爬虫会覆盖当前目录下的 `data.json` 和 `reviews.json`；评论串行抓取 + 间隔 2.5 秒，单次运行耗时较长（具体耗时未确认）
- 浏览器打开 `http://localhost:8000`（`http.server` 默认端口）

---

## 自动更新机制

| 触发方式 | 时机 |
|---|---|
| GitHub Actions 定时任务（cron `0 1 * * *`） | 每天 09:00 北京时间 |
| push 到 main 分支 | 仅当改动了 `scraper.py` 或 `.github/workflows/scrape.yml` |
| GitHub Actions 手动 dispatch | 按需触发（页面右上角 ⚡ 可跳转） |

- 工作流 `.github/workflows/scrape.yml`：`ubuntu-latest` + Python 3.12，运行 `python scraper.py` 后 `git add data.json reviews.json`，有变化才提交，提交信息 `data: snapshot <北京时间>`
- 并发组 `scrape`，不取消正在运行的任务（`cancel-in-progress: false`），避免两次抓取同时写文件
- **心跳**：`data.json` 的 `updated` 字段每次运行都会变化（每天还会新增一条 `daily` 快照），所以每次运行都会产生提交，仓库保持活跃
- GitHub 会在仓库 **60 天无提交** 后自动停用定时任务；上面的心跳机制正是为了避免这种情况。万一被停用，到仓库 Actions 页面重新启用即可

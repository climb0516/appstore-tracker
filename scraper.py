#!/usr/bin/env python3
"""AppWatch scraper — 券商 App 竞品画像：App Store 版本 / 评分 / 排名、商店描述与卖点、用户评论、媒体报道、关键词排名。
输出 data.json（主数据）和 reviews.json（评论原文）。仅依赖 Python 标准库。"""
import html, json, re, time, urllib.parse, urllib.request
import xml.etree.ElementTree as ET
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone, timedelta
from email.utils import parsedate_to_datetime
from pathlib import Path

OUT     = Path(__file__).with_name("data.json")
REV_OUT = Path(__file__).with_name("reviews.json")
CST = timezone(timedelta(hours=8))
UA  = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
                     "(KHTML, like Gecko) Chrome/126.0 Safari/537.36"}
HISTORY_KEEP = 60     # 每个 App 保留的版本记录数
DAILY_KEEP   = 365    # 每个 App 保留的每日快照天数
NOTES_MAX    = 1500   # 更新说明最长字数
DESC_MAX     = 4000   # 商店描述最长字数
REVIEW_PAGES = 10     # 评论接口最多 10 页 × 50 条
REVIEW_KEEP  = 600    # 每个 App 保留的评论条数（新的在前）
REVIEW_MAX   = 400    # 评论正文最长字数
RECENT_DAYS  = 90     # 「近期」评论统计窗口
NEWS_DAYS    = 30     # 媒体报道保留天数
NEWS_KEEP    = 30     # 每个 App 保留的报道条数

REGIONS = [("hk", "港区"), ("us", "美区")]

# 追踪的 App：地区 → [(App Store ID, 简称)]。增删直接改这里
APPS = {
    "hk": [
        (1470042146, "Longbridge"),
        (1605041188, "LongPort"),
        (592031984,  "富途牛牛"),
        (1023600494, "Tiger Trade"),
        (1557435421, "Webull"),
        (1463024118, "盈立 uSmart"),
        (492180369,  "雪球"),
        (454558592,  "IBKR Mobile"),
    ],
    "us": [
        (1440255819, "moomoo"),
        (1179213067, "Webull"),
        (938003185,  "Robinhood"),
        (1023600494, "Tiger Trade"),
        (454558592,  "IBKR Mobile"),
    ],
}
FINANCE_GENRE = 6015

# 媒体报道：每个 App 的搜索词，以及要排除的自家渠道（来源名包含这些词的视为官方发布，不算媒体评价）
NEWS = {
    "hk:1470042146": ('長橋證券 OR Longbridge',            ["Longbridge", "長橋", "长桥", "LongPort"]),
    "hk:1605041188": ('LongPort 長橋',                     ["Longbridge", "長橋", "长桥", "LongPort"]),
    "hk:592031984":  ('富途證券 OR 富途牛牛',               ["富途", "Futu", "moomoo", "Moomoo"]),
    "hk:1023600494": ('老虎證券 OR "Tiger Trade"',          ["老虎", "Tiger"]),
    "hk:1557435421": ('Webull 微牛',                       ["Webull", "微牛"]),
    "hk:1463024118": ('盈立證券 OR uSmart',                 ["盈立", "uSmart"]),
    "hk:492180369":  ('雪球 股票 App',                      ["雪球", "Snowball"]),
    "hk:454558592":  ('盈透證券 OR "Interactive Brokers"',  ["盈透", "Interactive Brokers", "IBKR"]),
    "us:1440255819": ('moomoo app',                        ["moomoo", "Moomoo", "Futu"]),
    "us:1179213067": ('Webull app',                        ["Webull"]),
    "us:938003185":  ('Robinhood app',                     ["Robinhood"]),
    "us:1023600494": ('"Tiger Brokers" OR "Tiger Trade"',  ["Tiger"]),
    "us:454558592":  ('"Interactive Brokers" app',         ["Interactive Brokers", "IBKR"]),
}
NEWS_LOCALE = {"hk": ("zh-HK", "HK", "HK:zh-Hant"), "us": ("en-US", "US", "US:en")}
REVIEW_HINT = re.compile(r"review|評測|评测|評價|评价|比較|比较|\bvs\.?\b|pros|cons|best .*app|哪個好|哪个好|點揀|测评", re.I)

# 关键词搜索排名（App Store 搜索接口的结果顺序，近似真机搜索）
KEYWORDS = {
    "hk": ["港股", "美股", "期權", "股票", "炒股", "ETF", "stock", "trading"],
    "us": ["stock", "trading", "options", "invest", "brokerage"],
}
SEARCH_LIMIT = 100

# 功能标签：(id, 分组, 名称, 正则)。从商店描述 + 历次更新说明里识别，依据是各家自己宣称的内容
FEATURES = [
    ("hk_stock",  "市场", "港股",       r"港股|HK stocks?|Hong Kong stocks?"),
    ("us_stock",  "市场", "美股",       r"美股|US stocks?|U\.S\. stocks?"),
    ("a_share",   "市场", "A 股",       r"A股|A 股|滬深港通|沪深港通|China A"),
    ("jp_stock",  "市场", "日股",       r"日股|日本股|Japan(ese)? stocks?"),
    ("sg_stock",  "市场", "新加坡股",   r"新加坡股|新股市場.*新加坡|Singapore stocks?|SGX"),
    ("crypto",    "产品", "加密货币",   r"Crypto|加密貨幣|加密货币|比特幣|比特币|Bitcoin|虛擬資產|虚拟资产"),
    ("options",   "产品", "期权",       r"期權|期权|options?\b"),
    ("futures",   "产品", "期货",       r"期貨|期货|futures"),
    ("funds",     "产品", "基金",       r"基金|funds?\b|mutual fund|貨幣基金|月供"),
    ("bonds",     "产品", "债券",       r"債券|债券|bonds?\b|Treasur"),
    ("fx",        "产品", "外汇",       r"外匯|外汇|槓桿式外匯|\bforex\b|\bFX\b"),
    ("ipo",       "产品", "新股认购",   r"新股|抽新股|\bIPOs?\b"),
    ("overnight", "交易", "夜盘/24 小时", r"夜盤|夜盘|24\s*小時|24\s*小时|5\s*[x×]\s*24|24/5|24-hour|overnight"),
    ("fractional","交易", "碎股",       r"碎股|零股|fractional"),
    ("condorder", "交易", "条件单/止盈止损", r"條件單|条件单|止盈|止損|止损|stop[- ]loss|take[- ]profit|conditional order|trailing stop"),
    ("margin",    "交易", "融资/保证金", r"融資|融资|孖展|保證金|保证金|margin"),
    ("paper",     "交易", "模拟交易",   r"模擬交易|模拟交易|模擬炒股|paper trading|simulated trading"),
    ("dca",       "交易", "定投/月供",  r"月供|定投|定期定額|recurring invest|auto[- ]invest"),
    ("ai",        "工具", "AI 助手",    r"\bAI\b|GPT|人工智能|智能助手|AI助手|大模型"),
    ("community", "工具", "社区",       r"社區|社区|牛牛圈|論壇|讨论|community|social feed"),
    ("lv2",       "工具", "Level 2 行情", r"LV2|Level\s*2|Lv2|深度行情|60\s*檔|十檔|10\s*檔"),
    ("news",      "工具", "资讯/研报",  r"資訊|资讯|新聞|研報|研报|news|research report"),
    ("screener",  "工具", "选股器",     r"選股|选股|screener"),
    ("chart",     "工具", "专业图表",   r"K線|K线|技術分析|技术分析|指標|指标|charting|technical analysis"),
    ("free_comm", "费用", "免佣/0 佣金", r"免佣|0\s*佣金|零佣金|commission[- ]free|\$0 commission|zero commission"),
    ("cash_mgmt", "费用", "现金管理/理财", r"現金寶|现金宝|現金管理|现金管理|cash management|high[- ]yield cash|利息"),
]
FEATURE_RE = [(fid, re.compile(rx, re.I)) for fid, _, _, rx in FEATURES]

# 差评主题：在 1–2 星评论里统计（繁体 / 简体 / 英文）
TOPICS = [
    ("crash",   "闪退卡顿",   r"閃退|闪退|崩潰|崩溃|卡頓|卡顿|卡死|好卡|很卡|慢|lag|crash|freez|frozen|slow|bug"),
    ("battery", "耗电发热",   r"耗電|耗电|發熱|发热|發燙|发烫|電量|电量|battery|heat|hot\b|drain"),
    ("login",   "登录验证",   r"登入|登录|登錄|驗證|验证|密碼|密码|log ?in|sign ?in|2fa|otp|verification|password|locked out"),
    ("quote",   "行情数据",   r"行情|報價|报价|延遲|延迟|數據|数据|圖表|图表|quote|delay|data|chart|price"),
    ("money",   "入金出金",   r"入金|出金|存款|提款|轉賬|转账|轉帳|資金|资金|deposit|withdraw|transfer|fund"),
    ("fee",     "费用佣金",   r"收費|收费|佣金|手續費|手续费|費用|费用|fee|commission|charge|subscription"),
    ("support", "客服",       r"客服|服務態度|服务态度|support|customer service|help ?desk|no response|回覆|回复"),
    ("order",   "下单交易",   r"下單|下单|成交|落單|交易失敗|order|execution|filled|trade fail"),
    ("ui",      "界面更新",   r"介面|界面|改版|更新後|更新后|新版|舊版|旧版|UI\b|interface|layout|update|redesign"),
    ("account", "开户审核",   r"開戶|开户|審核|审核|KYC|account (opening|approval)|verify (my )?identity"),
    ("ads",     "广告推送",   r"廣告|广告|推送|通知太多|\bads?\b|\badvert|spam|too many notifications|push notification"),
]
TOPIC_RE = [(tid, re.compile(rx, re.I)) for tid, _, rx in TOPICS]

# ── 工具 ──────────────────────────────────────────────────────────────────────

def fetch(url, timeout=20):
    return urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=timeout).read()

def fetch_json(url, timeout=20):
    return json.loads(fetch(url, timeout))

def iso(dt):
    return dt.astimezone(CST).isoformat(timespec="seconds")

def to_cst(s):
    try:
        return iso(datetime.fromisoformat(s.replace("Z", "+00:00")))
    except Exception:
        return s or ""

def clean(text):
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", text or ""))).strip()

def label(d, *keys):
    for k in keys:
        d = (d or {}).get(k, {})
    return d if isinstance(d, str) else (d or {}).get("label", "") if isinstance(d, dict) else ""

def run(label_, fn):
    try:
        res = fn()
        print(f"  ✓ {label_}")
        return res, ""
    except Exception as e:
        err = f"{type(e).__name__}: {e}"[:200]
        print(f"  ✗ {label_} {err}")
        return None, err

# ── App Store：详情 / 榜单 / 搜索 ─────────────────────────────────────────────

def lookup(region, ids):
    data = fetch_json(f"https://itunes.apple.com/lookup?id={','.join(map(str, ids))}&country={region}")
    return {r["trackId"]: r for r in data.get("results", [])}

def chart(region):
    feed = fetch_json(f"https://itunes.apple.com/{region}/rss/topfreeapplications/limit=100/genre={FINANCE_GENRE}/json")["feed"]
    out = []
    for i, e in enumerate(feed.get("entry", [])):
        imgs = e.get("im:image", [])
        out.append({"rank": i + 1, "id": int(e["id"]["attributes"]["im:id"]),
                    "name": e["im:name"]["label"], "seller": e.get("im:artist", {}).get("label", ""),
                    "icon": imgs[-1]["label"] if imgs else "", "url": e["id"]["label"]})
    return out

def keyword_ranks(region):
    """每个关键词的搜索结果里，追踪 App 的名次（不在前 SEARCH_LIMIT 名为 None）。"""
    ids = {aid for aid, _ in APPS[region]}
    out = {}
    for kw in KEYWORDS[region]:
        data = fetch_json(f"https://itunes.apple.com/search?term={urllib.parse.quote(kw)}&country={region}"
                          f"&entity=software&limit={SEARCH_LIMIT}")
        order = [r["trackId"] for r in data.get("results", [])]
        out[kw] = {str(aid): (order.index(aid) + 1 if aid in order else None) for aid in ids}
        time.sleep(1)   # 搜索接口有频率限制
    return out

# ── 商店描述：卖点与功能标签 ──────────────────────────────────────────────────

BULLET = re.compile(r"^\s*(?:\d{1,2}\s*[\.、．)）]|[a-zA-Z][\.)）]\s|[•●▪◆◇■□★☆✓✔➤►▶·\-–—*]|【[^】]{1,20}】)\s*")
# 订阅价格、条款、免责声明这类段落不能当定位语
LEGAL = re.compile(r"港幣\s*/\s*月|港币\s*/\s*月|/月|訂閱|订阅|自動續|自动续|subscription|auto-renew|privacy|terms|"
                   r"免責|免责|風險|风险|disclos|member SIPC|FINRA|Securities and Futures Commission|證監會", re.I)

def highlights(desc, limit=12):
    """从商店描述里摘出编号 / 列表形式的卖点条目（原文）。"""
    out = []
    for line in (desc or "").splitlines():
        line = line.strip()
        if not BULLET.match(line):
            continue
        text = BULLET.sub("", line).strip()
        if 6 <= len(text) <= 160 and text not in out:
            out.append(text)
        if len(out) >= limit:
            break
    return out

def intro(desc, n=220):
    """描述开头的定位语：第一段（非标题、非列表）。"""
    for para in re.split(r"\n\s*\n|\n", desc or ""):
        p = para.strip()
        if len(p) >= 20 and not BULLET.match(p) and not LEGAL.search(p):
            return p[:n] + ("…" if len(p) > n else "")
    return ""

def features(desc, history, tracked_since, region):
    """功能标签：先看历次更新说明（记录首次出现的版本日期），再看商店描述。"""
    found = {}
    # 美区 App 的描述只写 stocks 不写 US stocks，默认就是美股
    if region == "us" and re.search(r"\bstocks?\b", desc or "", re.I):
        found["us_stock"] = {"src": "desc", "since": tracked_since}
    for h in sorted(history, key=lambda h: h.get("date") or ""):
        for fid, rx in FEATURE_RE:
            if fid not in found and rx.search(h.get("notes") or ""):
                found[fid] = {"src": "notes", "since": (h.get("date") or "")[:10], "version": h.get("version", "")}
    for fid, rx in FEATURE_RE:
        if fid not in found and rx.search(desc or ""):
            found[fid] = {"src": "desc", "since": tracked_since}
    return found

# ── 用户评论 ──────────────────────────────────────────────────────────────────

def review_page(region, aid, page):
    """被限流时苹果不报错，而是返回空列表或非 JSON；所以空页先退避重试，确认真的为空才算没有更多。"""
    for attempt in range(3):
        try:
            feed = fetch_json(f"https://itunes.apple.com/{region}/rss/customerreviews/page={page}/id={aid}/sortby=mostrecent/json")["feed"]
            entries = feed.get("entry", [])
            entries = [entries] if isinstance(entries, dict) else entries   # 只有 1 条时是对象不是数组
            entries = [e for e in entries if "im:rating" in e]
            if entries:
                return entries
        except Exception:
            if attempt == 2 and page == 1:
                raise
        time.sleep(5 * (attempt + 1))
    return []

def reviews(region, aid):
    out = []
    for page in range(1, REVIEW_PAGES + 1):
        entries = review_page(region, aid, page)
        if not entries:
            break
        for e in entries:
            out.append({
                "id":      label(e, "id"),
                "rating":  int(label(e, "im:rating") or 0),
                "version": label(e, "im:version"),
                "date":    to_cst(label(e, "updated")),
                "author":  label(e, "author", "name"),
                "title":   clean(label(e, "title"))[:120],
                "content": clean(label(e, "content"))[:REVIEW_MAX],
                "votes":   int(label(e, "im:voteSum") or 0),
            })
        if len(entries) < 50:
            break
        time.sleep(2.5)   # 间隔 1 秒仍会被限流，实测需要更慢
    return out

def topics_of(text):
    return [tid for tid, rx in TOPIC_RE if rx.search(text)]

def review_stats(revs, now):
    """评论统计：近期星级分布、各版本口碑、差评主题。"""
    if not revs:
        return {"total": 0}
    cut = (now - timedelta(days=RECENT_DAYS)).isoformat()
    recent = [r for r in revs if r["date"] >= cut]
    base = recent if len(recent) >= 20 else revs   # 近期样本太少时用全部
    dist = Counter(r["rating"] for r in base)
    neg = [r for r in base if r["rating"] <= 2]
    topic_cnt = Counter(t for r in neg for t in topics_of(r["title"] + " " + r["content"]))

    by_ver = {}
    for r in revs:
        by_ver.setdefault(r["version"], []).append(r)
    versions = sorted(by_ver.items(), key=lambda kv: max(x["date"] for x in kv[1]), reverse=True)
    ver_rows = [{"version": v, "count": len(rs), "avg": round(sum(x["rating"] for x in rs) / len(rs), 2),
                 "neg": sum(x["rating"] <= 2 for x in rs), "last": max(x["date"] for x in rs)[:10]}
                for v, rs in versions if len(rs) >= 3][:10]
    return {
        "total":      len(revs),
        "window":     "recent" if base is recent else "all",
        "sample":     len(base),
        "avg":        round(sum(r["rating"] for r in base) / len(base), 2),
        "dist":       {str(s): dist.get(s, 0) for s in range(1, 6)},
        "neg":        len(neg),
        "topics":     {t: topic_cnt.get(t, 0) for t, _, _ in TOPICS},
        "versions":   ver_rows,
        "oldest":     min(r["date"] for r in revs)[:10],
        "newest":     max(r["date"] for r in revs)[:10],
    }

# ── 媒体报道（Google News RSS） ───────────────────────────────────────────────

def news(region, key):
    query, own = NEWS[key]
    hl, gl, ceid = NEWS_LOCALE[region]
    extra = " review" if region == "us" else " 評價 OR 評測 OR 比較"
    items = {}
    for q in (query, f"({query}){extra}"):
        url = (f"https://news.google.com/rss/search?q={urllib.parse.quote(q + ' when:' + str(NEWS_DAYS) + 'd')}"
               f"&hl={hl}&gl={gl}&ceid={urllib.parse.quote(ceid)}")
        root = ET.fromstring(fetch(url))
        for it in root.iter("item"):
            source = (it.findtext("source") or "").strip()
            if any(o.lower() in source.lower() for o in own):
                continue   # 自家渠道发布的不算媒体评价
            title = (it.findtext("title") or "").strip()
            if source and title.endswith(" - " + source):
                title = title[: -len(source) - 3].strip()
            try:
                date = iso(parsedate_to_datetime(it.findtext("pubDate") or ""))
            except Exception:
                date = ""
            k = re.sub(r"\W+", "", title.lower())[:60]
            if k and k not in items:
                items[k] = {"title": title, "source": source, "url": it.findtext("link") or "",
                            "date": date, "review": bool(REVIEW_HINT.search(title))}
        time.sleep(1)
    return sorted(items.values(), key=lambda x: x["date"], reverse=True)

# ── 主流程 ────────────────────────────────────────────────────────────────────

def main():
    prev, prev_rev = {}, {}
    for path, target in ((OUT, "prev"), (REV_OUT, "rev")):
        if path.exists():
            try:
                (prev if target == "prev" else prev_rev).update(json.loads(path.read_text()))
            except Exception:
                pass
    prev_apps = {a["key"]: a for a in prev.get("apps", [])}
    prev_charts = prev.get("charts", {})
    prev_kw = prev.get("keywords", {})
    prev_reviews = prev_rev.get("apps", {})
    now = datetime.now(CST)
    today = now.strftime("%Y-%m-%d")
    news_cut = (now - timedelta(days=NEWS_DAYS)).isoformat()

    print("→ 抓取")
    sources, apps, charts, keywords, all_reviews = [], [], {}, {}, {}
    rev_ok = rev_fail = news_ok = news_fail = 0
    for region, rname in REGIONS:
        # 榜单
        entries, err = run(f"{rname}财经榜", lambda: chart(region))
        pc = prev_charts.get(region, {})
        days = dict(pc.get("days", {}))          # 日期 → 当天榜单 ID 顺序，用来算较前一天的升降
        if entries is not None:
            days[today] = [e["id"] for e in entries]
        days = dict(sorted(days.items())[-3:])
        prev_day = next((d for d in sorted(days, reverse=True) if d < today), None)
        prev_rank = {aid: i + 1 for i, aid in enumerate(days.get(prev_day, []))}
        if entries is None:
            entries = pc.get("entries", [])
        for e in entries:
            e["prev_rank"] = prev_rank.get(e["id"]) if prev_day else None
        charts[region] = {"entries": entries, "days": days, "prev_day": prev_day,
                          "updated": iso(now) if err == "" else pc.get("updated", "")}
        sources.append({"id": f"chart-{region}", "name": f"{rname}财经免费榜", "ok": err == "",
                        "error": err, "count": len(entries)})
        rank_of = {e["id"]: e["rank"] for e in entries} if err == "" else {}

        # 关键词搜索排名
        kw, err = run(f"{rname}关键词排名", lambda: keyword_ranks(region))
        sources.append({"id": f"search-{region}", "name": f"{rname}关键词排名", "ok": kw is not None,
                        "error": err, "count": len(kw or {})})
        keywords[region] = kw if kw is not None else prev_kw.get(region, {})

        # App 详情（一次请求查完该地区所有 App）
        ids = [aid for aid, _ in APPS[region]]
        found, err = run(f"{rname} App 详情", lambda: lookup(region, ids))
        found = found or {}
        sources.append({"id": f"lookup-{region}", "name": f"{rname} App 详情", "ok": err == "" and len(found) == len(ids),
                        "error": err or (f"{len(ids) - len(found)} 个 App 未返回" if len(found) < len(ids) else ""),
                        "count": len(found)})

        # 评论接口限流很严，所有 App 串行抓（单独一个线程）；报道走 Google，和评论并行
        with ThreadPoolExecutor(max_workers=2) as pool:
            rev_all = pool.submit(lambda: {aid: run(f"{rname} 评论 {short}", lambda aid=aid: reviews(region, aid))
                                           for aid, short in APPS[region]})
            news_all = pool.submit(lambda: {aid: run(f"{rname} 报道 {short}", lambda aid=aid: news(region, f"{region}:{aid}"))
                                            for aid, short in APPS[region] if f"{region}:{aid}" in NEWS})
        rev_res, news_res = rev_all.result(), news_all.result()

        for aid, short in APPS[region]:
            key = f"{region}:{aid}"
            old = prev_apps.get(key, {})

            # 评论：与上次合并去重，新的在前
            fresh, err = rev_res[aid]
            if fresh is None:
                rev_fail += 1
            else:
                rev_ok += 1
            merged = {r["id"]: r for r in prev_reviews.get(key, [])}
            for r in fresh or []:
                merged[r["id"]] = r
            revs = sorted(merged.values(), key=lambda r: r["date"], reverse=True)[:REVIEW_KEEP]
            all_reviews[key] = revs

            # 报道：与上次合并，保留最近 NEWS_DAYS 天
            items = old.get("news", [])
            if aid in news_res:
                got, err = news_res[aid]
                if got is None:
                    news_fail += 1
                else:
                    news_ok += 1
                    seen = {re.sub(r"\W+", "", n["title"].lower())[:60] for n in got}
                    items = got + [n for n in items if re.sub(r"\W+", "", n["title"].lower())[:60] not in seen]
            items = sorted((n for n in items if n["date"] >= news_cut), key=lambda n: n["date"], reverse=True)[:NEWS_KEEP]

            r = found.get(aid)
            if r is None:
                if old:   # 本次没查到，沿用上次数据（评论和报道照常更新）
                    apps.append({**old, "stale": True, "news": items, "review_stats": review_stats(revs, now)})
                continue
            version, vdate = r.get("version", ""), to_cst(r.get("currentVersionReleaseDate", ""))
            notes = (r.get("releaseNotes") or "").strip()[:NOTES_MAX]
            history = list(old.get("history", []))
            if not history or history[0]["version"] != version:
                history.insert(0, {"version": version, "date": vdate, "notes": notes, "seen": iso(now)})
            history = history[:HISTORY_KEEP]
            tracked_since = old.get("tracked_since", today)
            desc = (r.get("description") or "").strip()[:DESC_MAX]

            # 每日快照：同一天多次运行只保留最后一次
            daily = [d for d in old.get("daily", []) if d["d"] != today]
            daily.append({"d": today, "rating": round(r.get("averageUserRating") or 0, 3),
                          "count": r.get("userRatingCount") or 0, "rank": rank_of.get(aid),
                          "kw": {k: v.get(str(aid)) for k, v in keywords[region].items()}})
            daily = sorted(daily, key=lambda d: d["d"])[-DAILY_KEEP:]

            apps.append({
                "key":          key,
                "region":       region,
                "id":           aid,
                "name":         short,
                "title":        r.get("trackName", ""),
                "seller":       r.get("sellerName", ""),
                "icon":         r.get("artworkUrl100", ""),
                "url":          (r.get("trackViewUrl") or "").split("?")[0],
                "version":      version,
                "version_date": vdate,
                "notes":        notes,
                "rating":       round(r.get("averageUserRating") or 0, 3),
                "rating_count": r.get("userRatingCount") or 0,
                "size":         int(r.get("fileSizeBytes") or 0),
                "min_os":       r.get("minimumOsVersion", ""),
                "languages":    len(r.get("languageCodesISO2A") or []),
                "released":     to_cst(r.get("releaseDate", ""))[:10],
                "rank":         rank_of.get(aid),
                "tracked_since": tracked_since,
                "stale":        False,
                "intro":        intro(desc),
                "description":  desc,
                "highlights":   highlights(desc),
                "screenshots":  (r.get("screenshotUrls") or [])[:10],
                "features":     features(desc, history, tracked_since, region),
                "review_stats": review_stats(revs, now),
                "news":         items,
                "history":      history,
                "daily":        daily,
            })

    sources.append({"id": "reviews", "name": "用户评论", "ok": rev_fail == 0,
                    "error": f"{rev_fail} 个 App 抓取失败" if rev_fail else "", "count": sum(len(v) for v in all_reviews.values())})
    sources.append({"id": "news", "name": "媒体报道（Google News）", "ok": news_fail == 0,
                    "error": f"{news_fail} 个 App 抓取失败" if news_fail else "",
                    "count": sum(len(a.get("news", [])) for a in apps)})

    data = {
        "updated":  iso(now),   # 每次都变，并且每天新增快照，保证每次运行都有提交
        "regions":  [{"id": k, "name": n} for k, n in REGIONS],
        "features": [{"id": f, "group": g, "name": n} for f, g, n, _ in FEATURES],
        "topics":   [{"id": t, "name": n} for t, n, _ in TOPICS],
        "keywords": keywords,
        "sources":  sources,
        "apps":     apps,
        "charts":   charts,
    }
    OUT.write_text(json.dumps(data, ensure_ascii=False, indent=1))
    REV_OUT.write_text(json.dumps({"updated": iso(now), "apps": all_reviews}, ensure_ascii=False, separators=(",", ":")))
    ok = sum(s["ok"] for s in sources)
    print(f"→ 完成：{ok}/{len(sources)} 个来源正常，追踪 {len(apps)} 个 App，评论 {sum(len(v) for v in all_reviews.values())} 条，"
          f"报道 {sum(len(a.get('news', [])) for a in apps)} 条 → {OUT.name} / {REV_OUT.name}")

if __name__ == "__main__":
    main()

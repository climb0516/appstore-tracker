#!/usr/bin/env python3
"""AppWatch scraper — 追踪券商 App 的 App Store 版本、评分与财经榜排名，输出 data.json。仅依赖 Python 标准库。"""
import json, urllib.request
from datetime import datetime, timezone, timedelta
from pathlib import Path

OUT = Path(__file__).with_name("data.json")
CST = timezone(timedelta(hours=8))
UA  = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
                     "(KHTML, like Gecko) Chrome/126.0 Safari/537.36"}
HISTORY_KEEP = 60     # 每个 App 保留的版本记录数
DAILY_KEEP   = 365    # 每个 App 保留的每日快照天数
NOTES_MAX    = 1500   # 更新说明最长字数

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

# ── 工具 ──────────────────────────────────────────────────────────────────────

def fetch_json(url, timeout=20):
    req = urllib.request.Request(url, headers=UA)
    return json.loads(urllib.request.urlopen(req, timeout=timeout).read())

def iso(dt):
    return dt.astimezone(CST).isoformat(timespec="seconds")

def to_cst(s):
    try:
        return iso(datetime.fromisoformat(s.replace("Z", "+00:00")))
    except Exception:
        return s or ""

def run(label, fn):
    try:
        res = fn()
        print(f"  ✓ {label}")
        return res, ""
    except Exception as e:
        err = f"{type(e).__name__}: {e}"[:200]
        print(f"  ✗ {label} {err}")
        return None, err

# ── 抓取 ──────────────────────────────────────────────────────────────────────

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

# ── 主流程 ────────────────────────────────────────────────────────────────────

def main():
    prev = {}
    if OUT.exists():
        try:
            prev = json.loads(OUT.read_text())
        except Exception:
            pass
    prev_apps = {a["key"]: a for a in prev.get("apps", [])}
    prev_charts = prev.get("charts", {})
    now = datetime.now(CST)
    today = now.strftime("%Y-%m-%d")

    print("→ 抓取")
    sources, apps, charts = [], [], {}
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

        # App 详情（一次请求查完该地区所有 App）
        ids = [aid for aid, _ in APPS[region]]
        found, err = run(f"{rname} App 详情", lambda: lookup(region, ids))
        found = found or {}
        sources.append({"id": f"lookup-{region}", "name": f"{rname} App 详情", "ok": err == "" and len(found) == len(ids),
                        "error": err or (f"{len(ids) - len(found)} 个 App 未返回" if len(found) < len(ids) else ""),
                        "count": len(found)})

        for aid, short in APPS[region]:
            key = f"{region}:{aid}"
            old = prev_apps.get(key, {})
            r = found.get(aid)
            if r is None:
                if old:   # 本次没查到，沿用上次数据
                    apps.append({**old, "stale": True})
                continue
            version, vdate = r.get("version", ""), to_cst(r.get("currentVersionReleaseDate", ""))
            notes = (r.get("releaseNotes") or "").strip()[:NOTES_MAX]
            history = list(old.get("history", []))
            if not history or history[0]["version"] != version:
                history.insert(0, {"version": version, "date": vdate, "notes": notes, "seen": iso(now)})
            history = history[:HISTORY_KEEP]

            # 每日快照：同一天多次运行只保留最后一次
            daily = [d for d in old.get("daily", []) if d["d"] != today]
            daily.append({"d": today, "rating": round(r.get("averageUserRating") or 0, 3),
                          "count": r.get("userRatingCount") or 0, "rank": rank_of.get(aid)})
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
                "rank":         rank_of.get(aid),
                "tracked_since": old.get("tracked_since", today),
                "stale":        False,
                "history":      history,
                "daily":        daily,
            })

    data = {
        "updated": iso(now),   # 每次都变，并且每天新增快照，保证每次运行都有提交
        "regions": [{"id": k, "name": n} for k, n in REGIONS],
        "sources": sources,
        "apps":    apps,
        "charts":  charts,
    }
    OUT.write_text(json.dumps(data, ensure_ascii=False, indent=1))
    ok = sum(s["ok"] for s in sources)
    print(f"→ 完成：{ok}/{len(sources)} 个来源正常，追踪 {len(apps)} 个 App → {OUT.name}")

if __name__ == "__main__":
    main()

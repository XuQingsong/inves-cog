#!/usr/bin/env python3
"""Build the info-system-v2 "today" page prototype.

Reads raw production dumps in ./raw (news, movers, page APIs, Nasdaq calendars,
Yahoo VIX), applies the deterministic rules layer, writes data-YYYY-MM-DD.json
and a self-contained index.html with both days embedded.
"""
import json
import re
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent
RAW = ROOT / "raw"
DAYS = ["2026-10-22", "2026-10-23"]
NY = ZoneInfo("America/New_York")
UTC = ZoneInfo("UTC")

STRONG_RATING = re.compile(r"upgrade|downgrade|initiates? coverage", re.I)
TAG_RULES = [
    ("财报", r"\b(earnings|EPS|revenue|quarterly results|Q[1-4] results|financial results)\b|reports? (third|second|first|fourth) quarter"),
    ("财报前瞻", r"earnings preview|what to expect|ahead of earnings|earnings (on deck|this week)|priced for .* swings|earnings volatility"),
    ("评级", r"upgrade|downgrade|initiates? coverage|price target|\bPT\b|reiterat"),
    ("指引", r"guidance|outlook|raises? (FY|full-year)|lowers? (FY|full-year)|cuts? forecast"),
    ("并购", r"merger|acquisition|acquires?|takeover|buyout|to buy\b"),
    ("监管关税", r"tariff|export control|sanction|antitrust|\bFTC\b|\bDOJ\b|regulat"),
    ("诉讼召回", r"lawsuit|litigation|\bsues?\b|recall|settlement"),
    ("宏观", r"\b(Fed|FOMC|Powell|CPI|PCE|payrolls|jobs report|treasury yields?|inflation|GDP)\b"),
    ("产品合作", r"partnership|partners with|collaborat|launch|unveil|deploy|contract"),
]
MACRO_RULES = [
    ("利率", r"Fed|FOMC|yield|rate cut|rate hike|treasur"),
    ("关税", r"tariff|trade war|export control"),
    ("原油", r"\boil\b|crude|OPEC|Brent|WTI"),
    ("加密", r"bitcoin|crypto|ethereum"),
]
HOT_TAGS = {"财报", "指引", "评级", "并购"}


def load(name):
    return json.loads((RAW / name).read_text())


def parse_ts(value):
    return datetime.fromisoformat(str(value).replace("Z", "+00:00"))


def money_cap(text):
    digits = re.sub(r"[^0-9.]", "", str(text or ""))
    return float(digits) if digits else 0.0


def rule_news(rows, pool, held, day):
    """Deterministic rules layer: primary_tickers, tags, importance, dedup."""
    late_cut = datetime.combine(datetime.fromisoformat(day).date(), datetime.min.time().replace(hour=16), tzinfo=NY)
    universe = set(pool) | set(held)
    items = []
    for row in rows:
        tickers = [t for t in (row.get("tickers") or []) if isinstance(t, str)]
        headline = row.get("headline") or ""
        primary = [t for t in tickers if t in universe]
        if len(tickers) > 5:
            primary = [t for t in primary if re.search(rf"\b{re.escape(t)}\b", headline)]
        tags = [name for name, pat in TAG_RULES if re.search(pat, headline, re.I)]
        if "并购" in tags and "产品合作" in tags:
            tags.remove("产品合作")
        macro = next((name for name, pat in MACRO_RULES if re.search(pat, headline, re.I)), None)
        score = 0
        if any(t in held for t in primary):
            score += 3
        elif primary:
            score += 2
        strong = HOT_TAGS & set(tags) or ({"评级"} & set(tags) if STRONG_RATING.search(headline) else set())
        if strong:
            score += 2
        elif set(tags) - {"评级"}:
            score += 1
        if len(tickers) > 5 and not primary:
            score -= 2
        published = parse_ts(row["published_at"])
        seen = parse_ts(row["first_seen_at"]) if row.get("first_seen_at") else published
        items.append(
            {
                "info_id": row["info_id"],
                "published": published,
                "seen": seen,
                "late": seen > late_cut,
                "source": row.get("source"),
                "headline": headline,
                "url": row.get("url"),
                "tickers": tickers,
                "primary": primary,
                "held": any(t in held for t in primary),
                "tags": tags,
                "macro": macro,
                "weak_rating_only": set(tags) == {"评级"} and not STRONG_RATING.search(headline),
                "importance": score,
            }
        )
    best = {}
    for item in sorted(items, key=lambda x: x["published"]):
        key = (tuple(sorted(item["primary"])), " ".join(item["headline"].lower().split()[:8]))
        if key not in best:
            best[key] = item
    kept = sorted(best.values(), key=lambda x: x["published"], reverse=True)
    return kept


def build_day(day):
    market = load(f"v2_market_{day}.json")
    stocks = load(f"v2_stocks_{day}.json")
    account = load(f"v2_account_{day}.json")
    movers = load(f"movers_{day}.json")
    news_rows = load(f"news_{day}.json")

    held = [h["ticker"] for h in account["holdings"]]
    pool = {}
    for theme in stocks["themes"]:
        for m in theme["members"]:
            pool[m["ticker"]] = {"theme": theme["sector"], "ret": m.get("ret"), "vol": m.get("volume_multiple")}
    news = rule_news(news_rows, set(pool), set(held), day)
    zh_file = RAW / "translations.json"
    zh = json.loads(zh_file.read_text()) if zh_file.exists() else {}
    for n in news:
        n["headline_zh"] = zh.get(n["info_id"], "")

    # module 2: movers + related news (news attached under each row)
    uni = {t: {**v, "held": t in held} for t, v in pool.items()}
    for t in held:
        uni.setdefault(t, {"theme": None, "ret": None, "vol": None, "held": True})
    top8 = sorted((t for t in uni if uni[t]["ret"] is not None), key=lambda t: -abs(uni[t]["ret"]))[:8]
    mover_rows = []
    for t in top8:
        own = sorted(
            (n for n in news if t in n["primary"]),
            key=lambda n: (-n["importance"], n["published"]),
        )
        mover_rows.append(
            {
                "ticker": t,
                "held": uni[t]["held"],
                "theme": uni[t]["theme"],
                "ret": uni[t]["ret"],
                "vol": uni[t]["vol"],
                "has_news": bool(own),
                "news": own[:2],
            }
        )
    mover_news = sorted(
        (n for n in news if set(n["primary"]) & set(top8)),
        key=lambda n: (-n["importance"], n["published"]),
    )[:10]

    # module 3: hot theme news
    def theme_of(n):
        if not n["primary"]:
            return n["macro"]
        held_p = [t for t in n["primary"] if t in held]
        if held_p:
            pick = max(held_p, key=lambda t: pool.get(t, {}).get("ret") is not None and abs(pool[t]["ret"]) or 0)
            return pool.get(pick, {}).get("theme") or pick
        in_title = [t for t in n["primary"] if re.search(rf"\b{re.escape(t)}\b", n["headline"])]
        if in_title:
            pick = in_title[0]
            return pool.get(pick, {}).get("theme") or pick
        pick = n["primary"][0]
        return pool.get(pick, {}).get("theme") or pick

    eligible = [n for n in news if theme_of(n) and not n["weak_rating_only"]]
    by_theme = {}
    for n in eligible:
        by_theme.setdefault(theme_of(n), []).append(n)
    theme_pick = []
    for theme, items in sorted(
        by_theme.items(),
        key=lambda kv: (-max(i["importance"] for i in kv[1]), kv[0]),
    ):
        items.sort(key=lambda n: (-n["importance"], n["published"]))
        theme_pick.extend((theme, n) for n in items[:2])
    theme_pick.sort(key=lambda tn: (-tn[1]["held"], -tn[1]["importance"], -tn[1]["published"].timestamp()))
    theme_pick = theme_pick[:15]

    # module 4: feed + calendars
    feed = [n for n in news if n["primary"] or n["macro"]][:40]
    previews = [n for n in news if "财报前瞻" in n["tags"]]

    earnings = []
    for f in sorted(RAW.glob("earnings_*.json")):
        d = load(f.name)["data"]
        date = f.stem.split("_")[1]
        for r in d.get("rows") or []:
            tlabel = {"time-pre-market": "盘前", "time-after-hours": "盘后"}.get(r.get("time"), "未定")
            earnings.append(
                {
                    "date": date,
                    "symbol": r.get("symbol"),
                    "name": r.get("name"),
                    "mktcap": money_cap(r.get("marketCap")),
                    "time": tlabel,
                    "eps": r.get("epsForecast"),
                    "ests": r.get("noOfEsts"),
                }
            )
    seen_names = {}
    deduped = []
    for e in earnings:
        key = (e["name"], e["date"])
        if key in seen_names:
            if e["symbol"] and e["symbol"] > seen_names[key]["symbol"]:
                deduped.remove(seen_names[key])
                deduped.append(e)
                seen_names[key] = e
        else:
            seen_names[key] = e
            deduped.append(e)
    earnings = deduped
    week_pool = sorted(
        (e for e in earnings if "2026-10-26" <= e["date"] <= "2026-10-30"),
        key=lambda e: -e["mktcap"],
    )[:10]
    week = sorted(week_pool, key=lambda e: (e["date"], -e["mktcap"]))
    mine = [e for e in earnings if e["symbol"] in set(pool) | set(held)]
    mine.sort(key=lambda e: e["date"])
    for e in mine:
        e["held"] = e["symbol"] in held
        e["previews"] = [n for n in previews if e["symbol"] in n["primary"]][:3]

    ECON_KEY = re.compile(
        r"FOMC|Fed Interest Rate|Fed Chair|Powell|CPI|PCE|Nonfarm|Unemployment Rate|\bGDP\b(?!Now)|ISM|"
        r"Retail Sales|Initial Jobless|Consumer Confidence|Michigan|JOLTS|PPI",
        re.I,
    )
    econ = []
    seen_econ = set()
    for f in sorted(RAW.glob("econ_*.json")):
        d = load(f.name)["data"]
        date = f.stem.split("_")[1]
        for r in d.get("rows") or []:
            if r.get("country") != "United States" or not ECON_KEY.search(r.get("eventName") or ""):
                continue
            key = (date, r.get("eventName"), r.get("gmt"))
            if key in seen_econ:
                continue
            seen_econ.add(key)
            econ.append({"date": date, "gmt": r.get("gmt"), "name": r.get("eventName"), "consensus": r.get("consensus"), "previous": r.get("previous")})
    econ.sort(key=lambda e: (e["date"], e["gmt"] or ""))
    econ = econ[:8]

    # module 5: leaderboards
    pool_sorted = sorted((t for t in pool if pool[t]["ret"] is not None), key=lambda t: pool[t]["ret"])
    leaders = {
        "pool_up": [{"ticker": t, "ret": pool[t]["ret"], "theme": pool[t]["theme"]} for t in pool_sorted[-5:][::-1]],
        "pool_down": [{"ticker": t, "ret": pool[t]["ret"], "theme": pool[t]["theme"]} for t in pool_sorted[:5]],
        "mkt_up": [{"ticker": m["ticker"], "ret": m["ret"], "close": m["close"], "mktcap": m["mktcap"]} for m in movers[:5]],
        "mkt_down": [{"ticker": m["ticker"], "ret": m["ret"], "close": m["close"], "mktcap": m["mktcap"]} for m in movers[-5:][::-1]],
    }

    vix_all = VIX["closes"]
    day_d = datetime.fromisoformat(day).date()
    vix = {"val": vix_all.get(day), "prev": vix_all.get(str(day_d - timedelta(days=1))), "source": "Yahoo"}

    def late_note(items):
        if not items:
            return None
        late = [n for n in items if n["late"]]
        if len(late) <= 0.8 * len(items):
            return None
        return min(n["seen"].astimezone(NY).date() for n in late).strftime("%m-%d")

    late_notes = {
        "movers": late_note([n for m in mover_rows for n in m["news"]]),
        "theme": late_note([n for _, n in theme_pick]),
        "feed": late_note(feed),
    }

    out = {
        "date": day,
        "late_notes": late_notes,
        "indexes": market["indexes"],
        "advancers": market["advancers"],
        "decliners": market["decliners"],
        "judgment": market.get("judgment"),
        "oneliner": market.get("oneliner"),
        "implication": market.get("implication"),
        "vix": vix,
        "movers": mover_rows,
        "mover_news": mover_news,
        "theme_news": [{"theme": th, **n} for th, n in theme_pick],
        "feed": feed,
        "earnings_week": week,
        "earnings_mine": mine,
        "econ": econ,
        "leaders": leaders,
        "events": market["events"],
        "held_tickers": held,
        "news_total": len(news_rows),
        "news_kept": len(news),
        "todo5": TODO5[day],
    }
    return out


TODO5 = {
    "2026-10-22": [
        "纳指 100 −2.86%、标普 −1.18%；AI 资本开支链 23 只同日下跌（4.7σ），判断为板块轮动而非全面恐慌。",
        "异动集中在半导体与光通信：NOK −14.8%、COHR −12.5%、LRCX −11.8%、LITE −11.5%，另有半导体设备 4 只集体下跌（2.3σ）。",
        "标的池 59 只中 42 只下跌、19 只波动超过 7%；纸面账户 AI 持仓占 26%，注意仓位集中度。",
        "VIX 19.03（Yahoo），较前日 16.68 明显抬升；必需消费 XLP +3.31%、区域银行 KRE +2.53% 领涨。",
        "下周进入财报密集期：GOOGL 10-28 盘后（预期 EPS $2.94），关注财报日历中持仓条目。",
    ],
    "2026-10-23": [
        "市场分化：标普 −0.52%、纳指基本持平，上涨家数仅占 34%；数据中心电力 −2.97%、HDD −2.39% 领跌。",
        "网络安全板块 +6.71% 逆势走强：CRWD +8.2%、ZS +7.3%、PANW +7.2%、FTNT +4.1%。",
        "BE −11.2% 为标的池最大跌幅；当天没有达到阈值的大事。",
        "VIX 19.45（Yahoo），连续两日维持在 19 上方。",
        "下周 GOOGL 10-28 盘后财报（预期 EPS $2.94）；宏观日历有 PCE 通胀等多项美国数据。",
    ],
}
VIX = {"closes": {}}


def fmt_t(ts):
    return ts.astimezone(NY).strftime("%H:%M")


def esc(s):
    return (str(s or "")).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def main():
    vix = load("vix.json")["chart"]["result"][0]
    for t, c in zip(vix["timestamp"], vix["indicators"]["quote"][0]["close"]):
        if c is not None:
            VIX["closes"][str(datetime.fromtimestamp(t, UTC).date())] = round(c, 2)

    days = {d: build_day(d) for d in DAYS}
    for d, blob in days.items():
        (ROOT / f"data-{d}.json").write_text(json.dumps(blob, ensure_ascii=False, indent=1, default=str))
    html = (ROOT / "template.html").read_text()
    css_path = Path("/Users/xuqingsong/workspace/inves-cog/src/inves_cog/web/investor.css")
    html = html.replace("__CSS__", css_path.read_text())
    html = html.replace("__DATA__", json.dumps(days, ensure_ascii=False, default=str))
    (ROOT / "index.html").write_text(html)
    for d, blob in days.items():
        print(d, "news", blob["news_total"], "kept", blob["news_kept"], "movers", len(blob["movers"]),
              "mover_news", len(blob["mover_news"]), "theme", len(blob["theme_news"]), "feed", len(blob["feed"]),
              "e_wk", len(blob["earnings_week"]), "e_mine", len(blob["earnings_mine"]), "econ", len(blob["econ"]),
              "events", len(blob["events"]))


if __name__ == "__main__":
    main()

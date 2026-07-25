#!/usr/bin/env python3
"""
collect_trustpilot.py — Trustpilot review + company-reply collector for the
CFD/forex broker social-response benchmark.

WHY PLAYWRIGHT: Trustpilot fronts its pages with a JavaScript bot-challenge
(Cloudflare-style). A plain urllib/requests GET returns HTTP 403. A real
browser passes the challenge; once the first page is loaded, same-origin
fetch() calls to ?page=N inherit the clearance and return clean JSON. All
review data (text, rating, dates, company reply, reviewer country/language)
lives in the page's <script id="__NEXT_DATA__"> blob — no HTML scraping needed.

INSTALL (one time, run locally — not needed inside the Claude browser env):
    pip install playwright
    playwright install chromium

USAGE:
    python collect_trustpilot.py exness.com --pages 40 --out ../data/exness_trustpilot.json
    python collect_trustpilot.py etoro.com  --pages 40 --out ../data/etoro_trustpilot.json

NOTES:
- Be polite: default 0.6s delay between page fetches. Do not lower it.
- Trustpilot's default .com view serves English reviews. To capture MENA /
  multilingual response behaviour, add locale variants later via the
  ?languages= param or country subdomains (see the plan's open item).
- source == "Organic" means an unsolicited review; "BusinessGeneratedLink"
  means the company invited it (review-gating signal — keep this field).
"""
import argparse
import json
import re
import sys
import time
from pathlib import Path

NEXT_RE = re.compile(
    r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>', re.S
)

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")


def trim(r):
    """Keep only the fields both analysis tracks need; compute response latency."""
    resp_h = None
    reply = r.get("reply") or None
    dates = r.get("dates") or {}
    if reply and reply.get("publishedDate") and dates.get("publishedDate"):
        from datetime import datetime
        fmt = lambda s: datetime.fromisoformat(s.replace("Z", "+00:00"))
        resp_h = round((fmt(reply["publishedDate"]) - fmt(dates["publishedDate"])).total_seconds() / 3600, 1)
    consumer = r.get("consumer") or {}
    labels = r.get("labels") or {}
    verification = (labels.get("verification") or {})
    return {
        "id": r.get("id"),
        "rating": r.get("rating"),
        "title": (r.get("title") or "")[:200],
        "text": (r.get("text") or "")[:5000],
        "lang": r.get("language"),
        "country": consumer.get("countryCode"),
        "verified": bool(verification.get("isVerified")),
        "experiencedDate": dates.get("experiencedDate"),
        "publishedDate": dates.get("publishedDate"),
        "source": r.get("source"),
        "replied": bool(reply),
        "replyDate": reply.get("publishedDate") if reply else None,
        "responseHours": resp_h,
        "replyMsg": (reply.get("message") or "")[:3000] if reply else None,
    }


def parse_html(html):
    m = NEXT_RE.search(html)
    if not m:
        return []
    data = json.loads(m.group(1))
    return data.get("props", {}).get("pageProps", {}).get("reviews", []) or []


def collect(domain, max_pages, sort, delay):
    from playwright.sync_api import sync_playwright
    out, seen = [], set()
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context(user_agent=UA, locale="en-US")
        page = ctx.new_page()
        # Load once to clear the bot challenge and get a same-origin context.
        page.goto(f"https://www.trustpilot.com/review/{domain}",
                  wait_until="domcontentloaded", timeout=60000)
        for pg in range(1, max_pages + 1):
            url = f"https://www.trustpilot.com/review/{domain}?page={pg}&sort={sort}"
            html = page.evaluate(
                "async (u) => { const r = await fetch(u, {credentials:'include'}); return await r.text(); }",
                url,
            )
            revs = parse_html(html)
            if not revs:
                print(f"  page {pg}: empty, stopping.", file=sys.stderr)
                break
            new = 0
            for r in revs:
                t = trim(r)
                if t["id"] and t["id"] not in seen:
                    seen.add(t["id"])
                    out.append(t)
                    new += 1
            print(f"  page {pg}: +{new} (total {len(out)})", file=sys.stderr)
            time.sleep(delay)
        browser.close()
    return out


def main():
    ap = argparse.ArgumentParser(description="Collect Trustpilot reviews + company replies.")
    ap.add_argument("domain", help="e.g. exness.com, etoro.com, xm.com")
    ap.add_argument("--pages", type=int, default=40, help="max pages (20 reviews each)")
    ap.add_argument("--sort", default="recency", choices=["recency", "relevance"])
    ap.add_argument("--delay", type=float, default=0.6, help="seconds between pages (be polite)")
    ap.add_argument("--out", required=True, help="output JSON path")
    args = ap.parse_args()

    print(f"Collecting {args.domain} (up to {args.pages} pages)...", file=sys.stderr)
    rows = collect(args.domain, args.pages, args.sort, args.delay)
    outp = Path(args.out)
    outp.parent.mkdir(parents=True, exist_ok=True)
    outp.write_text(json.dumps(
        {"domain": args.domain, "collected_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
         "count": len(rows), "reviews": rows},
        ensure_ascii=False, indent=2))
    print(f"Saved {len(rows)} reviews -> {outp}", file=sys.stderr)


if __name__ == "__main__":
    main()

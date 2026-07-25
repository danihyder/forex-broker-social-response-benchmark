#!/usr/bin/env python3
"""
prepare_dataset.py — turn raw collected reviews into the analysis-ready dataset.

What it adds to each review:
  features        complaint topics, from keyword dictionaries (pipe-separated,
                  "other" when nothing matches; a review can carry several)
  reply_type      substantive | redirect | regulator, classified from the
                  broker's public reply text
  is_template     1 when the reply's opening is reused >= 3 times by that broker
  word_count      words in title + body (used for language intensity)
  exclaim         number of exclamation marks
  is_organic      1 when the review was unsolicited rather than company-invited
  month           YYYY-MM, for the period filter

Usage:
    python scripts/prepare_dataset.py data/*.json
    python scripts/prepare_dataset.py data/exness_trustpilot.json data/xm_trustpilot.json
"""
import csv
import json
import pathlib
import re
import sys
from collections import Counter, defaultdict

BASE = pathlib.Path(__file__).resolve().parent.parent
OUT = BASE / "data" / "broker_reviews_clean.csv"
OUT_PHRASES = BASE / "data" / "complaint_phrases.json"

# Review text is stored as an excerpt rather than in full. Complaint phrases are
# computed from the complete text before truncation and saved alongside, so no
# analysis quality is lost.
TEXT_EXCERPT_CHARS = 300

# Function words and low-content tokens. A phrase is kept only when BOTH of its
# words carry content, which removes fragments such as "without any" or
# "still credited" that plain frequency counting surfaces.
PHRASE_STOPWORDS = set("""
the a an and or but to of in on for is are was were i my me we our you your it its this that
with at as be been being have has had not no so if then just get got can cant will would they
them he she from about all out up down over under more most very much too also only into their
when because after now like did do does am which what who how why any every another since even
back well many made make making take taken took put going want wants wanted need needs needed
said say says told tell telling ask asked keep keeps kept give given gave come came went know
knew think thought seem seems look looks feel felt still than times time multiple other others
same such per via able around already always never ever yet one two three first second next last
lot lots bit far near here there where while during before until again once each both few some
own thing things way ways getting ago best good great nice excellent
""".split())

# Minimum occurrences before a phrase is considered, to avoid ranking noise.
PHRASE_MIN_COUNT = 5

# Domain -> display name. Extend when adding brokers.
BRAND_BY_DOMAIN = {
    "exness.com": "Exness",
    "xm.com": "XM",
    "etoro.com": "eToro",
    "plus500.com": "Plus500",
}

# Complaint topics. Keyword dictionaries are deliberately explicit and readable
# so the tagging can be audited and adjusted rather than taken on trust.
FEATURES = {
    "withdrawal": ["withdraw", "payout", "cash out", "cashout", "get my money",
                   "take my money", "release my funds"],
    "deposit": ["deposit", "top up", "topup", "funding", "add funds"],
    "verification_kyc": ["verif", "kyc", " poi", " poa", "proof of", "document upload",
                         "identity", "id verification", "account approval"],
    "payments": ["upi", "bank transfer", "wire transfer", " crypto", "usdt", "skrill",
                 "neteller", "paypal", "e-wallet", "ewallet", "chargeback"],
    "platform_execution": ["slippage", "requote", "off quote", "off-quote", "ghost trade",
                           "manipulat", "freeze", "froze", "spread widen", "execution",
                           "stop loss hunt", "spike", "glitch", "platform crash", "server", "lag"],
    "account_access": ["locked", "blocked", "suspend", "restrict", "banned", "account closed",
                       "closed my account", "closure", "cannot access", "can't access",
                       "frozen account", "disabled my"],
    "support": ["no response", "unresponsive", "no reply", "live chat", "customer service",
                "support team", "ignored", "no answer", "no help", "waiting for days"],
    "bonus": ["bonus", "promo", "cashback", "contest", "campaign"],
    "scam_fraud": ["scam", "fraud", "thief", "thieves", "steal", "stole", "stolen", "robbed",
                   "cheat", "ponzi", "fake", "con artist"],
    "fees": ["hidden fee", "commission", "swap fee", "overnight fee", "inactivity fee",
             "hidden charge", "extra charge"],
}

REGULATOR_RE = re.compile(
    r"(financial commission|regulat|dispute resolution|ombudsman|fscs|fca complaint)", re.I)
REDIRECT_RE = re.compile(
    r"(contact (our )?support|live chat|support@|submit a (support )?request|personal area|"
    r"official (support )?channel|contact us|send us a|reach out|drop us|via email|email us)", re.I)

COLUMNS = ["brand", "rating", "month", "pub_date", "source", "is_organic", "country", "language",
           "verified", "replied", "response_hours", "reply_type", "is_template", "word_count",
           "exclaim", "features", "title", "text"]


def tag_features(text):
    low = text.lower()
    hits = [name for name, keys in FEATURES.items() if any(k in low for k in keys)]
    return hits or ["other"]


def classify_reply(message):
    if not message:
        return ""
    if REGULATOR_RE.search(message):
        return "regulator"
    if REDIRECT_RE.search(message):
        return "redirect"
    return "substantive"


def reply_signature(message):
    """First 80 characters, letters only. Near-identical openings share a signature."""
    return re.sub(r"\s+", " ", re.sub(r"[^a-z ]+", "", message.lower())).strip()[:80]


def main(paths):
    docs = []
    for p in paths:
        doc = json.load(open(p, encoding="utf-8"))
        domain = doc.get("domain", "")
        brand = BRAND_BY_DOMAIN.get(domain)
        if not brand:
            print(f"  skipping {p}: unknown domain {domain!r}", file=sys.stderr)
            continue
        docs.append((brand, doc.get("reviews", doc)))

    if not docs:
        sys.exit("No usable input files. Run collect_trustpilot.py first.")

    # Template detection needs per-broker reply frequencies, so count first.
    sig_counts = defaultdict(Counter)
    for brand, reviews in docs:
        for r in reviews:
            if r.get("replyMsg"):
                sig_counts[brand][reply_signature(r["replyMsg"])] += 1

    rows = []
    phrases = defaultdict(Counter)
    for brand, reviews in docs:
        for r in reviews:
            title, text = (r.get("title") or ""), (r.get("text") or "")
            full = f"{title} {text}"

            # Complaint phrases come from the complete text, before truncation.
            if (r.get("rating") or 0) <= 2:
                brand_tokens = {brand.lower(), "plus", "plus500", "etoros"}
                toks = [w for w in re.findall(r"[a-z']{3,}", full.lower())
                        if w not in brand_tokens]
                for i in range(len(toks) - 1):
                    a, b = toks[i], toks[i + 1]
                    if a in PHRASE_STOPWORDS or b in PHRASE_STOPWORDS or a == b:
                        continue
                    phrases[brand][f"{a} {b}"] += 1

            reply = r.get("replyMsg") or ""
            published = (r.get("publishedDate") or "")[:10]
            rows.append({
                "brand": brand,
                "rating": r.get("rating"),
                "month": published[:7],
                "pub_date": published,
                "source": r.get("source") or "",
                "is_organic": 1 if r.get("source") == "Organic" else 0,
                "country": r.get("country") or "",
                "language": r.get("lang") or "",
                "verified": 1 if r.get("verified") else 0,
                "replied": 1 if r.get("replied") else 0,
                "response_hours": r.get("responseHours") if r.get("responseHours") is not None else "",
                "reply_type": classify_reply(reply),
                "is_template": 1 if reply and sig_counts[brand][reply_signature(reply)] >= 3 else 0,
                "word_count": len(full.split()),
                "exclaim": full.count("!"),
                "features": "|".join(tag_features(full)),
                "title": " ".join(title.split())[:80],
                "text": " ".join(text.split())[:TEXT_EXCERPT_CHARS],
            })

    OUT.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=COLUMNS)
        writer.writeheader()
        writer.writerows(rows)

    # Rank phrases by distinctiveness rather than raw frequency. Frequency alone
    # returns the same generic terms for every broker ("customer service",
    # "trading account"); distinctiveness returns what sets each broker apart.
    totals = {b: sum(c.values()) for b, c in phrases.items()}
    pooled = Counter()
    for c in phrases.values():
        pooled.update(c)
    grand = sum(totals.values())

    distinctive = {}
    for b, counts in phrases.items():
        scored = []
        for phrase, n in counts.items():
            if n < PHRASE_MIN_COUNT:
                continue
            share_here = n / totals[b]
            share_elsewhere = (pooled[phrase] - n + 0.5) / max(grand - totals[b], 1)
            scored.append((round(share_here / share_elsewhere, 1), n, phrase))
        scored.sort(reverse=True)
        distinctive[b] = [[phrase, n, ratio] for ratio, n, phrase in scored[:15]]

    json.dump(distinctive, open(OUT_PHRASES, "w", encoding="utf-8"), indent=1)

    per_brand = Counter(r["brand"] for r in rows)
    print(f"wrote {OUT} | {len(rows)} reviews | " +
          ", ".join(f"{b} {n}" for b, n in sorted(per_brand.items())))
    print(f"wrote {OUT_PHRASES}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    main(sys.argv[1:])

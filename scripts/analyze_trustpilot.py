#!/usr/bin/env python3
"""
analyze_trustpilot.py — response-track analysis for the broker social-response
benchmark. Pure standard library (no pandas/numpy), so it runs anywhere. Reads a
file produced by collect_trustpilot.py and prints the response-management
metrics (reply rate by rating, reply time, reply type, source mix, complaint
topics, geography).

USAGE:
    python analyze_trustpilot.py ../data/exness_trustpilot.json
    python analyze_trustpilot.py ../data/*.json            # compare brands
"""
import json
import re
import statistics
import sys
from collections import Counter

REDIRECT_RE = re.compile(
    r"(contact (our )?support|live chat|support@|submit a support request|"
    r"personal area|official support channel|contact us)", re.I)
REGULATOR_RE = re.compile(r"(financial commission|regulat|dispute resolution)", re.I)

STOP = set(
    "the a an and or but to of in on for is are was were i my me we our you your it its this "
    "that with at as be have has had not no so if then just get got can cant will would they "
    "them he she from about all out up down over more most very much too also only into "
    "yourself have been their when because after now like".split())


def classify_reply(msg):
    if REGULATOR_RE.search(msg):
        return "regulator_deferral"
    if REDIRECT_RE.search(msg):
        return "redirect_to_private"
    return "public_substantive"


def median(xs):
    return round(statistics.median(xs), 1) if xs else None


def analyze(path):
    doc = json.load(open(path, encoding="utf-8"))
    rows = doc["reviews"] if isinstance(doc, dict) and "reviews" in doc else doc
    n = len(rows)
    neg = [r for r in rows if (r["rating"] or 0) <= 2]
    pos = [r for r in rows if (r["rating"] or 0) >= 4]
    repl = [r for r in rows if r["replied"]]
    hrs = sorted(r["responseHours"] for r in rows
                 if r["responseHours"] is not None and r["responseHours"] >= 0)

    reply_types = Counter(classify_reply(r["replyMsg"] or "") for r in repl)
    src = Counter(r["source"] for r in rows)
    src_neg = Counter(r["source"] for r in neg)
    countries = Counter(r["country"] for r in rows).most_common(10)

    toks = []
    for r in neg:
        for w in re.findall(r"[a-z]{3,}", (r["title"] + " " + r["text"]).lower()):
            if w not in STOP and "exness" not in w:
                toks.append(w)
    themes = Counter(toks).most_common(20)

    brand = doc.get("domain", path) if isinstance(doc, dict) else path
    rate = lambda part, whole: round(len(part) / len(whole) * 100, 1) if whole else None
    print(f"\n=== {brand}  (n={n}) ===")
    print(f"  negative (1-2*): {len(neg)}   positive (4-5*): {len(pos)}")
    print(f"  RESPONSE RATE  overall {rate(repl, rows)}%  |  "
          f"negative {rate([r for r in neg if r['replied']], neg)}%  |  "
          f"positive {rate([r for r in pos if r['replied']], pos)}%")
    if hrs:
        print(f"  RESPONSE TIME (h)  median {median(hrs)}  mean {round(sum(hrs)/len(hrs),1)}  "
              f"min {hrs[0]}  max {hrs[-1]}  (n={len(hrs)})")
    print(f"  REPLY TYPES  {dict(reply_types)}")
    print(f"  SOURCE (all)  {dict(src)}")
    print(f"  SOURCE (negatives only)  {dict(src_neg)}   <- review-gating signal")
    print(f"  TOP COUNTRIES  {countries}")
    print(f"  NEGATIVE COMPLAINT TERMS  {[t for t,_ in themes]}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    for p in sys.argv[1:]:
        analyze(p)

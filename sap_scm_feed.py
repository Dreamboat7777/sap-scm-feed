# -*- coding: utf-8 -*-
"""
Self-contained SAP SCM customer-story -> RSS builder.
Runs with Python 3 standard library ONLY (no pip installs), so it works
out-of-the-box on GitHub Actions runners.

Usage:
    python sap_scm_feed.py [output_rss.xml]
Default output: sap_scm_customer_stories.xml (next to this script)

How it works:
  The listing page is React-rendered; its data comes from an internal Solr
  endpoint. The endpoint DOES work over plain HTTP as long as the full
  componentPath is sent (it 404s only when params are stripped). We page
  through it with the exact query the page issues, parse JSON, emit RSS 2.0.
"""
import json, os, sys, re, html, time, urllib.request, urllib.error
from datetime import datetime
from email.utils import formatdate
from calendar import timegm
from math import ceil

# Page-1 URL captured verbatim from the live page's own XHR. Only the
# encoded "page":N value changes between pages. If SAP ever restructures the
# page component, update the componentPath here by re-capturing it from the
# browser network tab.
SOLR_PAGE1 = (
    "https://www.sap.com/bin/sapdx/solrsearch?showEmptyTags=false&isResourceCenter=true"
    "&highlighting=false&hideFacets=false&additionalProcess=false&showEventInfo=true"
    "&isDateRange=false&isEventPeriod=false&fuzzySearch=false&isFullTextSearch=false"
    "&pageLocale=en_hk&json=%7B%22componentPath%22%3A%22%2Fcontent%2Fsapdx%2Fcountries"
    "%2Fen_hk%2Fproducts%2Fscm%2Fcustomer-stories%2Fjcr%3Acontent%2Fpar%2F"
    "responsivegrid_453157306%2Fsection%2Fsection-par%2Fresourcecenterdynamic%2Fitems%2F"
    "item_1709578723721%22%2C%22search%22%3A%5B%5D%2C%22pagePath%22%3A%22%2Fcontent%2F"
    "sapdx%2Fcountries%2Fen_hk%2Fproducts%2Fscm%2Fcustomer-stories%22%2C%22page%22%3A1"
    "%2C%22pageCount%22%3A48%2C%22sortName%22%3A%22creationDate%22%2C%22sortType%22%3A"
    "%22desc%22%2C%22isMultiselectSearch%22%3Afalse%7D"
)
PAGE_SIZE = 48
BASE = "https://www.sap.com/hk"
PAGE_URL = "https://www.sap.com/hk/products/scm/customer-stories.html?sort=latest_desc"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/126.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": PAGE_URL,
    "X-Requested-With": "XMLHttpRequest",
}


def page_url(p):
    # Use a replacement callback: the replacement text itself contains '%'
    # encodings, which must NOT go through Python %-formatting.
    return re.sub(r"%22page%22%3A\d+",
                  lambda m: "%22page%22%3A" + str(p), SOLR_PAGE1)


def fetch(p, retries=3):
    last = None
    for attempt in range(retries):
        try:
            req = urllib.request.Request(page_url(p), headers=HEADERS)
            with urllib.request.urlopen(req, timeout=40) as r:
                raw = r.read().decode("utf-8", "replace")
            if raw.lstrip()[:1] != "{":
                raise ValueError("non-JSON response (likely 404 page)")
            return json.loads(raw)
        except Exception as e:  # noqa
            last = e
            time.sleep(2 * (attempt + 1))
    raise RuntimeError("page %d failed after %d tries: %r" % (p, retries, last))


def collect():
    first = fetch(1)
    total = int(first.get("count", 0))
    pages = max(1, ceil(total / PAGE_SIZE))
    out = list(first.get("results", []))
    for p in range(2, pages + 1):
        out.extend(fetch(p).get("results", []))
    # de-dupe by publicUrl
    seen, rows = set(), []
    for r in out:
        u = r.get("publicUrl") or r.get("basicUrl") or ""
        if not u or u in seen:
            continue
        seen.add(u)
        rows.append({
            "t": r.get("titleNotTokenized") or r.get("title") or "",
            "u": u,
            "d": r.get("creationDate") or "",
            "pd": r.get("publishDate") or "",
            "desc": r.get("descriptionNotTokenized") or r.get("description") or "",
        })
    return total, rows


def parse_date(s):
    s = (s or "").strip()
    for fmt in ("%b %d, %Y, %I:%M:%S %p", "%b %d, %Y, %I:%M %p", "%b %d, %Y"):
        try:
            return formatdate(timegm(datetime.strptime(s, fmt).timetuple()), usegmt=True)
        except ValueError:
            continue
    return None


def x(s):
    return html.escape(s or "", quote=True)


def build_rss(rows):
    now = formatdate(usegmt=True)
    p = ['<?xml version="1.0" encoding="UTF-8"?>',
         '<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom">', '<channel>',
         '<title>SAP Supply Chain Management Customer Stories</title>',
         '<link>%s</link>' % PAGE_URL,
         '<description>Latest SAP SCM customer success stories (articles &amp; videos), newest first.</description>',
         '<language>en-us</language>', '<lastBuildDate>%s</lastBuildDate>' % now]
    for it in rows:
        url = it["u"] if it["u"].startswith("http") else BASE + it["u"]
        kind = "Video" if "/assetdetail/" in it["u"] else "Article"
        title = html.unescape(it["t"])
        desc = html.unescape(it["desc"])
        pub = parse_date(it["d"]) or parse_date(it["pd"])
        p.append('<item>')
        p.append('<title>[%s] %s</title>' % (kind, x(title)))
        p.append('<link>%s</link>' % x(url))
        p.append('<guid isPermaLink="true">%s</guid>' % x(url))
        if pub:
            p.append('<pubDate>%s</pubDate>' % pub)
        p.append('<description>%s</description>' % x(desc))
        p.append('</item>')
    p.append('</channel></rss>')
    return "\n".join(p)


def main():
    here = os.path.dirname(os.path.abspath(__file__))
    out_rss = sys.argv[1] if len(sys.argv) > 1 else os.path.join(here, "sap_scm_customer_stories.xml")
    total, rows = collect()
    rss = build_rss(rows)
    with open(out_rss, "w", encoding="utf-8") as f:
        f.write(rss)
    # also refresh the raw snapshot next to the output RSS
    raw_path = os.path.join(os.path.dirname(out_rss), "sap_scm_cases_raw.json")
    with open(raw_path, "w", encoding="utf-8") as f:
        json.dump(rows, f, ensure_ascii=False, indent=2)
    print("server count=%d, collected unique=%d -> %s (%d bytes)"
          % (total, len(rows), out_rss, len(rss.encode("utf-8"))))
    if len(rows) < total * 0.9:
        print("WARNING: collected far fewer than server count; componentPath may be stale.", file=sys.stderr)
        sys.exit(2)


if __name__ == "__main__":
    main()

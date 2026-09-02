# SAP SCM Customer Stories → RSS

Auto-updating RSS feed of SAP Supply Chain Management customer success stories
(listing: https://www.sap.com/hk/products/scm/customer-stories.html?sort=latest_desc).

## Why this exists
The SAP listing is a React page whose items load via an internal Solr endpoint,
so ordinary RSS readers (Inoreader/Feedly) and no-JS feed builders see an empty
page. This repo fetches that endpoint with its **full componentPath** (plain
HTTPS works — no browser needed), converts all stories to RSS 2.0, and commits
the refreshed feed on a schedule.

## Files
- `sap_scm_feed.py` — stdlib-only fetcher + RSS builder (no pip installs).
- `.github/workflows/update_feed.yml` — runs daily 09:23 Asia/Shanghai (01:23 UTC);
  also runnable manually via **Actions → Run workflow**.
- `feed/sap_scm_customer_stories.xml` — the generated public feed.

## Subscribe URL (add this to Inoreader/Feedly)
```
https://raw.githubusercontent.com/<OWNER>/<REPO>/main/feed/sap_scm_customer_stories.xml
```
(Replace `<OWNER>/<REPO>` after creation. Add `?nocache=1` if a reader caches too hard.)

## Maintenance
- If SAP restructures the page component, the script exits with a warning
  ("componentPath may be stale"). Re-capture the page-1 Solr URL from the
  browser network tab and update `SOLR_PAGE1` in `sap_scm_feed.py`.
- Change cadence by editing `cron` in the workflow (times are UTC).

# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""Collect TikTok or Instagram comments and posts through Apify. This costs money.

Usage (each prints the most it can cost, and runs only with --yes):
  uv run scripts/collect_social.py tiktok-comments    --label gym-drinks --urls urls.txt --per-post 200
  uv run scripts/collect_social.py instagram-comments --label gym-drinks --urls urls.txt --per-post 200
  uv run scripts/collect_social.py tiktok-posts       --label rivals --accounts acct1,acct2 --per-account 60
  uv run scripts/collect_social.py instagram-reels    --label rivals --accounts acct1,acct2 --per-account 60
  uv run scripts/collect_social.py tiktok-hashtag     --label scene --tags gymtok,preworkout --per-tag 60

urls.txt has one TikTok or Instagram post link per line.
Needs APIFY_TOKEN=... in the .env file in this folder (Apify Console > Settings >
API & Integrations > Personal API tokens).

Comments go to data/raw/social/<label>/rows.jsonl.gz, ready for clean.py.
Posts go to hooks/posts_<label>.csv, with views, likes and the caption, ready for
score_posts.py. The raw Apify output is kept beside each file as items.jsonl.gz.

Spending guard: the run is capped at the item count you ask for, and at the dollar figure
printed before it starts (sent to Apify as maxTotalChargeUsd). Prices are the Free-plan
prices from each actor's Pricing tab, checked 19 November 2026. Check the tab before a big run.
"""
import argparse
import csv
import datetime as dt
import gzip
import json
import os
import pathlib
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

API = "https://api.apify.com/v2"
PRESETS = {
    "tiktok-comments":    {"actor": "clockworks~tiktok-comments-scraper", "per_1000": 5.00, "kind": "comments"},
    "instagram-comments": {"actor": "apify~instagram-comment-scraper", "per_1000": 2.60, "kind": "comments"},
    "tiktok-posts":       {"actor": "clockworks~tiktok-scraper", "per_1000": 5.00, "kind": "posts"},
    "tiktok-hashtag":     {"actor": "clockworks~tiktok-scraper", "per_1000": 5.00, "kind": "posts"},
    "instagram-reels":    {"actor": "apify~instagram-reel-scraper", "per_1000": 2.60, "kind": "posts"},
}


def token():
    env = pathlib.Path(".env")
    if env.exists():
        for line in env.read_text().splitlines():
            if line.strip().startswith("APIFY_TOKEN="):
                return line.split("=", 1)[1].strip().strip('"').strip("'")
    if os.environ.get("APIFY_TOKEN"):
        return os.environ["APIFY_TOKEN"]
    sys.exit("No APIFY_TOKEN found. Add a line APIFY_TOKEN=your-token to the .env file in this folder.")


def call(method, path, tok, body=None, params=None):
    url = API + path + ("?" + urllib.parse.urlencode(params) if params else "")
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method,
                                 headers={"Authorization": f"Bearer {tok}", "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        msg = e.read().decode(errors="replace")[:300]
        sys.exit(f"Apify refused the request ({e.code}): {msg}")


def to_ts(v):
    if v is None:
        return None
    if isinstance(v, (int, float)):
        return int(v)
    try:
        return int(dt.datetime.fromisoformat(str(v).replace("Z", "+00:00")).timestamp())
    except ValueError:
        return None


def handle(url):
    parts = [p for p in urllib.parse.urlparse(url or "").path.split("/") if p]
    return parts[0].lstrip("@") if parts and parts[0].startswith("@") else (parts[0] if parts else "")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("preset", choices=PRESETS)
    ap.add_argument("--label", required=True, help="a short name for this collection, such as gym-drinks")
    ap.add_argument("--urls", help="file with one post link per line (comment presets)")
    ap.add_argument("--accounts", help="comma-separated account names, without @ (post presets)")
    ap.add_argument("--tags", help="comma-separated hashtags, without # (tiktok-hashtag)")
    ap.add_argument("--per-post", type=int, default=200)
    ap.add_argument("--per-account", type=int, default=60)
    ap.add_argument("--per-tag", type=int, default=60)
    ap.add_argument("--yes", action="store_true", help="actually run it and spend the money")
    a = ap.parse_args()
    pre = PRESETS[a.preset]
    if a.preset in ("tiktok-comments", "instagram-comments"):
        if not a.urls:
            sys.exit("Give --urls, a file with one post link per line.")
        urls = [u.strip() for u in pathlib.Path(a.urls).read_text().splitlines() if u.strip().startswith("http")]
        if not urls:
            sys.exit(f"No links found in {a.urls}. Put one post link per line, each starting with http.")
        items = len(urls) * a.per_post
        body = ({"postURLs": urls, "commentsPerPost": a.per_post, "maxRepliesPerComment": 0}
                if a.preset == "tiktok-comments" else {"directUrls": urls, "resultsLimit": a.per_post})
        what = f"{len(urls)} posts x up to {a.per_post} comments"
    elif a.preset == "tiktok-hashtag":
        tags = [t.strip().lstrip("#") for t in (a.tags or "").split(",") if t.strip()]
        if not tags:
            sys.exit("Give --tags, for example --tags gymtok,preworkout")
        items = len(tags) * a.per_tag
        body = {"hashtags": tags, "resultsPerPage": a.per_tag}
        what = f"{len(tags)} hashtags x up to {a.per_tag} posts"
    else:
        accts = [x.strip().lstrip("@") for x in (a.accounts or "").split(",") if x.strip()]
        if not accts:
            sys.exit("Give --accounts, for example --accounts brand1,creator2")
        items = len(accts) * a.per_account
        body = ({"profiles": accts, "resultsPerPage": a.per_account, "profileSorting": "latest"}
                if a.preset == "tiktok-posts" else {"username": accts, "resultsLimit": a.per_account})
        what = f"{len(accts)} accounts x up to {a.per_account} posts"
    cost = round(items / 1000 * pre["per_1000"] + 0.05, 2)
    print(f"{a.preset}: {what} = up to {items:,} items.")
    print(f"Most this can cost: about ${cost:.2f} (at ${pre['per_1000']:.2f} per 1,000 items, plus the start fee).")
    if not a.yes:
        print("Nothing has run. Add --yes to the same command to run it.")
        return
    tok = token()
    run = call("POST", f"/acts/{pre['actor']}/runs", tok, body,
               {"maxItems": items, "maxTotalChargeUsd": cost})["data"]
    print(f"Started. You can watch it at https://console.apify.com/actors/runs/{run['id']}")
    while run["status"] in ("READY", "RUNNING"):
        time.sleep(15)
        run = call("GET", f"/actor-runs/{run['id']}", tok)["data"]
        print(f"  {run['status'].lower()}...")
    if run["status"] != "SUCCEEDED":
        print(f"The run ended as {run['status']}. Whatever it collected is saved below.")
    got, offset = [], 0
    while True:
        page = call("GET", f"/datasets/{run['defaultDatasetId']}/items", tok, params={"offset": offset, "limit": 1000, "clean": 1})
        if not isinstance(page, list) or not page:
            break
        got += page; offset += len(page)
    print(f"Collected {len(got):,} items.")
    if pre["kind"] == "comments":
        folder = pathlib.Path("data/raw/social") / a.label
        folder.mkdir(parents=True, exist_ok=True)
        with gzip.open(folder / "items.jsonl.gz", "wt", encoding="utf-8") as f:
            for it in got:
                f.write(json.dumps(it, ensure_ascii=False) + "\n")
        n = 0
        with gzip.open(folder / "rows.jsonl.gz", "wt", encoding="utf-8") as f:
            for it in got:
                if it.get("error"):
                    continue
                if a.preset == "tiktok-comments":
                    post = it.get("videoWebUrl") or it.get("submittedVideoUrl") or ""
                    row = dict(id="tiktok:" + str(it.get("cid")), source="tiktok", community=handle(post),
                               kind="comment", thread="tiktok:" + post, thread_title="",
                               author=it.get("uid") or it.get("uniqueId"),
                               created_utc=it.get("createTime") or to_ts(it.get("createTimeISO")),
                               text=it.get("text") or "", likes=it.get("diggCount"), replies=it.get("replyCommentTotal"))
                else:
                    post = it.get("postUrl") or ""
                    row = dict(id="instagram:" + str(it.get("id")), source="instagram", community=handle(post),
                               kind="comment", thread="instagram:" + post, thread_title="",
                               author=it.get("ownerUsername"), created_utc=to_ts(it.get("timestamp")),
                               text=it.get("text") or "", likes=it.get("likesCount"), replies=it.get("repliesCount"))
                f.write(json.dumps(row, ensure_ascii=False) + "\n"); n += 1
        print(f"Saved {n:,} comments to {folder}/rows.jsonl.gz. Run scripts/clean.py next.")
    else:
        folder = pathlib.Path("hooks"); folder.mkdir(exist_ok=True)
        with gzip.open(folder / f"items_{a.label}.jsonl.gz", "wt", encoding="utf-8") as f:
            for it in got:
                f.write(json.dumps(it, ensure_ascii=False) + "\n")
        rows = []
        for it in got:
            if it.get("error"):
                continue
            if a.preset.startswith("tiktok"):
                rows.append(dict(url=it.get("webVideoUrl"), account=(it.get("authorMeta") or {}).get("name", ""),
                                 date=(it.get("createTimeISO") or "")[:10],
                                 format="slideshow" if it.get("isSlideshow") else "video",
                                 views=it.get("playCount"), likes=it.get("diggCount"), comments=it.get("commentCount"),
                                 shares=it.get("shareCount"), saves=it.get("collectCount"),
                                 duration=(it.get("videoMeta") or {}).get("duration"),
                                 caption=" ".join((it.get("text") or "").split()), media_url=""))
            else:
                rows.append(dict(url=it.get("url"), account=it.get("ownerUsername", ""),
                                 date=(it.get("timestamp") or "")[:10], format="reel",
                                 views=it.get("videoPlayCount") or it.get("videoViewCount"), likes=it.get("likesCount"),
                                 comments=it.get("commentsCount"), shares=it.get("reshareCount"), saves="",
                                 duration=it.get("videoDuration"),
                                 caption=" ".join((it.get("caption") or "").split()),
                                 media_url=it.get("audioUrl") or it.get("videoUrl") or ""))
        out = folder / f"posts_{a.label}.csv"
        with out.open("w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0].keys()) if rows else ["url"])
            w.writeheader(); w.writerows(rows)
        print(f"Saved {len(rows):,} posts to {out}. Run scripts/score_posts.py --file {out} next.")


if __name__ == "__main__":
    main()

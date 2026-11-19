# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""Check candidate subreddits before you collect: how busy each one is, and 8 posts from it.

Usage:
  uv run scripts/browse.py energydrinks Monster pre_workout

For each subreddit it prints posts per month and comments per month (estimated from the
newest 100 of each) and 8 posts picked at random from the newest 100, with no search term,
so what you see is what the community talks about, not what you looked for.
Writes nothing. Free. Uses the Arctic Shift archive, one request per second.
"""
import json
import random
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

BASE = "https://arctic-shift.photon-reddit.com/api"


def get(kind, sub, fields):
    url = f"{BASE}/{kind}/search?" + urllib.parse.urlencode(
        {"subreddit": sub, "limit": 100, "sort": "desc", "fields": fields})
    for attempt in range(5):
        time.sleep(1)
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "buyer-research-starter-kit/1.0"})
            with urllib.request.urlopen(req, timeout=90) as r:
                return json.load(r).get("data") or []
        except urllib.error.HTTPError as e:
            time.sleep(20 * (attempt + 1))
        except (urllib.error.URLError, TimeoutError):
            time.sleep(20 * (attempt + 1))
    return None


def per_month(rows):
    if not rows or len(rows) < 2:
        return 0
    span = max(r["created_utc"] for r in rows) - min(r["created_utc"] for r in rows)
    days = max(span / 86400, 1 / 24)
    return round(len(rows) / days * 30.44)


def main():
    subs = [s.removeprefix("r/").strip("/") for s in sys.argv[1:]]
    if not subs:
        sys.exit("Give one or more subreddit names, for example: uv run scripts/browse.py energydrinks")
    for sub in subs:
        posts = get("posts", sub, "title,selftext,created_utc,num_comments")
        comments = get("comments", sub, "created_utc")
        print(f"\n=== r/{sub}")
        if posts is None:
            print("  The archive didn't answer. Try this one again in a minute.")
            continue
        if not posts:
            print("  No posts found. Check the spelling, or the community may be private or banned.")
            continue
        print(f"  About {per_month(posts):,} posts a month and {per_month(comments or []):,} comments a month")
        readable = [p for p in posts if (p.get("selftext") or "").strip() not in ("[removed]", "[deleted]")]
        print(f"  {len(readable)} of the newest {len(posts)} posts are still readable")
        random.seed(sub)
        for p in random.sample(readable, min(8, len(readable))):
            body = " ".join((p.get("selftext") or "").split())[:140]
            print(f"  - {p.get('title', '')[:110]}" + (f"  | {body}" if body else ""))


if __name__ == "__main__":
    main()

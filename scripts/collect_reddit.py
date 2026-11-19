# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""Collect posts and comments from one subreddit through the free Arctic Shift archive.

Usage:
  uv run scripts/collect_reddit.py --sub energydrinks --months 6
  uv run scripts/collect_reddit.py --sub energydrinks --pilot
  uv run scripts/collect_reddit.py --sub energydrinks --months 6 --refresh   (add newer rows)

Writes data/raw/reddit/<sub>/posts.jsonl.gz and comments.jsonl.gz.
--pilot collects the last 7 days only, up to 2,000 rows, into data/raw/reddit/<sub>__pilot/.
clean.py --pilot cleans pilot folders only, and clean.py without it skips them.
Safe to stop and run again: it resumes from data/raw/reddit/<sub>/checkpoint.json.
Pacing: one request at a time, at least 1 second apart, and it waits when the archive
asks it to slow down. Never touches reddit.com.
"""
import argparse
import datetime as dt
import gzip
import json
import pathlib
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

BASE = "https://arctic-shift.photon-reddit.com/api"
AGENT = "buyer-research-starter-kit/1.0"
FIELDS = {
    "posts": "id,author,title,selftext,created_utc,score,num_comments,subreddit,distinguished,over_18",
    "comments": "id,author,body,created_utc,score,link_id,parent_id,subreddit,distinguished",
}
_last_call = 0.0


def get(kind, params):
    global _last_call
    url = f"{BASE}/{kind}/search?" + urllib.parse.urlencode(params)
    for attempt in range(8):
        wait = 1.0 - (time.time() - _last_call)
        if wait > 0:
            time.sleep(wait)
        _last_call = time.time()
        try:
            req = urllib.request.Request(url, headers={"User-Agent": AGENT})
            with urllib.request.urlopen(req, timeout=90) as r:
                return json.load(r).get("data") or []
        except urllib.error.HTTPError as e:
            if e.code == 429:
                reset = e.headers.get("X-RateLimit-Reset") or "60"
                try:
                    pause = max(5, int(float(reset)))
                except ValueError:
                    pause = 60
                print(f"  The archive asked us to slow down. Waiting {pause} seconds.")
                time.sleep(pause + 1)
                continue
            if e.code >= 500:
                print(f"  The archive returned an error ({e.code}). Retrying shortly.")
                time.sleep(15 * (attempt + 1))
                continue
            try:
                why = json.load(e).get("error", "")
            except Exception:
                why = ""
            if "timeout" in why.lower():
                print("  The archive timed out. Waiting 20 seconds, then retrying.")
                time.sleep(20)
                continue
            sys.exit(f"The archive refused the request ({e.code}: {why}). Check the subreddit name.")
        except (urllib.error.URLError, TimeoutError, ConnectionError) as e:
            print(f"  Network problem ({e}). Retrying shortly.")
            time.sleep(15 * (attempt + 1))
    sys.exit("The archive isn't responding. Wait a few minutes, then run the same command again. "
             "It carries on from where it stopped.")


def collect(sub, kind, start, end, cap, folder, state):
    out = folder / f"{kind}.jsonl.gz"
    after = state.get(kind, {}).get("after", start)
    count = state.get(kind, {}).get("count", 0)
    seen_last = set(state.get(kind, {}).get("seen_last", []))
    if state.get(kind, {}).get("done"):
        print(f"{kind}: already complete ({count} rows).")
        return count
    print(f"{kind}: collecting from r/{sub}...")
    with gzip.open(out, "at", encoding="utf-8") as f:
        while True:
            if cap and count >= cap:
                break
            batch = get(kind, {"subreddit": sub, "after": after, "before": end,
                               "limit": 100, "sort": "asc", "fields": FIELDS[kind]})
            fresh = [x for x in batch if x.get("id") not in seen_last]
            if not batch or not fresh:
                if batch and not fresh:
                    after += 1  # every row in this second is already saved
                    continue
                state[kind] = {"after": after, "count": count, "done": True, "seen_last": []}
                break
            if cap:
                fresh = fresh[: max(0, cap - count)]
            for row in fresh:
                f.write(json.dumps(row, ensure_ascii=False) + "\n")
            count += len(fresh)
            newest = max(int(x["created_utc"]) for x in batch)
            seen_last = {x["id"] for x in batch if int(x["created_utc"]) == newest}
            after = newest
            state[kind] = {"after": after, "count": count, "done": False, "seen_last": sorted(seen_last)}
            (folder / "checkpoint.json").write_text(json.dumps(state))
            day = dt.datetime.fromtimestamp(newest, dt.timezone.utc).strftime("%d %b %Y")
            print(f"  {count} {kind} so far, up to {day}")
    (folder / "checkpoint.json").write_text(json.dumps(state))
    return count


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--sub", required=True, help="subreddit name, without r/")
    p.add_argument("--months", type=int, default=6, help="how far back to go (default 6)")
    p.add_argument("--max-rows", type=int, default=0, help="stop after this many rows in total (pilot runs)")
    p.add_argument("--posts-only", action="store_true", help="skip comments")
    p.add_argument("--pilot", action="store_true", help="last 7 days only, up to 2,000 rows, kept apart")
    p.add_argument("--refresh", action="store_true", help="add rows posted since the last run")
    a = p.parse_args()
    sub = a.sub.removeprefix("r/").strip("/")
    end = int(time.time())
    days = 7 if a.pilot else 30.44 * a.months
    if a.pilot:
        a.months = 0
        a.max_rows = a.max_rows or 2000
    start = int((dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=days)).timestamp())
    folder = pathlib.Path("data/raw/reddit") / (sub + ("__pilot" if a.pilot else ""))
    folder.mkdir(parents=True, exist_ok=True)
    cp = folder / "checkpoint.json"
    state = json.loads(cp.read_text()) if cp.exists() else {}
    if state.get("window") and state["window"]["months"] != a.months:
        sys.exit("This subreddit was started with a different --months. Delete its folder in data/raw/reddit to start again.")
    state.setdefault("window", {"start": start, "months": a.months, "max_rows": a.max_rows})
    if a.refresh:
        for kind in ("posts", "comments"):
            if kind in state:
                state[kind]["done"] = False
        print("Refreshing: collecting rows posted since the last run.")
    start = state["window"]["start"]
    cap_posts = a.max_rows // 2 if a.max_rows and not a.posts_only else a.max_rows
    n_posts = collect(sub, "posts", start, end, cap_posts, folder, state)
    n_comments = 0
    if not a.posts_only:
        cap_comments = (a.max_rows - n_posts) if a.max_rows else 0
        n_comments = collect(sub, "comments", start, end, cap_comments, folder, state)
    print(f"Done: r/{sub}, {n_posts} posts and {n_comments} comments in {folder}")


if __name__ == "__main__":
    main()

# /// script
# requires-python = ">=3.10"
# dependencies = ["pandas>=2.2", "pyarrow>=16"]
# ///
"""Clean everything in data/raw into one versioned corpus file, with a manifest.

Usage:
  uv run scripts/clean.py
  uv run scripts/clean.py --note "added r/pre_workout"
  uv run scripts/clean.py --pilot --note "pilot"     (pilot folders only)

Reads:  data/raw/reddit/<sub>/posts.jsonl.gz and comments.jsonl.gz
        data/raw/social/<label>/rows.jsonl.gz   (from collect_social.py)
        data/raw/youtube/*.info.json             (from yt-dlp --write-comments)
Writes: data/corpus/v<N>/rows.parquet and data/corpus/v<N>/manifest.json, a new N each run.

What it does, in order:
  - replaces every username with a random-looking id, so one person keeps one id across
    sources but no name is stored (the key is in data/.salt; don't share it);
  - replaces links, emails, phone numbers and @ or u/ mentions in the text;
  - drops removed or deleted posts, deleted authors, bots, moderator posts, empty text,
    duplicate ids, and the same text posted twice by the same person in the same place.
Every drop is counted by reason in the manifest. Nothing is silently capped.
"""
import argparse
import datetime as dt
import glob
import gzip
import hashlib
import json
import os
import pathlib
import re
import secrets

import pandas as pd

URL = re.compile(r"https?://\S+|www\.\S+")
EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
PHONE = re.compile(r"(?<!\w)(?:\+?\d[\d\s().-]{7,}\d)(?!\w)")
MENTION = re.compile(r"(?<!\w)(?:/?u/[\w-]+|@[\w.]+)")
GONE = {"[removed]", "[deleted]", "[ Removed by Reddit ]", "[removed by reddit]"}
BOTISH = re.compile(r"(?:^automoderator$|bot$|^bot[-_]|_bot_)", re.I)


def salt():
    p = pathlib.Path("data/.salt")
    if not p.exists():
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(secrets.token_hex(16))
    return p.read_text().strip()


def scrub(text):
    text = URL.sub("[link]", text)
    text = EMAIL.sub("[email]", text)
    text = PHONE.sub("[phone]", text)
    text = MENTION.sub("[user]", text)
    return " ".join(text.split())


def read_gz(path):
    with gzip.open(path, "rt", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                yield json.loads(line)


PILOT = False


def reddit_files(kind):
    files = glob.glob(f"data/raw/reddit/*/{kind}.jsonl.gz")
    return [f for f in files if pathlib.Path(f).parent.name.endswith("__pilot") == PILOT]


def reddit_rows():
    titles = {}
    for path in reddit_files("posts"):
        for p in read_gz(path):
            titles[p["id"]] = p.get("title") or ""
    for path in reddit_files("posts"):
        for p in read_gz(path):
            body = (p.get("selftext") or "").strip()
            title = (p.get("title") or "").strip()
            yield dict(id="reddit:" + p["id"], source="reddit", community=p.get("subreddit", ""),
                       kind="post", thread="reddit:" + p["id"], thread_title=title,
                       author=p.get("author"), created_utc=p.get("created_utc"),
                       text=(title + "\n\n" + body).strip() if body not in GONE else "[removed]",
                       likes=p.get("score"), replies=p.get("num_comments"),
                       moderator=p.get("distinguished") in ("moderator", "admin"))
    for path in reddit_files("comments"):
        for c in read_gz(path):
            thread = (c.get("link_id") or "").removeprefix("t3_")
            yield dict(id="reddit:" + c["id"], source="reddit", community=c.get("subreddit", ""),
                       kind="comment", thread="reddit:" + thread, thread_title=titles.get(thread, ""),
                       author=c.get("author"), created_utc=c.get("created_utc"),
                       text=(c.get("body") or "").strip(), likes=c.get("score"), replies=None,
                       moderator=c.get("distinguished") in ("moderator", "admin"))


def social_rows():
    if PILOT:
        return
    for path in glob.glob("data/raw/social/*/rows.jsonl.gz"):
        for r in read_gz(path):
            r.setdefault("moderator", False)
            yield r


def youtube_rows():
    if PILOT:
        return
    for path in glob.glob("data/raw/youtube/*.info.json"):
        info = json.loads(pathlib.Path(path).read_text())
        vid = info.get("id", pathlib.Path(path).stem)
        for c in info.get("comments") or []:
            if c.get("author_is_uploader"):
                continue
            yield dict(id="youtube:" + str(c.get("id")), source="youtube",
                       community=info.get("channel") or info.get("uploader") or "",
                       kind="comment", thread="youtube:" + vid, thread_title=info.get("title", ""),
                       author=c.get("author_id") or c.get("author"), created_utc=c.get("timestamp"),
                       text=(c.get("text") or "").strip(), likes=c.get("like_count"), replies=None,
                       moderator=False)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--note", default="", help="a line saying what changed in this version")
    ap.add_argument("--pilot", action="store_true", help="clean the pilot folders only")
    a = ap.parse_args()
    global PILOT
    PILOT = a.pilot
    key = salt()
    dropped = {}
    kept, seen_ids, seen_text = [], set(), set()

    def drop(reason):
        dropped[reason] = dropped.get(reason, 0) + 1

    raw = 0
    for r in [*reddit_rows(), *social_rows(), *youtube_rows()]:
        raw += 1
        text = (r.get("text") or "").strip()
        author = r.get("author")
        if r["id"] in seen_ids:
            drop("duplicate id"); continue
        seen_ids.add(r["id"])
        if not text or text.lower() in {g.lower() for g in GONE} or text.endswith("[removed]"):
            drop("removed, deleted or empty"); continue
        if not author or author in ("[deleted]", "[removed]"):
            drop("deleted author"); continue
        if BOTISH.search(str(author)):
            drop("bot account"); continue
        if r.get("moderator"):
            drop("moderator post"); continue
        clean = scrub(text)
        if len(clean) < 3:
            drop("removed, deleted or empty"); continue
        pid = hashlib.sha256((key + str(author)).encode()).hexdigest()[:16]
        repeat = (pid, r.get("community"), clean.lower())
        if repeat in seen_text:
            drop("same text repeated by same person"); continue
        seen_text.add(repeat)
        ts = r.get("created_utc")
        try:
            ts = int(float(ts))
        except (TypeError, ValueError):
            ts = None
        kept.append(dict(id=r["id"], source=r["source"], community=r.get("community") or "",
                         kind=r.get("kind") or "comment", thread=r.get("thread") or "",
                         thread_title=scrub(r.get("thread_title") or ""), author=pid,
                         created_utc=ts,
                         date=dt.datetime.fromtimestamp(ts, dt.timezone.utc).strftime("%Y-%m-%d") if ts else "",
                         text=clean, likes=r.get("likes"), replies=r.get("replies")))
    if not kept:
        raise SystemExit("Nothing to clean yet. Collect some data first (Phase 2, step C).")
    df = pd.DataFrame(kept)
    for col in ("likes", "replies", "created_utc"):
        df[col] = pd.to_numeric(df[col], errors="coerce").astype("Int64")
    root = pathlib.Path("data/corpus")
    root.mkdir(parents=True, exist_ok=True)
    versions = [int(p.name[1:]) for p in root.glob("v*") if p.name[1:].isdigit()]
    v = max(versions, default=0) + 1
    out = root / f"v{v}"
    out.mkdir()
    df.to_parquet(out / "rows.parquet", index=False)
    by_source = (df.groupby(["source", "community"])
                 .agg(rows=("id", "size"), people=("author", "nunique"),
                      posts=("kind", lambda k: int((k == "post").sum())))
                 .reset_index().sort_values("rows", ascending=False))
    manifest = dict(
        version=v, pilot=a.pilot, made=dt.datetime.now(dt.timezone.utc).strftime("%d %B %Y %H:%M UTC"), note=a.note,
        rows_in=raw, rows_kept=len(df), dropped_share=round(1 - len(df) / raw, 3) if raw else 0,
        people=int(df["author"].nunique()),
        dropped=dict(sorted(dropped.items(), key=lambda x: -x[1])),
        dates={"first": df["date"][df["date"] != ""].min(), "last": df["date"].max()},
        by_community=by_source.to_dict(orient="records"))
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2, default=str))
    print(f"Corpus v{v}: {len(df):,} rows from {manifest['people']:,} people, "
          f"{manifest['dates']['first']} to {manifest['dates']['last']}.")
    print(f"Started with {raw:,} rows and dropped {raw - len(df):,} ({manifest['dropped_share']:.0%}):")
    for k, n in manifest["dropped"].items():
        print(f"  {n:>8,}  {k}")
    print("Rows and people per community:")
    for r in by_source.head(30).itertuples():
        print(f"  {r.rows:>9,} rows {r.people:>8,} people  {r.source}/{r.community}")
    print(f"Saved {out}/rows.parquet and {out}/manifest.json")


if __name__ == "__main__":
    main()

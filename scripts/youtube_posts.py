# /// script
# requires-python = ">=3.10"
# dependencies = ["yt-dlp>=2025.1.1"]
# ///
"""List a YouTube channel's recent Shorts or videos with their view counts, for free.

Usage:
  uv run scripts/youtube_posts.py --label rivals --channels @channel1 @channel2 --tab shorts --max 60

Writes hooks/posts_<label>.csv with url, account, order, format, views and title, ready for
score_posts.py. YouTube lists newest first, so "order" stands in for the date: 1 is the newest.
Free, no key needed. One channel at a time, with a pause between them.
"""
import argparse
import csv
import pathlib
import time

import yt_dlp


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--label", required=True)
    ap.add_argument("--channels", nargs="+", required=True, help="channel handles, such as @name")
    ap.add_argument("--tab", choices=["shorts", "videos"], default="shorts")
    ap.add_argument("--max", type=int, default=60)
    a = ap.parse_args()
    rows = []
    for ch in a.channels:
        handle = ch if ch.startswith("@") else "@" + ch
        url = f"https://www.youtube.com/{handle}/{a.tab}"
        opts = {"extract_flat": True, "playlistend": a.max, "quiet": True, "no_warnings": True}
        try:
            with yt_dlp.YoutubeDL(opts) as y:
                info = y.extract_info(url, download=False)
        except Exception as e:
            print(f"  {handle}: couldn't read the channel ({str(e)[:100]})")
            continue
        entries = [e for e in info.get("entries") or [] if e]
        for i, e in enumerate(entries, 1):
            rows.append(dict(url=e.get("url"), account=handle, date="", order=i,
                             format="short" if a.tab == "shorts" else "video", views=e.get("view_count"),
                             likes="", comments="", duration=e.get("duration") or "",
                             caption=" ".join((e.get("title") or "").split()), media_url=""))
        print(f"  {handle}: {len(entries)} {a.tab}")
        time.sleep(3)
    out = pathlib.Path("hooks"); out.mkdir(exist_ok=True)
    path = out / f"posts_{a.label}.csv"
    with path.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()) if rows else ["url"])
        w.writeheader(); w.writerows(rows)
    print(f"Saved {len(rows)} posts to {path}. Run scripts/score_posts.py --file {path} next.")


if __name__ == "__main__":
    main()

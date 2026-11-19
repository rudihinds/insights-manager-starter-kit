# /// script
# requires-python = ">=3.10"
# dependencies = ["pandas>=2.2"]
# ///
"""Score each post against the posts around it, so you can tell a real outlier from a big account.

Usage:
  uv run scripts/score_posts.py --file hooks/posts.csv
  uv run scripts/score_posts.py --file hooks/posts_rivals.csv hooks/posts_creators.csv

posts.csv needs at least these columns: url, account, format, views, and either date
(YYYY-MM-DD) or order (1 = newest, as youtube_posts.py writes). If a format has no views
(carousels, text posts), put likes in the views column for it.

For each post: score = its views divided by the median views of the 30 posts nearest to it
in time, from the same account and the same format. 1.0 is normal for that account.
2.0 or more is an outlier, and 0.5 or less is a flop. Raw view counts mislead, because a
big account's flop can still out-view a small account's best post.

Writes hooks/posts_scored.csv, sorted best first.
"""
import argparse
import pathlib

import pandas as pd


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--file", nargs="+", required=True, help="one or more posts CSV files")
    ap.add_argument("--window", type=int, default=30)
    a = ap.parse_args()
    df = pd.concat([pd.read_csv(f) for f in a.file], ignore_index=True)
    need = {"url", "account", "format", "views"}
    if not need <= set(df.columns) or not ({"date", "order"} & set(df.columns)):
        raise SystemExit("posts.csv needs columns url, account, format, views, and date or order.")
    when = pd.to_datetime(df["date"], errors="coerce") if "date" in df else pd.Series(pd.NaT, index=df.index)
    if "order" in df:
        fallback = pd.Timestamp("2000-01-01") - pd.to_timedelta(pd.to_numeric(df["order"], errors="coerce"), unit="D")
        when = when.fillna(fallback)
    df["t"] = when
    df["views"] = pd.to_numeric(df["views"], errors="coerce")
    df = df.dropna(subset=["t", "views"]).reset_index(drop=True)
    scores = []
    for i, r in df.iterrows():
        peers = df[(df.account == r.account) & (df.format == r.format) & (df.index != i)].copy()
        if len(peers) < 5:
            scores.append(None); continue
        peers["gap"] = (peers.t - r.t).abs()
        med = peers.nsmallest(a.window, "gap")["views"].median()
        scores.append(round(r.views / med, 2) if med else None)
    df["score"] = scores
    df["class"] = df["score"].map(lambda s: "" if pd.isna(s) else "outlier" if s >= 2 else "flop" if s <= 0.5 else "normal")
    df = df.drop(columns=["t"]).sort_values("score", ascending=False)
    out = pathlib.Path(a.file[0]).with_name("posts_scored.csv")
    df.to_csv(out, index=False)
    print(df["class"].value_counts().to_string())
    print(f"\nTop 10 by score:")
    for r in df.head(10).itertuples():
        print(f"  {r.score:>5}  {r.account:<20} {r.format:<10} {int(r.views):>10,}  {r.url}")
    print(f"\nSaved {out}. Posts with fewer than 5 same-format peers get no score.")


if __name__ == "__main__":
    main()

# /// script
# requires-python = ">=3.10"
# dependencies = ["pandas>=2.2", "pyarrow>=16"]
# ///
"""Draw people (or top posts) from the corpus for reading and coding.

Usage:
  uv run scripts/sample.py --name discovery --people 200 --seed 1
  uv run scripts/sample.py --name code-1 --people 300 --seed 2 --exclude discovery
  uv run scripts/sample.py --name all --people 0                    (everyone)
  uv run scripts/sample.py --name top-replies --top-posts 150 --seed 3

People, not posts, are the unit: a person who posts 500 times counts once, so heavy posters
can't drown everyone else. People are drawn at random in three posting bands (1 row, 2 to 10,
11 or more) in proportion to their size, so the sample has the same mix as the corpus.
For each person it keeps their 50 newest rows, each cut to 600 characters.

--top-posts N picks the N posts with the most replies (spread across communities) whose
authors aren't already in your samples. Use it to look for anything your sample missed.

Writes samples/<name>.jsonl, one person per line, and records the seed in samples/log.csv.
Uses the newest corpus version unless you pass --corpus data/corpus/v1/rows.parquet.
"""
import argparse
import datetime as dt
import glob
import json
import pathlib
import random

import pandas as pd


def newest_corpus():
    versions = sorted(glob.glob("data/corpus/v*/rows.parquet"), key=lambda p: int(pathlib.Path(p).parent.name[1:]))
    if not versions:
        raise SystemExit("No corpus yet. Run: uv run scripts/clean.py")
    return versions[-1]


def used_authors(names):
    out = set()
    for n in names:
        p = pathlib.Path("samples") / f"{n}.jsonl"
        if not p.exists():
            raise SystemExit(f"There's no samples/{n}.jsonl to exclude.")
        for line in p.read_text().splitlines():
            out.add(json.loads(line)["author"])
    return out


def person_record(author, rows, total):
    rows = rows.sort_values("created_utc", ascending=False).head(50)
    return {"author": author, "total_rows": int(total),
            "rows": [{"id": r.id, "date": r.date, "where": f"{r.source}/{r.community}", "kind": r.kind,
                      "thread_title": (r.thread_title or "")[:150] if r.kind == "comment" else "",
                      "text": r.text[:600], "likes": None if pd.isna(r.likes) else int(r.likes)}
                     for r in rows.itertuples()]}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--name", required=True)
    ap.add_argument("--people", type=int, default=0, help="how many people; 0 means everyone")
    ap.add_argument("--top-posts", type=int, default=0)
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--exclude", nargs="*", default=[], help="sample names whose people to leave out")
    ap.add_argument("--corpus", default=None)
    a = ap.parse_args()
    path = a.corpus or newest_corpus()
    df = pd.read_parquet(path)
    skip = used_authors(a.exclude)
    out_dir = pathlib.Path("samples"); out_dir.mkdir(exist_ok=True)
    out = out_dir / f"{a.name}.jsonl"
    if out.exists():
        raise SystemExit(f"samples/{a.name}.jsonl already exists. Pick another --name.")
    rng = random.Random(a.seed)
    records = []
    if a.top_posts:
        posts = df[(df.kind == "post") & (~df.author.isin(skip))].copy()
        posts["replies"] = posts["replies"].fillna(0)
        posts = posts.sort_values("replies", ascending=False)
        per = max(1, a.top_posts // max(1, posts.community.nunique()))
        picked = posts.groupby("community").head(per).sort_values("replies", ascending=False).head(a.top_posts)
        for r in picked.itertuples():
            records.append({"author": r.author, "total_rows": 1, "rows": [
                {"id": r.id, "date": r.date, "where": f"{r.source}/{r.community}", "kind": r.kind,
                 "thread_title": "", "text": r.text[:600], "likes": None if pd.isna(r.likes) else int(r.likes),
                 "replies": int(r.replies)}]})
    else:
        counts = df.groupby("author").size()
        counts = counts[~counts.index.isin(skip)]
        bands = {"1 row": counts[counts == 1].index.tolist(),
                 "2 to 10 rows": counts[(counts >= 2) & (counts <= 10)].index.tolist(),
                 "11 or more rows": counts[counts >= 11].index.tolist()}
        total = sum(len(v) for v in bands.values())
        if total == 0:
            raise SystemExit("No people left to draw. Check --exclude.")
        want = total if a.people in (0, None) or a.people >= total else a.people
        exact = {k: want * len(v) / total for k, v in bands.items()}
        take = {k: int(x) for k, x in exact.items()}
        for k in sorted(exact, key=lambda k: -(exact[k] - take[k]))[: want - sum(take.values())]:
            take[k] += 1
        chosen = []
        for name, people in bands.items():
            people.sort()
            chosen += rng.sample(people, min(take[name], len(people)))
        grouped = df[df.author.isin(set(chosen))].groupby("author")
        for author, rows in grouped:
            records.append(person_record(author, rows, counts.get(author, len(rows))))
        rng.shuffle(records)
        print("Posting bands in the corpus: " + ", ".join(f"{k} {len(v):,}" for k, v in bands.items()))
    with out.open("w") as f:
        for r in records:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    log = out_dir / "log.csv"
    new = not log.exists()
    with log.open("a") as f:
        if new:
            f.write("name,people,seed,exclude,corpus,made\n")
        f.write(f"{a.name},{len(records)},{a.seed},{' '.join(a.exclude)},{path},"
                f"{dt.datetime.now().strftime('%Y-%m-%d %H:%M')}\n")
    rows = sum(len(r["rows"]) for r in records)
    print(f"Saved {out}: {len(records):,} people, {rows:,} rows. Seed {a.seed}.")


if __name__ == "__main__":
    main()

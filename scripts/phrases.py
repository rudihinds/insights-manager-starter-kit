# /// script
# requires-python = ">=3.10"
# dependencies = ["pandas>=2.2", "pyarrow>=16"]
# ///
"""Count how many different people use each phrase, across the whole corpus.

Usage:
  uv run scripts/phrases.py --file phrases.txt
  uv run scripts/phrases.py --file phrases.txt --by-community
  uv run scripts/phrases.py --file price.txt --examples 5 --out price.csv

phrases.txt has one phrase per line. A line can hold variants split by " | ", which are
counted together, for example:  first client | first paying client | landing a client
Matching ignores case and punctuation and needs whole words.

Prints, for each line, the number of distinct people and rows that use it, and the first
date it appears. Writes phrases.csv. Use it two ways:
  - Phase 4: check that a top-ranked need shows up across the full corpus, not just your sample.
  - Phase 5: keep only "their words" that 5 or more different people use, so no line in your
    message bank traces back to one person.
"""
import argparse
import csv
import glob
import pathlib
import re

import pandas as pd


def norm(s):
    return " " + re.sub(r"[^\w']+", " ", s.lower()).strip() + " "


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--file", required=True)
    ap.add_argument("--corpus", default=None)
    ap.add_argument("--by-community", action="store_true")
    ap.add_argument("--examples", type=int, default=0, help="also print this many random matching rows per line")
    ap.add_argument("--out", default="phrases.csv", help="where to save the counts (default phrases.csv)")
    a = ap.parse_args()
    path = a.corpus or sorted(glob.glob("data/corpus/v*/rows.parquet"), key=lambda p: int(pathlib.Path(p).parent.name[1:]))[-1]
    df = pd.read_parquet(path, columns=["author", "community", "date", "text"])
    df["t"] = df["text"].map(norm)
    lines = [l.strip() for l in pathlib.Path(a.file).read_text().splitlines() if l.strip() and not l.startswith("#")]
    out = []
    total_people = df["author"].nunique()
    for line in lines:
        variants = [norm(v) for v in line.split("|") if v.strip()]
        mask = pd.Series(False, index=df.index)
        for v in variants:
            mask |= df["t"].str.contains(re.escape(v), regex=True)
        hit = df[mask]
        row = {"phrase": line, "people": int(hit["author"].nunique()), "rows": int(len(hit)),
               "share_of_people": round(hit["author"].nunique() / total_people, 4),
               "first_seen": hit["date"].min() if len(hit) else ""}
        if a.by_community and len(hit):
            top = hit.groupby("community")["author"].nunique().sort_values(ascending=False).head(3)
            row["top_communities"] = "; ".join(f"{k} {v}" for k, v in top.items())
        out.append(row)
        if a.examples and len(hit):
            row["_examples"] = hit.sample(min(a.examples, len(hit)), random_state=1)["text"].str[:240].tolist()
    out.sort(key=lambda r: -r["people"])
    examples = {r["phrase"]: r.pop("_examples", []) for r in out}
    with open(a.out, "w", newline="") as f:
        keys = sorted({k for r in out for k in r}, key=lambda k: list(out[0].keys()).index(k) if k in out[0] else 99) if out else ["phrase"]
        w = csv.DictWriter(f, fieldnames=keys)
        w.writeheader(); w.writerows(out)
    print(f"{total_people:,} people in {path}\n")
    print(f"{'people':>7} {'rows':>7}  phrase")
    for r in out:
        flag = "" if r["people"] >= 5 else "   (fewer than 5 people: don't use as 'their words')"
        print(f"{r['people']:>7} {r['rows']:>7}  {r['phrase'][:70]}{flag}")
        for e in examples.get(r["phrase"], []):
            print(f"                   - {e}")
    print(f"\nSaved {a.out}")


if __name__ == "__main__":
    main()

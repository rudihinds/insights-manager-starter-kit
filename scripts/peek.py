# /// script
# requires-python = ">=3.10"
# dependencies = ["pandas>=2.2", "pyarrow>=16"]
# ///
"""Show a few random rows from the newest corpus, so you can see what's in it.

Usage:
  uv run scripts/peek.py --rows 10
  uv run scripts/peek.py --rows 10 --community energydrinks --seed 4

Prints each row's community, date, kind and the first 300 characters of its text.
Writes nothing.
"""
import argparse
import glob
import pathlib

import pandas as pd


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--rows", type=int, default=10)
    ap.add_argument("--community", default=None)
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--corpus", default=None)
    a = ap.parse_args()
    versions = sorted(glob.glob("data/corpus/v*/rows.parquet"), key=lambda p: int(pathlib.Path(p).parent.name[1:]))
    if not versions and not a.corpus:
        raise SystemExit("No corpus yet. Run: uv run scripts/clean.py")
    path = a.corpus or versions[-1]
    df = pd.read_parquet(path, columns=["source", "community", "date", "kind", "text"])
    if a.community:
        df = df[df.community.str.lower() == a.community.lower()]
    print(f"{len(df):,} rows in {path}. {min(a.rows, len(df))} at random:\n")
    for r in df.sample(min(a.rows, len(df)), random_state=a.seed).itertuples():
        print(f"[{r.source}/{r.community} · {r.date} · {r.kind}]\n  {r.text[:300]}\n")


if __name__ == "__main__":
    main()

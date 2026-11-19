# /// script
# requires-python = ">=3.10"
# dependencies = ["pandas>=2.2", "pyarrow>=16"]
# ///
"""Where does each group spend time? Counts a group's people by community.

Usage:
  uv run scripts/channels.py --within N04 N07 --name first-clients

Takes the in-scope people who hold any of the listed codes (the same group as
rank.py --within), finds every row they posted anywhere in the corpus, and counts
people per source and community. Writes channels_<name>.csv and prints the top 15.

"Share of group" is the share of the group's people seen in that community, so it shows
where they gather, not just where the corpus is biggest. "Lift" compares that share with
the share of all in-scope people seen there: above 1.0 means this group over-indexes there.
"""
import argparse
import glob
import json
import pathlib

import pandas as pd


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--within", nargs="+", required=True)
    ap.add_argument("--name", required=True)
    a = ap.parse_args()
    people = {}
    for f in sorted(glob.glob("coded/*.jsonl")):
        if f.endswith("-check.jsonl"):
            continue
        for line in pathlib.Path(f).read_text().splitlines():
            if line.strip():
                r = json.loads(line)
                people[r["author"]] = r
    inn = {p for p, r in people.items() if r["in_scope"] == "yes"}
    want = set(a.within)
    group = {p for p in inn if want & {c["code"] for c in people[p].get("codes") or []}}
    if not group:
        raise SystemExit("Nobody in scope holds those codes.")
    path = sorted(glob.glob("data/corpus/v*/rows.parquet"), key=lambda p: int(pathlib.Path(p).parent.name[1:]))[-1]
    df = pd.read_parquet(path, columns=["author", "source", "community"])
    df = df[df.author.isin(inn)].drop_duplicates()
    g = df[df.author.isin(group)].groupby(["source", "community"])["author"].nunique().rename("group_people")
    allp = df.groupby(["source", "community"])["author"].nunique().rename("in_scope_people")
    t = pd.concat([g, allp], axis=1).fillna(0).astype(int).reset_index()
    t = t[t.group_people > 0]
    t["share_of_group"] = (t.group_people / len(group)).round(3)
    t["lift"] = (t.share_of_group / (t.in_scope_people / len(inn))).round(2)
    t = t.sort_values(["group_people", "lift"], ascending=False)
    out = f"channels_{a.name}.csv"
    t.to_csv(out, index=False)
    print(f"Group {a.name}: {len(group)} people. Where they post:\n")
    print(f"{'people':>6} {'share':>6} {'lift':>5}  source/community")
    for r in t.head(15).itertuples():
        print(f"{r.group_people:>6} {r.share_of_group:>6.0%} {r.lift:>5}  {r.source}/{r.community}")
    print(f"\nSaved {out}. Only the communities you collected can show up here.")


if __name__ == "__main__":
    main()

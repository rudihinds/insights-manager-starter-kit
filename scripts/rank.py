# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""Rank every code by your mode's formula, from the coded files only.

Usage:
  uv run scripts/rank.py --mode problem
  uv run scripts/rank.py --mode moment --coded coded/code-1.jsonl coded/code-2.jsonl
  uv run scripts/rank.py --mode problem --within N04 N07 --name first-clients

--within ranks only the in-scope people who hold any of the listed codes: one persona group.
It writes ranking_<name>.csv instead of ranking.csv.

Reads coded/*.jsonl (not the -check files) and codebook.json for labels.
Counts only people coded in scope. Writes ranking.csv and prints the top 20.

Problem mode:  score = reach x intensity x (0.5 + 0.5 x acted) x (0.5 + 0.5 x unsolved)
Moment mode:   score = reach x charge x (0.5 + 0.5 x behaviour) x (0.5 + 0.5 x unowned)

  reach      share of in-scope people who hold the code
  intensity  average strength (1 passing, 2 real concern, 3 painful), divided by 3
  charge     the same 1 to 3 scale, read as emotional charge in moment mode
  acted      share of holders who did something about it (spent time or money, tried a tool)
  behaviour  share of holders who bought, tried, stocked up, collected or switched
  unsolved   share of holders who say what they tried didn't work
  unowned    share of holders who tie the moment to no brand at all

Codes held by fewer than 3 people are listed last and marked "(few)", because one person
can't make a pattern. The problem formula is the one from our real run. The moment formula
is the same shape with moment-mode inputs; we haven't run it on a full study yet.
"""
import argparse
import csv
import glob
import json
import pathlib


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--mode", choices=["problem", "moment"], required=True)
    ap.add_argument("--coded", nargs="*", default=None)
    ap.add_argument("--within", nargs="*", default=None, help="only people holding any of these codes")
    ap.add_argument("--name", default=None, help="name for this group's ranking file")
    ap.add_argument("--out", default=None, help="file to save to, instead of ranking.csv")
    a = ap.parse_args()
    files = a.coded or [f for f in sorted(glob.glob("coded/*.jsonl")) if not f.endswith("-check.jsonl")]
    if not files:
        raise SystemExit("No coded files yet. Code a sample and run merge.py first.")
    people = {}
    for f in files:
        for line in pathlib.Path(f).read_text().splitlines():
            if line.strip():
                r = json.loads(line)
                people[r["author"]] = r
    inn = [r for r in people.values() if r["in_scope"] == "yes"]
    if not inn:
        raise SystemExit("Nobody is coded in scope yet.")
    everyone = len(inn)
    if a.within:
        want = set(a.within)
        inn = [r for r in inn if want & {c["code"] for c in r.get("codes") or []}]
        if not inn:
            raise SystemExit("Nobody in scope holds those codes.")
    labels, kinds = {}, {}
    cb = pathlib.Path("codebook.json")
    if cb.exists():
        for c in json.loads(cb.read_text())["codes"]:
            labels[c["code"]] = c.get("label", "")
            kinds[c["code"]] = c.get("kind", "")
    stats = {}
    for r in inn:
        best = {}
        for c in r.get("codes") or []:
            k = c["code"]
            if k not in best or int(c.get("strength", 1)) > int(best[k].get("strength", 1)):
                best[k] = {**c, "acted": best.get(k, {}).get("acted") or c.get("acted"),
                           "unsolved": best.get(k, {}).get("unsolved") or c.get("unsolved")}
        for k, c in best.items():
            s = stats.setdefault(k, {"people": 0, "strength": 0, "painful": 0, "acted": 0, "unsolved": 0, "unowned": 0})
            s["people"] += 1
            s["strength"] += int(c.get("strength", 1))
            s["painful"] += int(c.get("strength", 1)) == 3
            s["acted"] += bool(c.get("acted"))
            s["unsolved"] += c.get("unsolved") is True
            s["unowned"] += not c.get("brand")
    rows = []
    n = len(inn)
    for k, s in stats.items():
        reach = s["people"] / n
        intensity = s["strength"] / s["people"] / 3
        acted = s["acted"] / s["people"]
        last = (s["unsolved"] if a.mode == "problem" else s["unowned"]) / s["people"]
        score = reach * intensity * (0.5 + 0.5 * acted) * (0.5 + 0.5 * last)
        rows.append({"code": k, "label": labels.get(k, ""), "kind": kinds.get(k, ""), "people": s["people"],
                     "reach": round(reach, 3), "intensity": round(intensity, 2), "painful": s["painful"],
                     ("acted" if a.mode == "problem" else "behaviour"): round(acted, 2),
                     ("unsolved" if a.mode == "problem" else "unowned"): round(last, 2),
                     "score": round(score, 4), "few": s["people"] < 3})
    rows.sort(key=lambda r: (r["few"], -r["score"]))
    for i, r in enumerate(rows, 1):
        r["rank"] = i
    out_name = a.out or (f"ranking_{a.name}.csv" if a.name else ("ranking_group.csv" if a.within else "ranking.csv"))
    with open(out_name, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["rank", *[k for k in rows[0] if k != "rank"]])
        w.writeheader(); w.writerows(rows)
    last_name = "unsolved" if a.mode == "problem" else "unowned"
    first_name = "acted" if a.mode == "problem" else "behaviour"
    print(f"{n:,} in-scope people from {len(files)} coded file(s). Mode: {a.mode}.")
    if a.within:
        print(f"Group: people holding {' or '.join(a.within)}. That's {n:,} of {everyone:,} in-scope people ({n / everyone:.0%}).")
        if n < 30:
            print("Fewer than 30 people: report this group as too thin to rank.")
    print()
    print(f"{'rank':>4}  {'code':<8} {'people':>6} {'reach':>6} {first_name:>9} {last_name:>8} {'score':>7}  label")
    for r in rows[:20]:
        print(f"{r['rank']:>4}  {r['code']:<8} {r['people']:>6} {r['reach']:>6.0%} {r[first_name]:>9.0%} "
              f"{r[last_name]:>8.0%} {r['score']:>7.3f}  {r['label'][:45]}{' (few)' if r['few'] else ''}")
    print(f"\nSaved {out_name}")


if __name__ == "__main__":
    main()

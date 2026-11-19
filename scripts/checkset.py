# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""Pick a random set of already-coded people for a second, independent coder.

Usage:
  uv run scripts/checkset.py --sample code-1 --people 60 --seed 7

Writes batches/<sample>-check/batch_001.jsonl ... (20 people each) with the same input
the first coder saw, and no labels, so the checker can't see the first coder's answers.
The checker writes its labels to labels/<sample>-check/. Then run:
  uv run scripts/merge.py --sample <sample>-check
  uv run scripts/agreement.py --sample <sample>
"""
import argparse
import json
import pathlib
import random


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--sample", required=True)
    ap.add_argument("--people", type=int, default=60)
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--size", type=int, default=20)
    ap.add_argument("--enrich", default=None,
                    help="a code, or 'in_scope', to over-sample: half the set is people the first coder gave it")
    a = ap.parse_args()
    people = {json.loads(l)["author"]: json.loads(l)
              for l in (pathlib.Path("samples") / f"{a.sample}.jsonl").read_text().splitlines() if l.strip()}
    coded = [json.loads(l) for l in (pathlib.Path("coded") / f"{a.sample}.jsonl").read_text().splitlines() if l.strip()]
    rng = random.Random(a.seed)
    ids = sorted(r["author"] for r in coded if r["author"] in people)
    if a.enrich:
        def has(r):
            return r["in_scope"] == "yes" if a.enrich == "in_scope" else any(c["code"] == a.enrich for c in r.get("codes") or [])
        hit = sorted(r["author"] for r in coded if has(r) and r["author"] in people)
        rest = sorted(set(ids) - set(hit))
        k = min(len(hit), a.people // 2)
        pick = rng.sample(hit, k) + rng.sample(rest, min(len(rest), a.people - k))
    else:
        pick = rng.sample(ids, min(a.people, len(ids)))
    rng.shuffle(pick)
    out = pathlib.Path("batches") / f"{a.sample}-check"
    if out.exists():
        raise SystemExit(f"{out} already exists. Delete it to draw a new check set.")
    out.mkdir(parents=True)
    names = []
    for i in range(0, len(pick), a.size):
        name = f"batch_{i // a.size + 1:03d}.jsonl"
        with (out / name).open("w") as f:
            for pid in pick[i:i + a.size]:
                f.write(json.dumps(people[pid], ensure_ascii=False) + "\n")
        names.append(str(out / name))
    (out / "todo.txt").write_text("\n".join(names) + "\n")
    print(f"Check set: {len(pick)} people in {len(names)} batches, in {out}. Seed {a.seed}.")


if __name__ == "__main__":
    main()

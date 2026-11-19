# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""Split a sample into batch files, one per coding agent.

Usage:
  uv run scripts/batches.py --sample code-1 --size 25

Writes batches/<sample>/batch_001.jsonl, batch_002.jsonl, ... (25 people each by default)
and batches/<sample>/todo.txt, the list of batch files still to code.
A batch of about 25 people keeps each coding agent well inside its context window.
"""
import argparse
import json
import pathlib


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--sample", required=True)
    ap.add_argument("--size", type=int, default=25)
    a = ap.parse_args()
    src = pathlib.Path("samples") / f"{a.sample}.jsonl"
    if not src.exists():
        raise SystemExit(f"No samples/{a.sample}.jsonl. Draw it first with scripts/sample.py.")
    people = [json.loads(l) for l in src.read_text().splitlines() if l.strip()]
    out = pathlib.Path("batches") / a.sample
    if out.exists() and any(out.glob("batch_*.jsonl")):
        raise SystemExit(f"{out} already has batches. Delete that folder to split again.")
    out.mkdir(parents=True, exist_ok=True)
    names = []
    for i in range(0, len(people), a.size):
        name = f"batch_{i // a.size + 1:03d}.jsonl"
        with (out / name).open("w") as f:
            for p in people[i:i + a.size]:
                f.write(json.dumps(p, ensure_ascii=False) + "\n")
        names.append(str(out / name))
    (out / "todo.txt").write_text("\n".join(names) + "\n")
    print(f"{len(people):,} people in {len(names)} batches of up to {a.size}, in {out}")


if __name__ == "__main__":
    main()

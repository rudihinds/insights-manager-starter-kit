# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""Check every coded batch against its input, then merge them into one file.

Usage:
  uv run scripts/merge.py --sample code-1
  uv run scripts/merge.py --sample code-1-check   (the checker's labels)

Reads batches/<sample>/batch_*.jsonl (who should be there) and
      labels/<sample>/batch_*.jsonl  (what the coding agents wrote, one person per line).
Writes coded/<sample>.jsonl and prints:
  - batches with people missing, duplicated or unexpected (re-run those batches);
  - lines that aren't valid JSON or lack required fields;
  - codes that aren't in codebook.json;
  - the share of people coded in scope (your audience filter).
Nothing here is done by a model, so every count is exact.
"""
import argparse
import json
import pathlib

STRENGTHS = {1, 2, 3}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--sample", required=True)
    ap.add_argument("--labels", default=None, help="folder of label files (default labels/<sample>)")
    ap.add_argument("--out", default=None)
    a = ap.parse_args()
    bdir = pathlib.Path("batches") / a.sample
    ldir = pathlib.Path(a.labels or f"labels/{a.sample}")
    out = pathlib.Path(a.out or (f"coded/{a.sample}.jsonl" if not a.labels else f"coded/{ldir.name}-{ldir.parent.name}.jsonl"))
    known = None
    cb = pathlib.Path("codebook.json")
    if cb.exists():
        known = {c["code"] for c in json.loads(cb.read_text())["codes"]}
    merged, problems, unknown_codes = [], [], {}
    batches = sorted(bdir.glob("batch_*.jsonl"))
    if not batches:
        raise SystemExit(f"No batches in {bdir}.")
    redo = []
    for b in batches:
        want = [json.loads(l)["author"] for l in b.read_text().splitlines() if l.strip()]
        lf = ldir / b.name
        if not lf.exists():
            redo.append(b.name); problems.append(f"{b.name}: not coded yet"); continue
        got, bad = [], 0
        for n, line in enumerate(lf.read_text().splitlines(), 1):
            if not line.strip():
                continue
            try:
                r = json.loads(line)
                assert isinstance(r.get("author"), str)
                assert r.get("in_scope") in ("yes", "no", "unclear")
                for c in r.get("codes") or []:
                    assert isinstance(c.get("code"), str)
                    c["strength"] = int(c.get("strength", 1))
                    assert c["strength"] in STRENGTHS
                    if known is not None and c["code"] not in known:
                        unknown_codes[c["code"]] = unknown_codes.get(c["code"], 0) + 1
            except (json.JSONDecodeError, AssertionError, ValueError, TypeError):
                bad += 1; continue
            got.append(r)
        ids = [r["author"] for r in got]
        missing = set(want) - set(ids)
        extra = set(ids) - set(want)
        dupes = len(ids) - len(set(ids))
        if missing or extra or dupes:
            redo.append(b.name)
        if missing or extra or dupes or bad:
            problems.append(f"{b.name}: {len(missing)} missing, {dupes} duplicated, "
                            f"{len(extra)} unexpected, {bad} unreadable lines")
        seen = set()
        for r in got:
            if r["author"] in want and r["author"] not in seen:
                seen.add(r["author"]); merged.append(r)
    out.parent.mkdir(exist_ok=True)
    with out.open("w") as f:
        for r in merged:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    total = sum(1 for b in batches for l in b.read_text().splitlines() if l.strip())
    yes = sum(r["in_scope"] == "yes" for r in merged)
    unclear = sum(r["in_scope"] == "unclear" for r in merged)
    print(f"Merged {len(merged):,} of {total:,} people into {out}.")
    if merged:
        print(f"In scope: {yes:,} ({yes / len(merged):.0%}). Unclear: {unclear:,}. "
              f"Out of scope: {len(merged) - yes - unclear:,}.")
    if unknown_codes:
        print("Codes not in codebook.json. Fix the codebook, or re-run the batches that used them: "
              + ", ".join(f"{k} x{v}" for k, v in sorted(unknown_codes.items())))
    if unknown_codes:
        problems.append("some codes aren't in codebook.json (listed above)")
    if problems:
        print(f"{len(problems)} problems:")
        for p in problems:
            print("  " + p)
        if redo:
            print("Re-run these batches: " + " ".join(redo))
        else:
            print("Everyone is present, so nothing needs re-running. Unreadable lines were skipped.")
    else:
        print("0 problems.")


if __name__ == "__main__":
    main()

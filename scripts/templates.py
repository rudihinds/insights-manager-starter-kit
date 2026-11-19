# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""Count each hook template and its median score, from your scored posts.

Usage:
  uv run scripts/templates.py

Reads hooks/hooks_raw.csv (from transcribe.py) and hooks/template_map.csv, which has
two columns, url and template: one row per post, saying which template its opening follows.
Claude writes template_map.csv from the openings. This script does the counting, so every
number in the hook bank comes from the data.

Writes hooks/templates.csv: template, uses, median score, best score, and the url of the
best-scoring original. Sorted by median score. A template used once has no median worth
trusting, so it's marked (once).
"""
import csv
import pathlib
import statistics


def main():
    raw = pathlib.Path("hooks/hooks_raw.csv")
    mp = pathlib.Path("hooks/template_map.csv")
    if not raw.exists() or not mp.exists():
        raise SystemExit("Needs hooks/hooks_raw.csv (from transcribe.py) and hooks/template_map.csv.")
    posts = {r["url"]: r for r in csv.DictReader(raw.open())}
    groups = {}
    missing = 0
    for r in csv.DictReader(mp.open()):
        p = posts.get((r.get("url") or "").strip())
        if not p or not p.get("score"):
            missing += 1
            continue
        groups.setdefault(r["template"].strip(), []).append(p)
    rows = []
    for t, ps in groups.items():
        scores = [float(p["score"]) for p in ps]
        best = max(ps, key=lambda p: float(p["score"]))
        rows.append({"template": t, "uses": len(ps), "median_score": round(statistics.median(scores), 2),
                     "best_score": round(max(scores), 2), "best_url": best["url"],
                     "best_original": best.get("spoken_hook") or best.get("caption", "")[:200],
                     "once": len(ps) == 1})
    rows.sort(key=lambda r: (r["once"], -r["median_score"]))
    out = pathlib.Path("hooks/templates.csv")
    with out.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()) if rows else ["template"])
        w.writeheader(); w.writerows(rows)
    print(f"{'uses':>4} {'median':>6} {'best':>5}  template")
    for r in rows:
        print(f"{r['uses']:>4} {r['median_score']:>6} {r['best_score']:>5}  {r['template'][:70]}{' (once)' if r['once'] else ''}")
    if missing:
        print(f"\n{missing} rows in template_map.csv had no matching scored post, and were skipped.")
    print(f"\nSaved {out}")


if __name__ == "__main__":
    main()

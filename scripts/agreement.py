# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""Measure how well two independent coders agree, with Cohen's kappa.

Usage:
  uv run scripts/agreement.py --sample code-1

Compares coded/<sample>.jsonl (first coder) with coded/<sample>-check.jsonl (checker)
on the people both coded. Reports:
  1. In scope: raw agreement and kappa.
  2. Each code used by 3 or more people in either set: did both coders give this person
     this code? Raw agreement and kappa, for the codes that matter most.
  3. Whether the ranking holds: the top 5 codes by people for each coder, and the overlap.
  4. Every disagreement on in scope, with both reasons, and for each code the people the
     two coders split on, so you can compare them in coded/<sample>.jsonl and -check.jsonl.
Writes agreement/<sample>.json.

Kappa is agreement after removing the agreement you'd get by luck. 1 is perfect, 0 is no
better than chance. Below 0.60 is too low to trust (McHugh 2012); aim for 0.70 or more.
"""
import argparse
import json
import pathlib
from collections import Counter


def kappa(a, b):
    n = len(a)
    if n == 0:
        return None, None
    po = sum(x == y for x, y in zip(a, b)) / n
    ca, cb = Counter(a), Counter(b)
    pe = sum((ca[k] / n) * (cb[k] / n) for k in set(ca) | set(cb))
    if pe == 1:
        return po, None
    return po, (po - pe) / (1 - pe)


def load(p):
    return {r["author"]: r for r in (json.loads(l) for l in pathlib.Path(p).read_text().splitlines() if l.strip())}


def fmt(po, k):
    return f"{po:.0%} agree, kappa {'n/a' if k is None else f'{k:.2f}'}"


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--sample", required=True)
    a = ap.parse_args()
    A = load(f"coded/{a.sample}.jsonl")
    B = load(f"coded/{a.sample}-check.jsonl")
    both = sorted(set(A) & set(B))
    if not both:
        raise SystemExit("No people in common. Run checkset.py, the checker, then merge.py first.")
    labels = {}
    cb = pathlib.Path("codebook.json")
    if cb.exists():
        labels = {c["code"]: c.get("label", "") for c in json.loads(cb.read_text())["codes"]}
    po, k = kappa([A[p]["in_scope"] for p in both], [B[p]["in_scope"] for p in both])
    report = {"people": len(both), "in_scope": {"agree": po, "kappa": k}, "codes": [], "disagreements": []}
    print(f"{len(both)} people coded by both.\n\nIn scope: {fmt(po, k)}")
    inn = [p for p in both if A[p]["in_scope"] == "yes" and B[p]["in_scope"] == "yes"]
    codes_a = {p: {c["code"] for c in A[p].get("codes") or []} for p in inn}
    codes_b = {p: {c["code"] for c in B[p].get("codes") or []} for p in inn}
    count_a = Counter(c for p in inn for c in codes_a[p])
    count_b = Counter(c for p in inn for c in codes_b[p])
    common = [c for c in set(count_a) | set(count_b) if max(count_a[c], count_b[c]) >= 3]
    common.sort(key=lambda c: -(count_a[c] + count_b[c]))
    if inn:
        print(f"\nCodes, on the {len(inn)} people both coders put in scope (codes held by 3 or more):")
        print(f"  {'code':<8} {'coder 1':>7} {'checker':>7}  agreement")
        ks = []
        for c in common:
            po_c, k_c = kappa([c in codes_a[p] for p in inn], [c in codes_b[p] for p in inn])
            ks.append(k_c)
            split = [{"author": p, "coder1_has_it": c in codes_a[p], "checker_has_it": c in codes_b[p]}
                     for p in inn if (c in codes_a[p]) != (c in codes_b[p])]
            report["codes"].append({"code": c, "label": labels.get(c, ""), "coder1": count_a[c],
                                    "checker": count_b[c], "agree": po_c, "kappa": k_c, "split": split})
            print(f"  {c:<8} {count_a[c]:>7} {count_b[c]:>7}  {fmt(po_c, k_c)}  {labels.get(c, '')[:40]}")
        real = [x for x in ks[:10] if x is not None]
        if real:
            mean = sum(real) / len(real)
            report["mean_kappa_top10"] = mean
            print(f"\nMean kappa over the 10 most-used codes: {mean:.2f}")
        top_a = [c for c, _ in count_a.most_common(5)]
        top_b = [c for c, _ in count_b.most_common(5)]
        overlap = len(set(top_a) & set(top_b))
        report["top5"] = {"coder1": top_a, "checker": top_b, "overlap": overlap}
        print(f"Top 5 codes, coder 1: {', '.join(top_a)}")
        print(f"Top 5 codes, checker: {', '.join(top_b)}")
        print(f"Overlap: {overlap} of 5")
    for p in both:
        if A[p]["in_scope"] != B[p]["in_scope"]:
            report["disagreements"].append({"author": p, "coder1": A[p]["in_scope"], "coder1_reason": A[p].get("reason", ""),
                                            "checker": B[p]["in_scope"], "checker_reason": B[p].get("reason", "")})
    if report["disagreements"]:
        print(f"\n{len(report['disagreements'])} in-scope disagreements are listed in agreement/{a.sample}.json")
    out = pathlib.Path("agreement"); out.mkdir(exist_ok=True)
    (out / f"{a.sample}.json").write_text(json.dumps(report, indent=2))
    print(f"Saved agreement/{a.sample}.json")


if __name__ == "__main__":
    main()

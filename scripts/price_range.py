# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""Work out a price range from Van Westendorp's four price questions.

Usage:
  uv run scripts/price_range.py --file price_answers.csv

price_answers.csv has one row per person and four columns, each a price in your currency:
  too_expensive   so expensive they wouldn't consider it
  too_cheap       so cheap they'd doubt the quality
  expensive       starting to feel expensive, but still worth thinking about
  bargain         a bargain, a great buy for the money

It draws the four curves the method uses and prints where they cross:
  lowest acceptable price    where "too cheap" crosses "not a bargain"
  optimal price              where "too cheap" crosses "too expensive"
  indifference price         where "a bargain" crosses "expensive"
  highest acceptable price   where "too expensive" crosses "not expensive"
The acceptable range runs from the lowest to the highest. It also prints how many answers
it used. Rows with a missing or non-numeric answer are skipped and counted.
Method: Van Westendorp (1976), NSS Price Sensitivity Meter, ESOMAR Congress.
"""
import argparse
import csv


def share_at_or_below(values, p):
    return sum(v <= p for v in values) / len(values)


def share_at_or_above(values, p):
    return sum(v >= p for v in values) / len(values)


def cross(grid, f, g):
    """First price where f and g meet. If they run level for a stretch, take its middle."""
    ds = [f(p) - g(p) for p in grid]
    for i in range(1, len(grid)):
        if ds[i] == 0:
            j = i
            while j + 1 < len(grid) and ds[j + 1] == 0:
                j += 1
            return round((grid[i] + grid[j]) / 2, 2)
        if (ds[i] > 0) != (ds[i - 1] > 0) and ds[i - 1] != 0:
            return round((grid[i - 1] + grid[i]) / 2, 2)
    return None


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--file", required=True)
    a = ap.parse_args()
    cols = ["too_expensive", "too_cheap", "expensive", "bargain"]
    data = {c: [] for c in cols}
    skipped = 0
    for r in csv.DictReader(open(a.file)):
        try:
            vals = {c: float(str(r[c]).replace("$", "").replace("£", "").replace(",", "").strip()) for c in cols}
        except (KeyError, ValueError, TypeError):
            skipped += 1
            continue
        for c in cols:
            data[c].append(vals[c])
    n = len(data["bargain"])
    if n < 2:
        raise SystemExit("Need at least 2 complete answers. Columns: too_expensive, too_cheap, expensive, bargain.")
    lo = min(min(v) for v in data.values())
    hi = max(max(v) for v in data.values())
    grid = [lo + (hi - lo) * i / 1000 for i in range(1001)]
    too_cheap = lambda p: share_at_or_above(data["too_cheap"], p)
    bargain = lambda p: share_at_or_above(data["bargain"], p)
    expensive = lambda p: share_at_or_below(data["expensive"], p)
    too_exp = lambda p: share_at_or_below(data["too_expensive"], p)
    pmc = cross(grid, too_cheap, lambda p: 1 - bargain(p))
    opp = cross(grid, too_cheap, too_exp)
    ipp = cross(grid, bargain, expensive)
    pme = cross(grid, too_exp, lambda p: 1 - expensive(p))
    print(f"Based on {n} complete answers ({skipped} skipped).")
    print(f"  Lowest acceptable price:  {pmc}")
    print(f"  Optimal price:            {opp}")
    print(f"  Indifference price:       {ipp}")
    print(f"  Highest acceptable price: {pme}")
    if pmc and pme:
        print(f"Acceptable range: {pmc} to {pme}")
    if n < 30:
        print("Fewer than 30 answers: treat this as a rough range, not a price.")


if __name__ == "__main__":
    main()

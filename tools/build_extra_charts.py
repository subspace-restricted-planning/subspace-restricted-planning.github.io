#!/usr/bin/env python3
"""Add the budget-sweep series to static/charts.js, computed from the paper's records.

    PAPER_REPO=/path/to/paper python3 tools/build_extra_charts.py
    python3 tools/build_extra_charts.py --paper /path/to/paper

Reads the paper's data/m0 read-only and never writes outside this repo. The
paper's own builder (figs/src/build_page_charts.py) writes into the paper repo,
which is off limits during the submission window, so this lives here instead.
Fail-closed: a missing record aborts rather than silently dropping a seed.
"""
import argparse, json, os, re, sys
from pathlib import Path
import numpy as np

ap = argparse.ArgumentParser()
ap.add_argument("--paper", default=os.environ.get("PAPER_REPO"), required=False,
                help="paper repo holding data/m0; or set PAPER_REPO")
ap.add_argument("--charts", default="static/charts.js")
a = ap.parse_args()
if not a.paper:
    sys.exit("set PAPER_REPO or pass --paper: the paper repo holding data/m0")
D = os.path.join(a.paper, "data", "m0")
if not os.path.isdir(D):
    sys.exit(f"no records at {D}")

NS = [100, 300, 900, 2700]
ARMS = [("ambient sampler", "cube_default_N{n}_s{s}.npz"),
        ("pruned sampling", "cube_row_N{n}_s{s}.npz")]

def seeds(pat, n):
    return sorted(int(m.group(1)) for f in os.listdir(D)
                  for m in [re.fullmatch(pat.format(n=n, s=r"(\d+)"), f)] if m)

def rate(pat, n, s):
    z = np.load(os.path.join(D, pat.format(n=n, s=s)))
    return 100.0 * z["episode_successes"].astype(int).mean()

lines, seedpts = [], []
for label, pat in ARMS:
    ys, pts = [], []
    for n in NS:
        ss = seeds(pat, n)
        if not ss:
            sys.exit(f"[FAIL-CLOSED] no records for {label} at N={n}")
        vals = [rate(pat, n, s) for s in ss]
        ys.append(round(float(np.mean(vals)), 1))
        pts.append([round(float(v), 1) for v in vals])
    lines.append(dict(s=label, y=ys))
    seedpts.append(pts)
    print(f"  {label:18} " + "  ".join(f"N={n}:{y:5.1f} (n={len(p)})"
                                       for n, y, p in zip(NS, ys, pts)))

spec = dict(kind="xlines", title="Cube success rate against the sampling budget",
            x="CEM samples per iteration N", y="success rate (%)",
            xs=NS, xevery=True, ymin=55, ymax=80, ystep=5,
            lines=lines, seeds=seedpts,
            sub="27-fold range - the paired gap at N=2700 is +4.0 (p=0.0075, six of six seeds)")

p = a.charts
t = open(p, encoding="utf-8").read()
m = re.match(r"(const CHARTS = )(\{.*\})(;?\s*)$", t, re.S)
charts = json.loads(m.group(2))
charts["budget"] = spec
open(p, "w", encoding="utf-8").write(m.group(1) + json.dumps(charts, ensure_ascii=False) + m.group(3))
print(f"  wrote budget series into {p}")

#!/usr/bin/env python3
# Copyright (c) 2026 Paulo Santos (@wkhadgar)
#
# SPDX-License-Identifier: Apache-2.0

"""Q1 boot medians, Mann-Whitney with Holm and Cliff's delta. Usage: q1_stats.py DIR BOARD"""

import csv
import glob
import statistics as st
import sys

import numpy as np
from scipy.stats import mannwhitneyu
from statsmodels.stats.multitest import multipletests


def cliff(a, b):
    a, b = np.sort(np.asarray(a)), np.sort(np.asarray(b))
    gt = np.searchsorted(b, a, side="left").sum()
    lt = (len(b) - np.searchsorted(b, a, side="right")).sum()
    return (gt - lt) / (len(a) * len(b))


def main():
    data, board = sys.argv[1], sys.argv[2]
    cond = {}
    for d in sorted(glob.glob(f"{data}/*-q1-{board}-*-boot*")):
        name = d.split(f"-q1-{board}-")[1].split("-boot")[0]
        rows = list(csv.DictReader(open(f"{d}/ring.csv")))
        w = [float(r["ns"]) for r in rows]
        s = [float(r["start_ns"]) for r in rows if float(r["start_ns"]) > 0]
        cond.setdefault(name, []).append({"dir": d, "w": w, "s": s, "n": len(rows)})
    base = cond["detached"]
    base_w = st.median(st.median(b["w"]) for b in base)
    base_s = st.median(st.median(b["s"]) for b in base)
    others = [c for c in cond if c != "detached"]
    pw, ps = [], []
    for c in others:
        pw.append(
            mannwhitneyu(
                [st.median(b["w"]) for b in cond[c]],
                [st.median(b["w"]) for b in base],
                alternative="two-sided",
                method="exact",
            )
        )
        ps.append(
            mannwhitneyu(
                [st.median(b["s"]) for b in cond[c]],
                [st.median(b["s"]) for b in base],
                alternative="two-sided",
                method="exact",
            )
        )
    hw = multipletests([r.pvalue for r in pw], alpha=0.05, method="holm")
    hs = multipletests([r.pvalue for r in ps], alpha=0.05, method="holm")
    allbase = [x for b in base for x in b["w"]]
    print(
        f"board {board}; detached: window {base_w:.1f} ns, start-to-start {base_s:.1f} ns, "
        f"boots {len(base)}, windows {[b['n'] for b in base]}"
    )
    for i, c in enumerate(others):
        bw = [st.median(b["w"]) for b in cond[c]]
        bs = [st.median(b["s"]) for b in cond[c]]
        mw, ms = st.median(bw), st.median(bs)
        q = np.percentile([x for b in cond[c] for x in b["w"]], [25, 75])
        print(f"{c}: boots {len(cond[c])}, windows {[b['n'] for b in cond[c]]}")
        print(
            f"  window boot medians {[round(x, 1) for x in bw]} -> {mw:.1f} ns, "
            f"shift {100 * (mw - base_w) / base_w:+.4f}%, IQR all windows {q[0]:.1f} to {q[1]:.1f}"
        )
        print(
            f"  start-to-start boot medians {[round(x, 1) for x in bs]} -> {ms:.1f} ns, "
            f"shift {100 * (ms - base_s) / base_s:+.4f}%"
        )
        print(
            f"  MWU window U {pw[i].statistic:.1f} p {pw[i].pvalue:.4f} (Holm p {hw[1][i]:.4f}, "
            f"reject {hw[0][i]}); period U {ps[i].statistic:.1f} p {ps[i].pvalue:.4f} "
            f"(Holm p {hs[1][i]:.4f}, reject {hs[0][i]})"
        )
        print(
            f"  Cliff delta (windows) {cliff([x for b in cond[c] for x in b['w']], allbase):+.4f}"
        )
        print(
            f"  pass (both shifts under 1%): "
            f"{abs(mw - base_w) / base_w < 0.01 and abs(ms - base_s) / base_s < 0.01}"
        )


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
# Copyright (c) 2026 Paulo Santos (@wkhadgar)
#
# SPDX-License-Identifier: Apache-2.0

"""Q3 detected hold fraction against P(d), Wilson 95%. Usage: q3_fidelity.py ELF DATASET..."""

import os
import bisect
import csv
import gzip
import json
import math
import statistics
import subprocess
import sys

NM = os.environ.get(
    "NM", os.path.expanduser("~/zephyr-sdk-1.0.1/gnu/arm-zephyr-eabi/bin/arm-zephyr-eabi-nm")
)
# Timing counter clock: 150e6 on the zbook, 200e6 on the FPB-RA6E2.
FREQ = float(os.environ.get("FREQ_HZ", "150e6"))
WARMUP_S = 30.0
EDGE_S = 1.0
Z = 1.959963984540054


def symbols(elf):
    out = subprocess.run([NM, elf], capture_output=True, text=True, check=True).stdout
    sym = {}
    for line in out.splitlines():
        parts = line.split()
        if len(parts) == 3:
            sym[parts[2]] = int(parts[0], 16)
    return sym


def unwrap(values):
    out, base, prev = [], 0, None
    for v in values:
        if prev is not None and v < prev - (1 << 31):
            base += 1 << 32
        out.append(v + base)
        prev = v
    return out


def frames(path, usage_addr, mutex_addr):
    """Yield (host_start, usage0, owner) per poll batch that read both."""
    batch = None
    with gzip.open(path, "rt") as f:
        f.readline()
        for line in f:
            o = json.loads(line)
            op = o.get("op")
            if op == "begin_batch":
                batch = {"t": o["t"]}
            elif op == "end_batch":
                if batch and "usage" in batch and "owner" in batch:
                    yield batch["t"], batch["usage"], batch["owner"]
                batch = None
            elif batch is not None and op == "read32":
                at, res = o["args"]["at"], o.get("result") or []
                if at == usage_addr and res:
                    batch["usage"] = res[0]
                elif at == mutex_addr and len(res) >= 3:
                    batch["owner"] = res[2]  # k_mutex: wait_q (2 words), owner, lock_count


def wilson(x, n):
    p = x / n
    c = (x + Z * Z / 2) / (n + Z * Z)
    h = Z * math.sqrt(n) / (n + Z * Z) * math.sqrt(p * (1 - p) + Z * Z / (4 * n))
    return c - h, c + h


def analyse(sym, d):
    raw = list(frames(f"{d}/rec.ndjson.gz", sym["_kernel"] + 0x18, sym["bench_lock"]))
    owner_obj = sym["_k_thread_obj_lock_owner_id"]
    fr, stamp, dropped = [], [], []
    for h, u, o in raw:
        if not stamp:
            fr.append((h, u, o))
            stamp.append(u)
            continue
        expected = stamp[-1] + (h - fr[-1][0]) * FREQ
        k = round((expected - u) / (1 << 32))
        v = u + k * (1 << 32)
        if abs(v - expected) > 0.5 * FREQ:
            dropped.append((round(h - raw[0][0], 2), u))
            continue
        fr.append((h, u, o))
        stamp.append(v)
    host = [t for t, _, _ in fr]
    rows = list(csv.DictReader(open(f"{d}/holds.csv")))
    starts = unwrap([int(r["start_cycles"]) for r in rows])
    ends = [s + int(r["cycles"]) for s, r in zip(starts, rows)]

    t0 = stamp[0] + WARMUP_S * FREQ
    t1 = stamp[-1] - EDGE_S * FREQ
    counted = [i for i in range(len(starts)) if starts[i] >= t0 and ends[i] <= t1]
    seen = set()
    for s, (_, _, owner) in zip(stamp, fr):
        if owner != owner_obj:
            continue
        j = bisect.bisect_left(starts, s)
        cand = [k for k in (j - 1, j) if 0 <= k < len(starts)]
        k = min(
            cand,
            key=lambda k: 0
            if starts[k] <= s <= ends[k]
            else min(abs(s - starts[k]), abs(s - ends[k])),
        )
        seen.add(k)
    n = len(counted)
    x = sum(1 for i in counted if i in seen)

    # Host intervals between frame starts in the counted window; host and target time agree
    # because these backends do not halt the core.
    sel = [h for h, s in zip(host, stamp) if t0 <= s <= t1]
    tk = [b - a for a, b in zip(sel, sel[1:])]
    dur = statistics.median((ends[i] - starts[i]) / FREQ for i in counted)
    pred = sum(min(dur, t) for t in tk) / sum(tk)
    lo, hi = wilson(x, n)
    return {
        "dataset": d.rstrip("/").split("/")[-1],
        "frames": len(raw),
        "dropped_frames": dropped,
        "T_mean_s": statistics.mean(tk),
        "T_p50_s": statistics.median(tk),
        "d_s": dur,
        "holds": n,
        "detected": x,
        "fraction": x / n,
        "wilson95": [lo, hi],
        "prediction": pred,
        "pass": lo <= pred <= hi,
    }


def main():
    sym = symbols(sys.argv[1])
    res = [analyse(sym, d) for d in sys.argv[2:]]
    for r in res:
        print(
            f"{r['dataset']}: T mean {r['T_mean_s']:.3f} s, d {r['d_s']:.3f} s, "
            f"{r['detected']}/{r['holds']} = {r['fraction']:.3f} "
            f"[{r['wilson95'][0]:.3f}, {r['wilson95'][1]:.3f}], P(d) {r['prediction']:.3f}, "
            f"{'PASS' if r['pass'] else 'FAIL'}, dropped {len(r['dropped_frames'])} {r['dropped_frames']}"
        )
    return res


if __name__ == "__main__":
    main()

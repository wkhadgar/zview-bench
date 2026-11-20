#!/usr/bin/env python3
# Copyright (c) 2026 Paulo Santos (@wkhadgar)
#
# SPDX-License-Identifier: Apache-2.0

"""Q2 read cost per recording, after the 30 s warm-up.

A frame is one begin_batch..end_batch pair with at least one read. Prints the frames kept, the
latency p50, p99 and max, the bytes per frame and the host interval between frame starts.

Usage: q2_stats.py DATASET_DIR [...]
"""

import gzip
import json
import statistics as st
import sys

import numpy as np

SIZE = {"read8": 1, "read32": 4, "read64": 8}
WARMUP_S = 30.0


def frames(path):
    out, cur = [], None
    with gzip.open(path, "rt") as f:
        f.readline()
        for line in f:
            o = json.loads(line)
            op = o.get("op")
            if op == "begin_batch":
                cur = {"b": o["t"], "bytes": 0, "reads": 0}
            elif op == "end_batch" and cur is not None:
                if cur["reads"]:
                    cur["e"] = o["t"]
                    out.append(cur)
                cur = None
            elif cur is not None and (op in SIZE or op == "read_bytes"):
                a = o.get("args", {})
                n = a.get("amount", 1) * SIZE.get(op, 1)
                cur["bytes"] += n
                cur["reads"] += 1
    return out


def main():
    for d in sys.argv[1:]:
        fr = frames(f"{d}/rec.ndjson.gz")
        t0 = fr[0]["b"] + WARMUP_S
        kept = [f for f in fr if f["b"] >= t0]
        lat = np.array([f["e"] - f["b"] for f in kept])
        gaps = [b["b"] - a["b"] for a, b in zip(kept, kept[1:])]
        print(
            f"{d.rstrip('/').split('/')[-1]}: frames {len(kept)} of {len(fr)}, "
            f"latency p50 {np.median(lat):.4f} p99 {np.percentile(lat, 99):.4f} max {lat.max():.4f} s, "
            f"bytes p50 {st.median(f['bytes'] for f in kept)}, "
            f"interval p50 {st.median(gaps):.4f} s"
        )


if __name__ == "__main__":
    main()

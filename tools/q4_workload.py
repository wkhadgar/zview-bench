#!/usr/bin/env python3
# Copyright (c) 2026 Paulo Santos (@wkhadgar)
#
# SPDX-License-Identifier: Apache-2.0

"""Q4 accuracy against the workloads' own definitions, from replayed frames (q4_replay_frames.py).

Usage: compare_workload.py FRAMES.jsonl PERIOD_S
Skips the first 30 s (frames * period). load_id share: rolling mean over one 2 s step, then the
level nearest each defined duty (10, 35, 70 %) as the median of the rolling means within +-8 points.
"""
import json, statistics, sys
fr = [json.loads(l) for l in open(sys.argv[1])]
per = float(sys.argv[2]); skip = int(round(30 / per)); fr = fr[skip:]
def row(f, g, name):
    return next((r for r in f.get(g, []) if r.get("name") == name), None)
msgq = {(r["max_msgs"], r["msg_size"]) for f in fr if (r := row(f, "msgqs", "bench_q"))}
slab = {(r["num_blocks"], r["block_size"], r["max_used"]) for f in fr if (r := row(f, "mem_slabs", "bench_slab"))}
sem = {r["limit"] for f in fr if (r := row(f, "semaphores", "bench_slots"))}
cpu = [r["runtime"]["cpu_normalized"] for f in fr if (r := row(f, "threads", "load_id")) and r["runtime"].get("cpu_normalized") is not None]
print(f"frames {len(fr)} after 30 s; msgq (capacity, size) {msgq}; slab (blocks, size, peak) {slab}; sem limit {sem}")
print(f"load_id CPU % per frame (cpu_normalized), {len(cpu)} frames")
for duty in (10, 35, 70):
    near = sorted(v for v in cpu if abs(v - duty) <= 3)
    within1 = sum(1 for v in cpu if abs(v - duty) <= 1)
    if near:
        print(f"  duty {duty}%: {len(near)} frames within 3 points, median {statistics.median(near):.2f}%, p5 {near[len(near)//20]:.2f}, p95 {near[len(near)*19//20]:.2f}, within 1 point {within1}")

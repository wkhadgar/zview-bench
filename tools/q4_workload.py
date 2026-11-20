#!/usr/bin/env python3
# Copyright (c) 2026 Paulo Santos (@wkhadgar)
#
# SPDX-License-Identifier: Apache-2.0

"""Q4 accuracy of replayed frames. Usage: q4_workload.py FRAMES.jsonl PERIOD_S"""

import json
import statistics
import sys


def row(frame, group, name):
    return next((r for r in frame.get(group, []) if r.get("name") == name), None)


def main():
    frames = [json.loads(line) for line in open(sys.argv[1])]
    period = float(sys.argv[2])
    frames = frames[int(round(30 / period)) :]

    msgq = {(r["max_msgs"], r["msg_size"]) for f in frames if (r := row(f, "msgqs", "bench_q"))}
    slab = {
        (r["num_blocks"], r["block_size"], r["max_used"])
        for f in frames
        if (r := row(f, "mem_slabs", "bench_slab"))
    }
    sem = {r["limit"] for f in frames if (r := row(f, "semaphores", "bench_slots"))}
    # cpu_normalized is the CPU % column (idle included); cpu is Load %.
    cpu = [
        r["runtime"]["cpu_normalized"]
        for f in frames
        if (r := row(f, "threads", "load_id")) and r["runtime"].get("cpu_normalized") is not None
    ]

    print(
        f"frames {len(frames)} after 30 s; msgq (capacity, size) {msgq}; "
        f"slab (blocks, size, peak) {slab}; sem limit {sem}"
    )
    print(f"load_id CPU % per frame (cpu_normalized), {len(cpu)} frames")
    for duty in (10, 35, 70):
        near = sorted(v for v in cpu if abs(v - duty) <= 3)
        within1 = sum(1 for v in cpu if abs(v - duty) <= 1)
        if near:
            print(
                f"  duty {duty}%: {len(near)} frames within 3 points, "
                f"median {statistics.median(near):.2f}%, p5 {near[len(near) // 20]:.2f}, "
                f"p95 {near[len(near) * 19 // 20]:.2f}, within 1 point {within1}"
            )


if __name__ == "__main__":
    main()

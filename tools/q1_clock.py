#!/usr/bin/env python3
# Copyright (c) 2026 Paulo Santos (@wkhadgar)
#
# SPDX-License-Identifier: Apache-2.0

"""Q1 clock ratio: how far the target's time advanced against the host's during a recording.

The CPU 0 usage stamp (`_kernel` + 0x18) holds the timing counter at the last runtime-stats
update, and that counter stops while the core is halted. The ratio is the stamp's advance, in
seconds, over the host time between the same two frames, from 30 to 50 s of the session. Stamps
are unwrapped from 32 bits, and a zero stamp, read between a switch-out and the next switch-in,
is skipped.

Usage: q1_clock.py ELF FREQ_HZ DATASET_DIR [...]
"""

import os
import gzip
import json
import subprocess
import sys

NM = os.environ.get(
    "NM", os.path.expanduser("~/zephyr-sdk-1.0.1/gnu/arm-zephyr-eabi/bin/arm-zephyr-eabi-nm")
)
WARMUP_S = 30.0
# The steady workload stops at 55 s of uptime, after which the stamp only moves at the main
# thread's 1 s wake-ups; the session starts about 3 s after the reset.
STOP_S = 50.0


def kernel_addr(elf):
    for line in subprocess.run(
        [NM, elf], capture_output=True, text=True, check=True
    ).stdout.splitlines():
        p = line.split()
        if len(p) == 3 and p[2] == "_kernel":
            return int(p[0], 16)
    raise SystemExit("no _kernel")


def stamps(path, addr):
    out, cur = [], None
    with gzip.open(path, "rt") as f:
        f.readline()
        for line in f:
            o = json.loads(line)
            op = o.get("op")
            if op == "begin_batch":
                cur = [o["t"], None]
            elif op == "end_batch":
                if cur and cur[1]:
                    out.append(tuple(cur))
                cur = None
            elif cur is not None and op == "read32" and o["args"]["at"] == addr and o.get("result"):
                cur[1] = o["result"][0]
    return out


def main():
    elf, freq = sys.argv[1], float(sys.argv[2])
    addr = kernel_addr(elf) + 0x18
    for d in sys.argv[3:]:
        st = stamps(f"{d}/rec.ndjson.gz", addr)
        st0 = st[0][0]
        t0 = st0 + WARMUP_S
        st = [s for s in st if s[0] >= t0]
        host0, v0 = st[0]
        base, prev_raw, last = 0, v0, (host0, v0)
        for h, u in st[1:]:
            if u == 0:
                continue
            if u < prev_raw - (1 << 31):
                base += 1 << 32
            prev_raw = u
            if h - st0 >= STOP_S:
                break
            last = (h, u + base)
        ratio = (last[1] - v0) / freq / (last[0] - host0)
        print(
            f"{d.rstrip('/').split('/')[-1]}: host {last[0] - host0:.2f} s, "
            f"target {(last[1] - v0) / freq:.2f} s, ratio {ratio:.4f}"
        )


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
# Copyright (c) 2026 Paulo Santos (@wkhadgar)
#
# SPDX-License-Identifier: Apache-2.0

"""Stack bound per thread: puncover's static worst case plus what it cannot see.

puncover counts a recursive function once and does not follow calls through function pointers.
The bound adds the z_thread_entry frame, the bench's known recursion (depth + 1 frames of
force_stack_watermark) and the Armv8-M exception frame (32 B, or 104 B with FP context), and is
compared with ZView's watermark.

THREADS_TXT has one line per thread: name, entry symbol, stack size and ZView's watermark.

Usage: stack_bound.py PUNCOVER_JSON THREADS_TXT
"""

import json
import sys

# force_stack_watermark(depth) call of each thread entry in app/src/dynamic.
DEPTH = {
    "lock_owner_thread": 1,
    "lock_waiter_thread": 2,
    "load_thread": 2,
    "sem_burst_thread": 1,
    "gate_keeper_thread": 2,
    "msgq_tx_thread": 3,
    "msgq_rx_thread": 4,
    "slab_thread": 1,
}


def main():
    report = json.load(open(sys.argv[1]))["no_tag"]["stack_report"]

    def frame(fn):
        return next(f["stack_size"] for f in report[fn]["call_stack"] if f["function"] == fn)

    fsw = frame("force_stack_watermark")
    zte = frame("z_thread_entry")
    print(f"force_stack_watermark frame {fsw} B, z_thread_entry frame {zte} B")
    print("thread entry static_worst rec_path bound32 bound104 zview_wm wm<=bound104")
    for line in open(sys.argv[2]):
        name, entry, _size, wm = line.split()
        wm = int(wm)
        if entry not in report:
            print(name, entry, "no report")
            continue
        worst = report[entry]["max_static_stack_size"]
        rec = frame(entry) + (DEPTH[entry] + 1) * fsw if entry in DEPTH else 0
        base = zte + max(worst, rec)
        print(name, entry, worst, rec, base + 32, base + 104, wm, wm <= base + 104)


if __name__ == "__main__":
    main()

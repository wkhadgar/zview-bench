#!/usr/bin/env python3
# Copyright (c) 2026 Paulo Santos (@wkhadgar)
#
# SPDX-License-Identifier: Apache-2.0

"""Stack bound per thread from puncover's worst case and the bench's recursion depths.

Usage: stack_bound.py PUNCOVER_JSON THREADS_TXT
THREADS_TXT lines: name entry_symbol stack_size zview_watermark (from tools/q4_replay_frames.py output).
Bound = z_thread_entry frame + max(puncover worst case of the entry, entry frame +
(depth + 1) * force_stack_watermark frame) + exception frame (32 B integer, 104 B with FP context).
"""
import json, sys
rep = json.load(open(sys.argv[1]))["no_tag"]["stack_report"]
DEPTH = {"lock_owner_thread": 1, "lock_waiter_thread": 2, "load_thread": 2, "sem_burst_thread": 1,
         "gate_keeper_thread": 2, "msgq_tx_thread": 3, "msgq_rx_thread": 4, "slab_thread": 1}
def frame(fn): return next(f["stack_size"] for f in rep[fn]["call_stack"] if f["function"] == fn)
fsw = frame("force_stack_watermark"); zte = frame("z_thread_entry")
print(f"force_stack_watermark frame {fsw} B, z_thread_entry frame {zte} B")
print("thread entry static_worst rec_path bound32 bound104 zview_wm wm<=bound104")
for line in open(sys.argv[2]):
    name, entry, size, wm = line.split(); size, wm = int(size), int(wm)
    if entry not in rep: print(name, entry, "no report"); continue
    worst = rep[entry]["max_static_stack_size"]
    rec = frame(entry) + (DEPTH[entry] + 1) * fsw if entry in DEPTH else 0
    base = zte + max(worst, rec)
    print(name, entry, worst, rec, base + 32, base + 104, wm, wm <= base + 104)

#!/usr/bin/env python3
# Copyright (c) 2026 Paulo Santos (@wkhadgar)
#
# SPDX-License-Identifier: Apache-2.0

"""Replay a ZView recording unpaced and write every frame as JSON lines (dump --json shape).

Usage: q4_replay_frames.py ZVIEW_SRC ELF REC OUT.jsonl
"""
import json, queue, sys
sys.path.insert(0, sys.argv[1])
from zview.target import Target
from zview.selection import Selection
from zview.frames import Frame, Fatal, Notice, ReplayEnd
from zview.kinds import KINDS

def to_json(groups):
    return {k.key: [k.to_json(i) for i in groups[k.key]] for k in KINDS if k.key in groups}

def main():
    _, src, elf, rec, out = sys.argv
    t = Target(elf, recording=rec, is_paced=False)
    sel = Selection()
    n = 0
    with t.open(sel) as core, open(out, "w") as fp:
        core.start(0)
        try:
            while True:
                try:
                    ev = core.events.get(timeout=30)
                except queue.Empty:
                    break
                if isinstance(ev, ReplayEnd):
                    break
                if isinstance(ev, Fatal):
                    print("fatal", ev, file=sys.stderr); break
                if isinstance(ev, Frame):
                    n += 1
                    fp.write(json.dumps({"t": getattr(ev, "t", None), **to_json(ev.groups)}) + "\n")
        finally:
            core.stop()
    print(f"{n} frames -> {out}")

main()

#!/usr/bin/env python3
# Copyright (c) 2026 Paulo Santos (@wkhadgar)
#
# SPDX-License-Identifier: Apache-2.0

"""Replay a ZView recording without pacing and write every frame as one JSON line.

Each line has the shape of `west zview dump --json`, plus `at`, the frame's replay time. The
ZView source tree is put on the import path, so the replay uses that exact release.

Usage: q4_replay_frames.py ZVIEW_SRC ELF REC OUT.jsonl
"""

import json
import queue
import sys


def main():
    src, elf, rec, out = sys.argv[1:5]
    sys.path.insert(0, src)
    from zview.frames import Fatal, Frame, ReplayEnd
    from zview.kinds import KINDS
    from zview.selection import Selection
    from zview.target import Target

    def to_json(groups):
        return {k.key: [k.to_json(i) for i in groups[k.key]] for k in KINDS if k.key in groups}

    target = Target(elf, recording=rec, is_paced=False)
    count = 0
    with target.open(Selection()) as core, open(out, "w") as fp:
        core.start(0)
        try:
            while True:
                try:
                    event = core.events.get(timeout=30)
                except queue.Empty:
                    break
                if isinstance(event, ReplayEnd):
                    break
                if isinstance(event, Fatal):
                    print("fatal", event, file=sys.stderr)
                    break
                if isinstance(event, Frame):
                    count += 1
                    fp.write(json.dumps({"at": event.at, **to_json(event.groups)}) + "\n")
        finally:
            core.stop()
    print(f"{count} frames -> {out}")


if __name__ == "__main__":
    main()

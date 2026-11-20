#!/usr/bin/env python3
# Copyright (c) 2026 Paulo Santos (@wkhadgar)
#
# SPDX-License-Identifier: Apache-2.0
"""Q4 shell cross-check: ZView's readings against the kernel shell's own statistics.

Stacks: ZView's watermark (dump.json) against the bytes used that `kernel thread stacks` reports.
CPU: ZView's shares in frame 2 of the recording against the shares from the shell's cycle deltas
between the two replies nearest frames 1 and 2. The shell prints 32-bit cycle counts, so deltas
are taken modulo 2**32. Calls `west zview dump`, so run it from the west workspace.

Usage: q4_shell_compare.py ELF DATASET_DIR
"""

import gzip
import json
import re
import subprocess
import sys

ELF, D = sys.argv[1], sys.argv[2]
WRAP = 2**32


def frame_times(path):
    """Host time of each frame: the first call after a gap of more than 5 s, plus the first."""
    times = []
    last = None
    with gzip.open(path, "rt") as f:
        next(f)
        for line in f:
            e = json.loads(line)
            if e.get("op") in ("connect", "begin_batch", "end_batch"):
                continue
            t = e["t"]
            if last is None or t - last > 5.0:
                times.append(t)
            last = t
    return times


def shell_threads(text):
    """{name: cycles} from one `kernel thread list` reply."""
    out, name = {}, None
    for line in text.splitlines():
        m = re.match(r"\s*\*?\s*0x[0-9a-f]+\s+(\S+)", line)
        if m:
            name = m.group(1)
            continue
        m = re.search(r"Total execution cycles: (\d+)", line)
        if m and name:
            out[name] = int(m.group(1))
    return out


def main():
    ft = frame_times(f"{D}/rec.ndjson.gz")
    replies = [json.loads(line) for line in open(f"{D}/shell-list.jsonl")]

    def mid(r):
        return (r["host_start"] + r["host_end"]) / 2

    # A reply can come back cut short; the nearest ones are kept, and missing threads are listed.
    r1 = min(replies, key=lambda r: abs(mid(r) - ft[0]))
    r2 = min(replies, key=lambda r: abs(mid(r) - ft[1]))
    c1, c2 = shell_threads(r1["text"]), shell_threads(r2["text"])
    delta = {n: (c2[n] - c1[n]) % WRAP for n in c2 if n in c1}
    total = sum(delta.values())
    shell_share = {n: 100.0 * v / total for n, v in delta.items()}
    print(
        f"frames at {ft[0]:.2f} and {ft[1]:.2f} s; shell replies at {mid(r1):.2f} and {mid(r2):.2f} s "
        f"(offsets {mid(r1) - ft[0]:+.2f} and {mid(r2) - ft[1]:+.2f} s)"
    )

    dump = json.loads(
        subprocess.run(
            [
                "west",
                "zview",
                "dump",
                "-e",
                ELF,
                "-i",
                f"{D}/rec.ndjson.gz",
                "--frame",
                "2",
                "--json",
            ],
            check=True,
            capture_output=True,
            text=True,
        ).stdout
    )
    # cpu_normalized is the CPU % column (idle included); cpu is Load % (idle excluded).
    zv = {t["name"]: t["runtime"]["cpu_normalized"] for t in dump["threads"] if t.get("runtime")}
    zl = {t["name"]: t["runtime"]["cpu"] for t in dump["threads"] if t.get("runtime")}
    busy = total - delta.get("idle", 0)
    shell_load = {n: (100.0 * v / busy if n != "idle" else 0.0) for n, v in delta.items()}
    print(f"shell threads in the two replies: {len(c1)} and {len(c2)}")
    print("\nCPU share over the same window (percentage points)")
    print(f"{'thread':24s} {'zview':>8s} {'shell':>8s} {'diff':>8s}")
    worst = 0.0
    for n in sorted(set(zv) & set(shell_share), key=lambda n: -shell_share[n]):
        d = zv[n] - shell_share[n]
        worst = max(worst, abs(d))
        print(f"{n:24s} {zv[n]:8.2f} {shell_share[n]:8.2f} {d:+8.2f}")
    print(f"largest difference {worst:.2f} pp")
    lw = max(abs(zl[n] - shell_load[n]) for n in set(zl) & set(shell_load))
    print(
        f"Load % (idle excluded): largest difference {lw:.2f} pp, load_id zview {zl.get('load_id', 0):.2f} shell {shell_load.get('load_id', 0):.2f}"
    )
    print(
        f"threads missing from a shell reply: {sorted((set(c1) | set(c2)) - (set(c1) & set(c2)))}"
    )
    print(
        f"threads only in zview {sorted(set(zv) - set(shell_share))}, "
        f"only in shell {sorted(set(shell_share) - set(zv))}"
    )

    stacks = {}
    for line in open(f"{D}/shell-stacks.txt"):
        m = re.match(
            r"\s*0x[0-9a-f]+\s+(\S+)\s+\(real size\s+(\d+)\):\s+unused\s+(\d+)\s+usage\s+(\d+)",
            line,
        )
        if m:
            stacks[m.group(1)] = (int(m.group(2)), int(m.group(4)))
    snap = json.load(open(f"{D}/dump.json"))
    print("\nStack usage in bytes")
    print(f"{'thread':24s} {'size':>6s} {'zview':>6s} {'shell':>6s} {'diff':>6s}")
    for t in snap["threads"]:
        n, wm = t["name"], (t.get("runtime") or {}).get("stack_watermark")
        if n in stacks and wm is not None:
            size, used = stacks[n]
            print(f"{n:24s} {size:6d} {wm:6d} {used:6d} {wm - used:+6d}")


if __name__ == "__main__":
    main()

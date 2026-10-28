#!/usr/bin/env python3
# Copyright (c) 2026 Paulo Santos (@wkhadgar)
#
# SPDX-License-Identifier: Apache-2.0

"""
Snapshot the dynamic-mode mutex hold log off the target into a CSV.

The owner of ``bench_lock`` writes the start and the end of each hold, in
timing cycles, into the ``bench_holds`` no-init array of ``{start, end}`` pairs
(``bench_hold_head`` is the next slot). The same counter stamps each thread's
usage, so a recording's frames line up with these holds. This reads the log over
a non-halting pyOCD attach, reorders it into chronological order, drops the
hold in progress and the unwritten slots, and writes one row per hold.

Run it after the recording, from the same dataset directory.
"""

import argparse
import csv
import sys

from read_ring import reorder_ring, resolve_symbol

HOLDS_SYMBOL = "bench_holds"
HEAD_SYMBOL = "bench_hold_head"


def pair_words(words: list[int]) -> list[tuple[int, int]]:
    """Split the flat ``start, end, start, end ...`` words into (start, end) pairs."""
    if len(words) % 2:
        raise ValueError("the hold log holds an odd number of words")
    return list(zip(words[0::2], words[1::2], strict=True))


def finished_holds(holds: list[tuple[int, int]]) -> list[tuple[int, int]]:
    """Drop the hold in progress and unwritten slots, both with a zero end."""
    return [(start, end) for start, end in holds if end != 0]


def hold_cycles(start: int, end: int) -> int:
    """The hold's length in cycles, right across a wrap of the 32-bit counter."""
    return (end - start) % (1 << 32)


def read_holds(target: str, elf_path: str) -> tuple[list[tuple[int, int]], int]:
    """Attach over pyOCD and read the reordered, finished holds. Returns (holds, head)."""
    from pyocd.core.helpers import ConnectHelper

    holds_addr, holds_size = resolve_symbol(elf_path, HOLDS_SYMBOL)
    head_addr, _ = resolve_symbol(elf_path, HEAD_SYMBOL)

    session = ConnectHelper.session_with_chosen_probe(target_override=target, connect_mode="attach")
    if session is None:
        raise RuntimeError("no pyOCD probe found")
    with session:
        t = session.target
        head = t.read_memory_block32(head_addr, 1)[0]
        words = list(t.read_memory_block32(holds_addr, holds_size // 4))

    return finished_holds(reorder_ring(pair_words(words), head)), head


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--elf", required=True, help="The flashed dynamic-mode ELF.")
    ap.add_argument("--target", required=True, help="pyOCD target name.")
    ap.add_argument("--freq-hz", type=float, required=True, help="Timing counter clock, in Hz.")
    ap.add_argument("-o", "--output", required=True, help="Output CSV path.")
    args = ap.parse_args(argv)

    holds, head = read_holds(args.target, args.elf)
    with open(args.output, "w", newline="") as fp:
        w = csv.writer(fp)
        w.writerow(["index", "start_cycles", "end_cycles", "cycles", "ms"])
        for i, (start, end) in enumerate(holds):
            cycles = hold_cycles(start, end)
            w.writerow([i, start, end, cycles, round(cycles / args.freq_hz * 1e3, 3)])

    print(f"wrote {len(holds)} holds to {args.output} (head={head})", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())

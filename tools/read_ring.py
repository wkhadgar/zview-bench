#!/usr/bin/env python3
# Copyright (c) 2026 Paulo Santos (@wkhadgar)
#
# SPDX-License-Identifier: Apache-2.0

"""
Snapshot the steady-mode DWT per-period ring off the target into a CSV.

The metronome records each period's work-window cycle count into the
``bench_period_cycles`` no-init array, and the cycles from the start of the
previous window into ``bench_start_cycles`` (``bench_period_head`` is the next
write slot of both). This reads them over a non-halting pyOCD attach, reorders
the ring into chronological order, drops unwritten slots, and writes one row
per period.

With ``--stop`` it first sets ``bench_stop``, waits for the metronome to see it,
and only then reads, so the read's bus traffic touches no measured window.

Run it once per condition (ZView detached vs polling); feed the CSVs to the
distribution comparison.
"""

import argparse
import csv
import sys
import time
from pathlib import Path

from elftools.elf.elffile import ELFFile

CYCLES_SYMBOL = "bench_period_cycles"
START_SYMBOL = "bench_start_cycles"
HEAD_SYMBOL = "bench_period_head"
STOP_SYMBOL = "bench_stop"


def resolve_symbol(elf_path: str | Path, name: str) -> tuple[int, int]:
    """Return ``(address, size_bytes)`` of a named symbol from the ELF symtab."""
    with open(elf_path, "rb") as fp:
        elf = ELFFile(fp)
        symtab = elf.get_section_by_name(".symtab")
        if symtab is None:
            raise LookupError("ELF has no .symtab")
        for sym in symtab.iter_symbols():
            if sym.name == name:
                return sym["st_value"], sym["st_size"]
    raise LookupError(f"symbol {name!r} not found")


def reorder_ring(values: list[int], head: int) -> list[int]:
    """Chronological oldest-to-newest order; ``head`` is the next write slot."""
    if not values:
        return []
    head %= len(values)
    return values[head:] + values[:head]


def drop_unwritten(values: list[int]) -> list[int]:
    """Drop zero slots (never written; real work-window counts are never zero)."""
    return [v for v in values if v != 0]


def pair_rings(windows: list[int], starts: list[int] | None) -> list[tuple[int, int | None]]:
    """
    Pair each written window with its start-to-start time, both in ring order.

    Slots are dropped by the window alone, since the first window of a run has
    no previous start and records a start-to-start of zero. Without the second
    ring (an older build), every start-to-start is None.
    """
    starts = starts if starts is not None else [None] * len(windows)
    return [(w, s) for w, s in zip(windows, starts, strict=True) if w != 0]


def read_ring(
    target: str, elf_path: str, stop: bool = False, settle_s: float = 0.1
) -> tuple[list[tuple[int, int | None]], int]:
    """Attach over pyOCD and read the reordered, written ring. Returns (rows, head)."""
    from pyocd.core.helpers import ConnectHelper

    cyc_addr, cyc_size = resolve_symbol(elf_path, CYCLES_SYMBOL)
    head_addr, _ = resolve_symbol(elf_path, HEAD_SYMBOL)
    try:
        start_addr, _ = resolve_symbol(elf_path, START_SYMBOL)
    except LookupError:
        start_addr = None
    stop_addr = resolve_symbol(elf_path, STOP_SYMBOL)[0] if stop else None
    count = cyc_size // 4

    session = ConnectHelper.session_with_chosen_probe(target_override=target, connect_mode="attach")
    if session is None:
        raise RuntimeError("no pyOCD probe found")
    with session:
        t = session.target
        if stop_addr is not None:
            t.write_memory_block32(stop_addr, [1])
            # The metronome checks the flag once per period.
            time.sleep(settle_s)
        head = t.read_memory_block32(head_addr, 1)[0]
        windows = list(t.read_memory_block32(cyc_addr, count))
        starts = list(t.read_memory_block32(start_addr, count)) if start_addr is not None else None

    windows = reorder_ring(windows, head)
    starts = reorder_ring(starts, head) if starts is not None else None
    return pair_rings(windows, starts), head


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--elf", required=True, help="The flashed steady-mode ELF.")
    ap.add_argument("--target", default="stm32h753zitx", help="pyOCD target name.")
    ap.add_argument("--freq-hz", type=float, default=480e6, help="Core clock for ns conversion.")
    ap.add_argument("--stop", action="store_true", help="Set bench_stop before reading.")
    ap.add_argument(
        "--settle", type=float, default=0.1, help="Seconds to wait after --stop (default 0.1)."
    )
    ap.add_argument("-o", "--output", required=True, help="Output CSV path.")
    args = ap.parse_args(argv)

    rows, head = read_ring(args.target, args.elf, stop=args.stop, settle_s=args.settle)
    with open(args.output, "w", newline="") as fp:
        w = csv.writer(fp)
        w.writerow(["index", "cycles", "ns", "start_cycles", "start_ns"])
        for i, (c, s) in enumerate(rows):
            start_ns = "" if s is None else round(s / args.freq_hz * 1e9, 1)
            w.writerow([i, c, round(c / args.freq_hz * 1e9, 1), "" if s is None else s, start_ns])

    print(f"wrote {len(rows)} periods to {args.output} (head={head})", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())

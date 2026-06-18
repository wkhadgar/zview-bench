#!/usr/bin/env python3
# Copyright (c) 2026 Paulo Santos (@wkhadgar)
#
# SPDX-License-Identifier: Apache-2.0

"""
Snapshot the steady-mode DWT per-period ring off the target into a CSV.

The metronome records each period's work-window cycle count into the
``bench_period_cycles`` no-init array (``bench_period_head`` is the next write
slot). This reads both over a non-halting pyOCD attach, reorders the ring into
chronological order, drops unwritten slots, and writes one row per period.

Run it once per condition (ZView detached vs polling); feed the CSVs to the
distribution comparison.
"""

import argparse
import csv
import sys
from pathlib import Path

from elftools.elf.elffile import ELFFile

CYCLES_SYMBOL = "bench_period_cycles"
HEAD_SYMBOL = "bench_period_head"


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


def read_ring(target: str, elf_path: str) -> tuple[list[int], int]:
    """Attach over pyOCD and read the reordered, written ring. Returns (cycles, head)."""
    from pyocd.core.helpers import ConnectHelper

    cyc_addr, cyc_size = resolve_symbol(elf_path, CYCLES_SYMBOL)
    head_addr, _ = resolve_symbol(elf_path, HEAD_SYMBOL)
    count = cyc_size // 4

    session = ConnectHelper.session_with_chosen_probe(target_override=target, connect_mode="attach")
    if session is None:
        raise RuntimeError("no pyOCD probe found")
    with session:
        t = session.target
        head = t.read_memory_block32(head_addr, 1)[0]
        raw = list(t.read_memory_block32(cyc_addr, count))

    return drop_unwritten(reorder_ring(raw, head)), head


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--elf", required=True, help="The flashed steady-mode ELF.")
    ap.add_argument("--target", default="stm32h753zitx", help="pyOCD target name.")
    ap.add_argument("--freq-hz", type=float, default=480e6, help="Core clock for ns conversion.")
    ap.add_argument("-o", "--output", required=True, help="Output CSV path.")
    args = ap.parse_args(argv)

    cycles, head = read_ring(args.target, args.elf)
    with open(args.output, "w", newline="") as fp:
        w = csv.writer(fp)
        w.writerow(["index", "cycles", "ns"])
        for i, c in enumerate(cycles):
            w.writerow([i, c, round(c / args.freq_hz * 1e9, 1)])

    print(f"wrote {len(cycles)} periods to {args.output} (head={head})", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())

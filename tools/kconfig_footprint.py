#!/usr/bin/env python3
# Copyright (c) 2026 Paulo Santos (@wkhadgar)
#
# SPDX-License-Identifier: Apache-2.0

"""
Measure the flash and RAM cost of the Kconfig options ZView needs.

Builds one app repeatedly with a different Kconfig overlay each time and diffs
the end-of-build ``Memory region`` table against a baseline that forces every
option OFF, so the app's own defaults cannot hide a cost. Reports each option
alone, a required-only subtotal, an optional-only subtotal, and all of them
together. Pristine builds throughout. Pure stdlib.

Singles do not sum to the subtotals: the options share code and struct space, so
quote a subtotal rather than adding the rows up.

Two options are accounted per object rather than globally:
``SYS_HEAP_RUNTIME_STATS`` costs per heap and ``MEM_SLAB_TRACE_MAX_UTILIZATION``
per slab. An app that declares neither measures both as zero and understates the
bill. The published figures were taken on Zephyr's ``samples/synchronization``
with one ``K_HEAP_DEFINE(fp_heap, 1024)`` and one
``K_MEM_SLAB_DEFINE(fp_slab, 64, 4, 4)`` added and touched once from ``main``, so
that both had a real object to account for.

Example:

    tools/kconfig_footprint.py --west-topdir ~/zephyrproject \\
        --board rpi_pico2/rp2350a/m33 --app path/to/app
"""

import argparse
import re
import shutil
import subprocess
import sys
from pathlib import Path

# Without these three ZView shows nothing: no watermark, no thread discovery, no
# per-thread metadata.
REQUIRED = [
    "CONFIG_INIT_STACKS",
    "CONFIG_THREAD_MONITOR",
    "CONFIG_THREAD_STACK_INFO",
]

# Each of these buys one view and can be left out.
OPTIONAL = [
    "CONFIG_THREAD_NAME",
    "CONFIG_THREAD_RUNTIME_STATS",
    "CONFIG_SYS_HEAP_RUNTIME_STATS",
    "CONFIG_MEM_SLAB_TRACE_MAX_UTILIZATION",
]

ALL_OPTIONS = REQUIRED + OPTIONAL

# "           FLASH:       19404 B         4 MB      0.46%"
REGION_RE = re.compile(r"^\s*(\w+):\s+(\d+) B\s", re.MULTILINE)


def write_overlay(path: Path, enabled: list[str]) -> None:
    """Write an overlay setting every known option, only `enabled` to y."""
    on = set(enabled)
    lines = [f"{opt}={'y' if opt in on else 'n'}" for opt in ALL_OPTIONS]
    path.write_text("\n".join(lines) + "\n")


def regions(log: str) -> dict[str, int]:
    """Used bytes per memory region, from a build log's region table."""
    return {name: int(size) for name, size in REGION_RE.findall(log)}


def build(args, name: str, enabled: list[str]) -> dict[str, int]:
    """Build one variant pristine and return its per-region used bytes."""
    overlay = args.out / f"{name}.conf"
    write_overlay(overlay, enabled)

    cmd = [
        str(args.west),
        "build",
        "-p",
        "always",
        "-b",
        args.board,
        str(args.app),
        "-d",
        str(args.out / f"b-{name}"),
        "--",
        f"-DEXTRA_CONF_FILE={overlay}",
    ]
    done = subprocess.run(cmd, cwd=args.west_topdir, capture_output=True, text=True)
    log = done.stdout + done.stderr
    (args.out / f"{name}.log").write_text(log)

    if done.returncode != 0:
        sys.exit(f"build failed for {name}; see {args.out / f'{name}.log'}")

    found = regions(log)
    if not found:
        sys.exit(f"no memory region table in {name} build output")
    return found


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--west-topdir", type=Path, required=True, help="west workspace root")
    parser.add_argument("--board", required=True, help="board target, as west build -b takes it")
    parser.add_argument("--app", type=Path, required=True, help="application to build")
    parser.add_argument(
        "--out",
        type=Path,
        default=Path("footprint-out"),
        help="directory for overlays, build trees and logs (default: ./footprint-out)",
    )
    parser.add_argument(
        "--west",
        default=shutil.which("west") or "west",
        help="west executable (default: the one on PATH)",
    )
    args = parser.parse_args()

    args.app = args.app.resolve()
    args.out = args.out.resolve()
    args.out.mkdir(parents=True, exist_ok=True)

    base = build(args, "base", [])
    print(f"baseline: {', '.join(f'{k} {v} B' for k, v in base.items())}\n")

    rows: list[tuple[str, dict[str, int]]] = []
    for opt in ALL_OPTIONS:
        rows.append((opt, build(args, opt, [opt])))
    rows.append(("all required", build(args, "req", REQUIRED)))
    rows.append(("all optional", build(args, "opt", OPTIONAL)))
    rows.append(("everything", build(args, "all", ALL_OPTIONS)))

    # Boards report regions these options never touch, IDT_LIST among them.
    # Drop any region that is unchanged by every variant, so the table carries
    # only columns that moved.
    names = [n for n in sorted(base) if any(m.get(n, 0) != base[n] for _, m in rows)]
    if not names:
        names = sorted(base)

    width = max(len(label) for label, _ in rows)
    header = "  ".join(f"{n:>9}" for n in names)
    print(f"{'option'.ljust(width)}  {header}")
    for label, measured in rows:
        deltas = "  ".join(f"{measured.get(n, 0) - base[n]:>+9}" for n in names)
        print(f"{label.ljust(width)}  {deltas}")

    print("\nDeltas in bytes against the all-off baseline. Singles do not sum to")
    print("the subtotals, because the options share code and struct space.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

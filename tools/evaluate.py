#!/usr/bin/env python3
# Copyright (c) 2026 Paulo Santos (@wkhadgar)
#
# SPDX-License-Identifier: Apache-2.0

"""
Offline analyzer for ZView recordings.

Parses a ``zview record`` NDJSON file, groups backend calls into poll frames
(``begin_batch``..``end_batch``), and reports the per-poll read load and host
cadence: the inputs to the benchmark's contention analysis. Pure stdlib.
"""

import argparse
import gzip
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path

# Bytes per element for the fixed-width read ops. ``read_bytes`` is special:
# its ``amount`` argument is already a byte count.
OP_WIDTH = {"read8": 1, "read32": 4, "read64": 8}
READ_OPS = set(OP_WIDTH) | {"read_bytes"}


def _read_byte_count(op: str, args: dict, result) -> int:
    """Bytes moved by one read entry."""
    if op == "read_bytes":
        return int(args.get("amount", 0))
    if op in OP_WIDTH:
        return len(result or []) * OP_WIDTH[op]
    return 0


@dataclass
class Frame:
    """One ``begin_batch``..``end_batch`` group."""

    index: int
    t_begin: float
    t_end: float | None = None
    reads: dict[str, int] = field(default_factory=dict)
    bytes_by_op: dict[str, int] = field(default_factory=dict)
    max_read_bytes: int = 0

    def add_read(self, op: str, nbytes: int) -> None:
        self.reads[op] = self.reads.get(op, 0) + 1
        self.bytes_by_op[op] = self.bytes_by_op.get(op, 0) + nbytes
        self.max_read_bytes = max(self.max_read_bytes, nbytes)

    @property
    def latency(self) -> float | None:
        return None if self.t_end is None else self.t_end - self.t_begin

    @property
    def total_bytes(self) -> int:
        return sum(self.bytes_by_op.values())

    @property
    def total_reads(self) -> int:
        return sum(self.reads.values())

    @property
    def is_poll(self) -> bool:
        """A poll frame reads per-thread usage (read64); the thread-list walk does not."""
        return "read64" in self.reads


def load_entries(path: str | Path) -> tuple[dict, list[dict]]:
    """Return ``(header, entries)`` from a recording. Accepts gzip or plain NDJSON."""
    p = Path(path)
    opener = gzip.open if p.suffix == ".gz" else open
    with opener(p, "rt", encoding="utf-8") as fp:
        lines = [json.loads(ln) for ln in fp if ln.strip()]
    if not lines:
        raise ValueError(f"{p} is empty")
    return lines[0], lines[1:]


def group_frames(entries: list[dict]) -> tuple[list[Frame], int]:
    """Group entries into frames. Returns ``(frames, reads_outside_any_frame)``."""
    frames: list[Frame] = []
    current: Frame | None = None
    orphan_reads = 0

    for e in entries:
        op = e.get("op")
        if op == "begin_batch":
            current = Frame(index=len(frames), t_begin=e.get("t", 0.0))
            frames.append(current)
        elif op == "end_batch":
            if current is not None:
                current.t_end = e.get("t", current.t_begin)
                current = None
        elif op in READ_OPS:
            nbytes = _read_byte_count(op, e.get("args", {}), e.get("result"))
            if current is None:
                orphan_reads += 1
            else:
                current.add_read(op, nbytes)
        # connect/disconnect and unknown ops are ignored.

    return frames, orphan_reads


def _percentile(values: list[float], q: float) -> float:
    """Linear-interpolated percentile, ``q`` in [0, 1]."""
    if not values:
        return 0.0
    s = sorted(values)
    if len(s) == 1:
        return float(s[0])
    pos = (len(s) - 1) * q
    lo = int(pos)
    hi = min(lo + 1, len(s) - 1)
    frac = pos - lo
    return s[lo] * (1.0 - frac) + s[hi] * frac


def _stats(values: list[float]) -> dict:
    """mean/min/p50/p99/max over a list; zeros for empty."""
    if not values:
        return {"n": 0, "mean": 0.0, "min": 0.0, "p50": 0.0, "p99": 0.0, "max": 0.0}
    return {
        "n": len(values),
        "mean": sum(values) / len(values),
        "min": min(values),
        "p50": _percentile(values, 0.50),
        "p99": _percentile(values, 0.99),
        "max": max(values),
    }


def summarize(header: dict, frames: list[Frame], orphan_reads: int) -> dict:
    """Aggregate frame metrics into the benchmark report dict."""
    data_frames = [f for f in frames if f.total_reads > 0]
    poll_frames = [f for f in data_frames if f.is_poll]
    setup_frames = [f for f in data_frames if not f.is_poll]

    # Watermark-cache asymmetry lives among poll frames: the first poll scans
    # full stacks, later polls read only the residual above each cached mark.
    # Fall back to all data frames when usage reads are absent (no read64).
    seq = poll_frames if poll_frames else data_frames
    first = seq[0] if seq else None
    steady = seq[1:]

    latencies = [f.latency for f in data_frames if f.latency is not None]
    begins = [f.t_begin for f in frames]
    cadence = [b - a for a, b in zip(begins, begins[1:], strict=False)]

    def frame_view(f: Frame | None) -> dict:
        if f is None:
            return {}
        return {
            "index": f.index,
            "latency_s": f.latency,
            "total_reads": f.total_reads,
            "total_bytes": f.total_bytes,
            "max_read_bytes": f.max_read_bytes,
            "reads_by_op": dict(sorted(f.reads.items())),
            "bytes_by_op": dict(sorted(f.bytes_by_op.items())),
            "is_poll": f.is_poll,
        }

    return {
        "schema": header.get("schema"),
        "endianess": header.get("endianess"),
        "frames_total": len(frames),
        "data_frames": len(data_frames),
        "poll_frames": len(poll_frames),
        "setup_frames": len(setup_frames),
        "orphan_reads": orphan_reads,
        "first_poll_frame": frame_view(first),
        "steady": {
            "frames": len(steady),
            "latency_s": _stats([f.latency for f in steady if f.latency is not None]),
            "total_bytes": _stats([float(f.total_bytes) for f in steady]),
            "read32_bytes": _stats([float(f.bytes_by_op.get("read32", 0)) for f in steady]),
        },
        "all_frames": {
            "latency_s": _stats(latencies),
            "total_bytes": _stats([float(f.total_bytes) for f in data_frames]),
        },
        "cadence_s": _stats(cadence),
    }


def render_text(summary: dict) -> str:
    """Human-readable report."""
    lines: list[str] = []
    lines.append(f"schema           {summary['schema']}")
    lines.append(
        f"frames           {summary['frames_total']} "
        f"({summary['poll_frames']} poll, {summary['setup_frames']} setup)"
    )
    if summary["orphan_reads"]:
        lines.append(f"orphan reads     {summary['orphan_reads']} (outside any batch)")

    fdf = summary["first_poll_frame"]
    if fdf:
        lines.append("")
        lines.append("first poll frame (heaviest; full stack scan)")
        lines.append(f"  reads          {fdf['total_reads']}  ({fdf['reads_by_op']})")
        lines.append(f"  bytes          {fdf['total_bytes']}  ({fdf['bytes_by_op']})")
        lines.append(f"  largest read   {fdf['max_read_bytes']} B")
        if fdf["latency_s"] is not None:
            lines.append(f"  latency        {fdf['latency_s'] * 1e3:.3f} ms")

    st = summary["steady"]

    def fmt(stats: dict, scale: float, unit: str) -> str:
        return (
            f"mean {stats['mean'] * scale:.3f} p50 {stats['p50'] * scale:.3f} "
            f"p99 {stats['p99'] * scale:.3f} max {stats['max'] * scale:.3f} {unit}"
        )

    lines.append("")
    lines.append(f"steady poll      {st['frames']} frames")
    if st["frames"]:
        lines.append(f"  latency        {fmt(st['latency_s'], 1e3, 'ms')}")
        lines.append(f"  total bytes    {fmt(st['total_bytes'], 1.0, 'B')}")
        lines.append(f"  read32 bytes   {fmt(st['read32_bytes'], 1.0, 'B')}")

    if fdf and st["frames"] and st["total_bytes"]["p50"] > 0:
        ratio = fdf["total_bytes"] / st["total_bytes"]["p50"]
        lines.append(f"  frame1/steady  {ratio:.1f}x bytes (watermark-cache effect)")

    cad = summary["cadence_s"]
    lines.append("")
    lines.append(f"poll cadence     {fmt(cad, 1e3, 'ms')}")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("recording", help="Path to a .ndjson(.gz) recording.")
    parser.add_argument("--json", action="store_true", help="Emit the summary as JSON.")
    args = parser.parse_args(argv)

    header, entries = load_entries(args.recording)
    frames, orphan = group_frames(entries)
    summary = summarize(header, frames, orphan)

    if args.json:
        print(json.dumps(summary, indent=2))
    else:
        print(render_text(summary))
    return 0


if __name__ == "__main__":
    sys.exit(main())

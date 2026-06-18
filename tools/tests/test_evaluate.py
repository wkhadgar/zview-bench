# Copyright (c) 2026 Paulo Santos (@wkhadgar)
#
# SPDX-License-Identifier: Apache-2.0

"""Coverage for the offline recording analyzer, tools/evaluate.py."""

import gzip
import json
import sys
from pathlib import Path

import pytest

_TOOLS_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_TOOLS_DIR))

import evaluate  # noqa: E402

_FIXTURE = _TOOLS_DIR / "tests" / "fixtures" / "sample.ndjson.gz"


def _write_recording(path: Path, entries: list[dict], header: dict | None = None) -> None:
    hdr = header or {"schema": "zview-recording/2", "endianess": "<", "created_at": 0.0}
    with gzip.open(path, "wt", encoding="utf-8") as fp:
        fp.write(json.dumps(hdr) + "\n")
        for e in entries:
            fp.write(json.dumps(e) + "\n")


# --- byte accounting --------------------------------------------------------


def test_read_byte_count_widths():
    assert evaluate._read_byte_count("read8", {"amount": 4}, [0, 0, 0, 0]) == 4
    assert evaluate._read_byte_count("read32", {"amount": 3}, [1, 2, 3]) == 12
    assert evaluate._read_byte_count("read64", {"amount": 2}, [1, 2]) == 16


def test_read_byte_count_read_bytes_uses_amount():
    # read_bytes result is a hex string; the amount is the byte count.
    assert evaluate._read_byte_count("read_bytes", {"amount": 64}, "00" * 64) == 64


def test_read_byte_count_ignores_non_read_ops():
    assert evaluate._read_byte_count("begin_batch", {}, None) == 0


# --- frame grouping ---------------------------------------------------------


def _frame(reads):
    """entries for one begin/read*/end batch."""
    out = [{"t": 0.0, "op": "begin_batch", "args": {}}]
    for op, at, amount, result in reads:
        out.append({"t": 0.0, "op": op, "args": {"at": at, "amount": amount}, "result": result})
    out.append({"t": 0.0, "op": "end_batch", "args": {}})
    return out


def test_group_frames_basic_counts_and_bytes():
    entries = [
        {"t": 0.0, "op": "connect", "args": {}},
        {"t": 1.0, "op": "begin_batch", "args": {}},
        {"t": 1.0, "op": "read32", "args": {"at": 0, "amount": 2}, "result": [1, 2]},
        {"t": 1.0, "op": "read64", "args": {"at": 8, "amount": 1}, "result": [9]},
        {"t": 1.5, "op": "end_batch", "args": {}},
    ]
    frames, orphan = evaluate.group_frames(entries)
    assert orphan == 0
    assert len(frames) == 1
    f = frames[0]
    assert f.total_reads == 2
    assert f.bytes_by_op == {"read32": 8, "read64": 8}
    assert f.total_bytes == 16
    assert f.max_read_bytes == 8
    assert f.latency == pytest.approx(0.5)
    assert f.is_poll is True  # has read64


def test_group_frames_thread_walk_is_not_poll():
    """A batch with only read32 (no per-thread usage read) is not a poll frame."""
    frames, _ = evaluate.group_frames(_frame([("read32", 0, 1, [5])]))
    assert frames[0].is_poll is False


def test_group_frames_counts_orphan_reads():
    entries = [
        {"t": 0.0, "op": "connect", "args": {}},
        {"t": 0.0, "op": "read32", "args": {"at": 0, "amount": 1}, "result": [1]},
    ]
    frames, orphan = evaluate.group_frames(entries)
    assert frames == []
    assert orphan == 1


def test_group_frames_open_frame_has_no_latency():
    entries = [{"t": 0.0, "op": "begin_batch", "args": {}}]
    frames, _ = evaluate.group_frames(entries)
    assert frames[0].latency is None


# --- percentile / stats -----------------------------------------------------


def test_percentile_edges():
    assert evaluate._percentile([], 0.5) == 0.0
    assert evaluate._percentile([42.0], 0.99) == 42.0
    assert evaluate._percentile([0.0, 10.0], 0.5) == pytest.approx(5.0)
    assert evaluate._percentile([0.0, 100.0], 0.99) == pytest.approx(99.0)


def test_stats_shape():
    s = evaluate._stats([1.0, 2.0, 3.0])
    assert s["n"] == 3
    assert s["mean"] == pytest.approx(2.0)
    assert s["min"] == 1.0
    assert s["max"] == 3.0


# --- summarize: watermark-cache asymmetry -----------------------------------


def test_summarize_first_poll_heavier_than_steady():
    """First poll frame scans full stacks; later frames read the residual."""
    heavy = _frame([("read64", 8, 1, [0]), ("read32", 0x2000, 250, list(range(250)))])
    light = _frame([("read64", 8, 1, [0]), ("read32", 0x2000, 4, [0, 0, 0, 0])])
    header = {"schema": "zview-recording/2", "endianess": "<"}
    frames, orphan = evaluate.group_frames(heavy + light + light)
    summary = evaluate.summarize(header, frames, orphan)

    assert summary["data_frames"] == 3
    assert summary["poll_frames"] == 3
    assert summary["first_poll_frame"]["total_bytes"] == 250 * 4 + 8
    assert summary["steady"]["frames"] == 2
    # Steady read32 load is the 4-word residual, far below frame 1.
    assert summary["steady"]["read32_bytes"]["max"] == 16
    assert summary["first_poll_frame"]["total_bytes"] > summary["steady"]["total_bytes"]["max"]


def test_summarize_excludes_setup_frame_from_poll_stats():
    """A leading read32-only thread-walk batch is a setup frame, not a poll."""
    walk = _frame([("read32", 0x500, 1, [0x1000]), ("read32", 0x1000, 48, list(range(48)))])
    poll = _frame([("read64", 8, 1, [0]), ("read32", 0x2000, 4, [0, 0, 0, 0])])
    frames, orphan = evaluate.group_frames(walk + poll + poll)
    summary = evaluate.summarize({}, frames, orphan)

    assert summary["setup_frames"] == 1
    assert summary["poll_frames"] == 2
    # The heavy first poll is poll[0]; the setup walk does not contaminate it.
    assert summary["first_poll_frame"]["is_poll"] is True
    assert summary["first_poll_frame"]["index"] == 1


def test_summarize_cadence_from_begin_timestamps():
    entries = []
    for i in range(4):
        b = {"t": float(i), "op": "begin_batch", "args": {}}
        r = {"t": float(i), "op": "read32", "args": {"at": 0, "amount": 1}, "result": [0]}
        e = {"t": float(i) + 0.1, "op": "end_batch", "args": {}}
        entries += [b, r, e]
    frames, orphan = evaluate.group_frames(entries)
    summary = evaluate.summarize({}, frames, orphan)
    assert summary["cadence_s"]["mean"] == pytest.approx(1.0)


# --- end to end against the committed fixture -------------------------------


def test_load_and_summarize_real_fixture():
    header, entries = evaluate.load_entries(_FIXTURE)
    assert header["schema"].startswith("zview-recording/")

    frames, orphan = evaluate.group_frames(entries)
    summary = evaluate.summarize(header, frames, orphan)

    assert summary["data_frames"] >= 1
    assert summary["all_frames"]["total_bytes"]["mean"] > 0
    # At least one real poll frame (per-thread usage read present).
    assert any(f.is_poll for f in frames)
    # JSON-serializable (the harness emits --json).
    json.dumps(summary)


def test_main_json_runs_on_fixture(capsys):
    rc = evaluate.main([str(_FIXTURE), "--json"])
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert out["frames_total"] >= 1


def test_main_text_runs_on_fixture(capsys):
    rc = evaluate.main([str(_FIXTURE)])
    assert rc == 0
    assert "poll cadence" in capsys.readouterr().out


def test_load_entries_rejects_empty(tmp_path):
    p = tmp_path / "empty.ndjson.gz"
    with gzip.open(p, "wt", encoding="utf-8") as fp:
        fp.write("")
    with pytest.raises(ValueError, match="empty"):
        evaluate.load_entries(p)

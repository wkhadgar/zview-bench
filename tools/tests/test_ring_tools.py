# Copyright (c) 2026 Paulo Santos (@wkhadgar)
#
# SPDX-License-Identifier: Apache-2.0

"""Coverage for the pure logic in tools/read_ring.py."""

import sys
from pathlib import Path

import pytest

_TOOLS_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_TOOLS_DIR))

import read_ring  # noqa: E402

# The flashed ELF is a build artifact outside the repo; tests that need it skip
# when it is absent (e.g. CI without a build).
_ELF_CANDIDATES = [
    _TOOLS_DIR.parent.parent / "build" / "zephyr" / "zephyr.elf",
]


def _find_elf() -> Path | None:
    return next((p for p in _ELF_CANDIDATES if p.exists()), None)


def test_reorder_ring_empty():
    assert read_ring.reorder_ring([], 0) == []


def test_reorder_ring_head_zero_is_identity():
    assert read_ring.reorder_ring([1, 2, 3, 4], 0) == [1, 2, 3, 4]


def test_reorder_ring_rotates_at_head():
    # head = next write slot; chronological oldest..newest starts at head.
    assert read_ring.reorder_ring([30, 40, 10, 20], 2) == [10, 20, 30, 40]


def test_reorder_ring_head_wraps_modulo_len():
    assert read_ring.reorder_ring([1, 2, 3, 4], 6) == read_ring.reorder_ring([1, 2, 3, 4], 2)


def test_drop_unwritten_removes_zeros():
    assert read_ring.drop_unwritten([0, 0, 132000, 131500, 0]) == [132000, 131500]


def test_drop_unwritten_all_zero_is_empty():
    assert read_ring.drop_unwritten([0, 0, 0]) == []


def test_resolve_symbol_finds_ring_symbols():
    elf = _find_elf()
    if elf is None:
        pytest.skip("no flashed ELF available")
    cyc_addr, cyc_size = read_ring.resolve_symbol(elf, "bench_period_cycles")
    head_addr, _ = read_ring.resolve_symbol(elf, "bench_period_head")
    assert cyc_addr != 0
    assert cyc_size > 0 and cyc_size % 4 == 0  # uint32 array
    assert head_addr != 0


def test_resolve_symbol_missing_raises():
    elf = _find_elf()
    if elf is None:
        pytest.skip("no flashed ELF available")
    with pytest.raises(LookupError):
        read_ring.resolve_symbol(elf, "no_such_symbol_xyz")

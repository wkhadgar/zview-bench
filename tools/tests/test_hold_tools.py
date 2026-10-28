# Copyright (c) 2026 Paulo Santos (@wkhadgar)
#
# SPDX-License-Identifier: Apache-2.0

"""Coverage for the pure logic in tools/read_holds.py."""

import sys
from pathlib import Path

import pytest

_TOOLS_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_TOOLS_DIR))

import read_holds  # noqa: E402
import read_ring  # noqa: E402


def test_pair_words_splits_start_and_end():
    assert read_holds.pair_words([1, 2, 3, 4]) == [(1, 2), (3, 4)]


def test_pair_words_rejects_an_odd_count():
    with pytest.raises(ValueError):
        read_holds.pair_words([1, 2, 3])


def test_finished_holds_drops_the_hold_in_progress_and_unwritten_slots():
    assert read_holds.finished_holds([(10, 20), (30, 0), (0, 0)]) == [(10, 20)]


def test_hold_cycles_across_a_counter_wrap():
    assert read_holds.hold_cycles(0xFFFF_FFF0, 0x10) == 0x20


def test_holds_come_out_oldest_first():
    # head = 1: slot 1 is the oldest, slot 0 the newest.
    holds = read_ring.reorder_ring(read_holds.pair_words([50, 60, 10, 20]), 1)
    assert read_holds.finished_holds(holds) == [(10, 20), (50, 60)]

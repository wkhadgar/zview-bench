/*
 * Copyright (c) 2026 Paulo Santos (@wkhadgar)
 * SPDX-License-Identifier: Apache-2.0
 *
 * Steady-state mode: a metronome thread on an absolute deadline, for measuring
 * a probe's timing perturbation.
 */

#include <stddef.h>
#include <stdint.h>

#include <zephyr/kernel.h>
#include <zephyr/timing/timing.h>

#include "bench.h"

#define METRO_STACK   2048
#define METRO_PRIO    7
#define PERIOD_MS     CONFIG_ZVIEW_BENCH_PERIOD_MS
#define STREAM_WORDS  CONFIG_ZVIEW_BENCH_STREAM_WORDS
#define STREAM_PASSES CONFIG_ZVIEW_BENCH_STREAM_PASSES

/* Larger than the data cache, so each pass crosses the bus a probe reads. */
static volatile uint32_t stream_buf[STREAM_WORDS];
static volatile uint32_t stream_sink;

static void do_fixed_work(void)
{
	uint32_t acc = 1U;

	for (int pass = 0; pass < STREAM_PASSES; pass++) {
		for (size_t i = 0; i < STREAM_WORDS; i++) {
			acc += stream_buf[i];
			stream_buf[i] = acc;
		}
	}
	stream_sink = acc;
}

static void metronome(void *p1, void *p2, void *p3)
{
	ARG_UNUSED(p1);
	ARG_UNUSED(p2);
	ARG_UNUSED(p3);

	for (size_t i = 0; i < STREAM_WORDS; i++) {
		stream_buf[i] = (uint32_t)i;
	}

	/* Warm-up, discarded. */
	do_fixed_work();

	int64_t next = k_uptime_ticks();
	const int64_t period_ticks = k_ms_to_ticks_ceil64(PERIOD_MS);

	while (1) {
		timing_t t0 = timing_counter_get();
		toggle_set(1);

		do_fixed_work();

		toggle_set(0);
		timing_t t1 = timing_counter_get();

		ring_record((uint32_t)timing_cycles_get(&t0, &t1));

		next += period_ticks;
		k_sleep(K_TIMEOUT_ABS_TICKS(next));
	}
}

K_THREAD_DEFINE(metro_id, METRO_STACK, metronome, NULL, NULL, NULL, METRO_PRIO, 0,
		BENCH_START_DELAY_MS);

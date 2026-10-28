/*
 * Copyright (c) 2026 Paulo Santos (@wkhadgar)
 * SPDX-License-Identifier: Apache-2.0
 *
 * Steady-state mode: a metronome thread on an absolute deadline, for measuring
 * a probe's timing perturbation.
 */

#include <stddef.h>
#include <stdint.h>
#include <string.h>

#include <zephyr/kernel.h>
#include <zephyr/linker/section_tags.h>
#include <zephyr/timing/timing.h>

#if defined(CONFIG_CORTEX_M_DWT)
#include <cmsis_core.h>
#endif

#include "bench.h"

#define METRO_STACK   2048
#define METRO_PRIO    7
#define PERIOD_MS     CONFIG_ZVIEW_BENCH_PERIOD_MS
#define STREAM_WORDS  CONFIG_ZVIEW_BENCH_STREAM_WORDS
#define STREAM_PASSES CONFIG_ZVIEW_BENCH_STREAM_PASSES
#define RUN_MS        CONFIG_ZVIEW_BENCH_RUN_MS

/*
 * Each period's work window, and the time from the start of the previous
 * window to the start of this one, in timing cycles. No-init, so a probe
 * reading these never aliases the measured state; a zero window is never
 * recorded, so zero marks a slot not yet written.
 */
#define BENCH_RING_LEN 1024U
uint32_t bench_period_cycles[BENCH_RING_LEN] __noinit;
uint32_t bench_start_cycles[BENCH_RING_LEN] __noinit;
uint32_t bench_period_head __noinit;

/* The host sets it, through a probe write, to end the run before reading the ring. */
volatile uint32_t bench_stop;

/* Larger than the data cache, so each pass crosses the bus a probe reads. */
static volatile uint32_t stream_buf[STREAM_WORDS];
static volatile uint32_t stream_sink;

static void ring_record(uint32_t window, uint32_t start_to_start)
{
	bench_period_cycles[bench_period_head] = window;
	bench_start_cycles[bench_period_head] = start_to_start;
	bench_period_head = (bench_period_head + 1U) % BENCH_RING_LEN;
}

/*
 * pyOCD clears DEMCR when it closes a session, and the DWT cycle counter stops
 * with TRCENA. Zephyr sets it only at boot, so the metronome sets it again
 * before every window.
 */
static void trace_enable(void)
{
#if defined(CONFIG_CORTEX_M_DWT)
	DCB->DEMCR |= DCB_DEMCR_TRCENA_Msk;
	DWT->CTRL |= DWT_CTRL_CYCCNTENA_Msk;
#endif
}

static bool run_over(void)
{
	return bench_stop != 0U || (RUN_MS > 0 && k_uptime_get() >= RUN_MS);
}

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

	bench_period_head = 0U;
	memset(bench_period_cycles, 0, sizeof(bench_period_cycles));
	memset(bench_start_cycles, 0, sizeof(bench_start_cycles));

	for (size_t i = 0; i < STREAM_WORDS; i++) {
		stream_buf[i] = (uint32_t)i;
	}

	/* Warm-up, discarded. */
	do_fixed_work();

	int64_t next = k_uptime_ticks();
	const int64_t period_ticks = k_ms_to_ticks_ceil64(PERIOD_MS);
	timing_t prev_t0 = 0;
	bool have_prev = false;

	while (!run_over()) {
		trace_enable();

		timing_t t0 = timing_counter_get();
		toggle_set(1);

		do_fixed_work();

		toggle_set(0);
		timing_t t1 = timing_counter_get();

		/* The 32-bit truncation keeps both differences right across a counter wrap. */
		uint32_t window = (uint32_t)timing_cycles_get(&t0, &t1);
		uint32_t start_to_start = have_prev ? (uint32_t)timing_cycles_get(&prev_t0, &t0) : 0U;

		/* A zero window means the counter stood still, so there is nothing to record. */
		if (window != 0U) {
			ring_record(window, start_to_start);
		}
		prev_t0 = t0;
		have_prev = true;

		next += period_ticks;
		k_sleep(K_TIMEOUT_ABS_TICKS(next));
	}
}

K_THREAD_DEFINE(metro_id, METRO_STACK, metronome, NULL, NULL, NULL, METRO_PRIO, 0,
		BENCH_START_DELAY_MS);

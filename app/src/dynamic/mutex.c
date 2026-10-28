/*
 * Copyright (c) 2026 Paulo Santos (@wkhadgar)
 * SPDX-License-Identifier: Apache-2.0
 *
 * A mutex held for long stretches, with a second thread queueing on it. The
 * owner logs the start and end of each hold, the ground truth of the sampling
 * fidelity experiment.
 */

#include <stdint.h>
#include <string.h>

#include <zephyr/kernel.h>
#include <zephyr/linker/section_tags.h>
#include <zephyr/timing/timing.h>

#include "bench.h"
#include "dynamic.h"

#define LOCK_HOLD_MS 600
#define LOCK_IDLE_MS 900
#define LOCK_WAIT_MS 1100

K_MUTEX_DEFINE(bench_lock);

/*
 * The owner's holds, in timing cycles: the counter the kernel stamps on each
 * thread's usage, so a recording's frames line up with the holds. No-init, so
 * a probe reading it never aliases the measured state; a zero end marks a hold
 * in progress or a slot not yet written. 512 holds cover 12.8 min.
 */
#define BENCH_HOLD_LEN 512U
struct bench_hold {
	uint32_t start;
	uint32_t end;
};
struct bench_hold bench_holds[BENCH_HOLD_LEN] __noinit;
uint32_t bench_hold_head __noinit;

static void lock_owner_thread(void *p1, void *p2, void *p3)
{
	ARG_UNUSED(p1);
	ARG_UNUSED(p2);
	ARG_UNUSED(p3);

	force_stack_watermark(1);

	bench_hold_head = 0U;
	memset(bench_holds, 0, sizeof(bench_holds));

	while (1) {
		struct bench_hold *hold = &bench_holds[bench_hold_head];

		k_mutex_lock(&bench_lock, K_FOREVER);
		hold->end = 0U;
		hold->start = (uint32_t)timing_counter_get();
		k_msleep(LOCK_HOLD_MS);
		hold->end = (uint32_t)timing_counter_get();
		k_mutex_unlock(&bench_lock);

		bench_hold_head = (bench_hold_head + 1U) % BENCH_HOLD_LEN;
		k_msleep(LOCK_IDLE_MS);
	}
}

/* Its period is not a multiple of the owner's, so it drifts across the hold. */
static void lock_waiter_thread(void *p1, void *p2, void *p3)
{
	ARG_UNUSED(p1);
	ARG_UNUSED(p2);
	ARG_UNUSED(p3);

	force_stack_watermark(2);

	while (1) {
		k_mutex_lock(&bench_lock, K_FOREVER);
		k_mutex_unlock(&bench_lock);
		k_msleep(LOCK_WAIT_MS);
	}
}

K_THREAD_DEFINE(lock_owner_id, SYNC_STACK, lock_owner_thread, NULL, NULL, NULL, SYNC_PRIO, 0,
		BENCH_START_DELAY_MS);

K_THREAD_DEFINE(lock_waiter_id, SYNC_STACK, lock_waiter_thread, NULL, NULL, NULL, SYNC_PRIO, 0,
		BENCH_START_DELAY_MS);

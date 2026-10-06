/*
 * Copyright (c) 2026 Paulo Santos (@wkhadgar)
 * SPDX-License-Identifier: Apache-2.0
 *
 * A mutex held for long stretches, with a second thread queueing on it.
 */

#include <zephyr/kernel.h>

#include "bench.h"
#include "dynamic.h"

#define LOCK_HOLD_MS 600
#define LOCK_IDLE_MS 900
#define LOCK_WAIT_MS 1100

K_MUTEX_DEFINE(bench_lock);

static void lock_owner_thread(void *p1, void *p2, void *p3)
{
	ARG_UNUSED(p1);
	ARG_UNUSED(p2);
	ARG_UNUSED(p3);

	force_stack_watermark(1);

	while (1) {
		k_mutex_lock(&bench_lock, K_FOREVER);
		k_msleep(LOCK_HOLD_MS);
		k_mutex_unlock(&bench_lock);
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

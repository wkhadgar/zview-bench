/*
 * Copyright (c) 2026 Paulo Santos (@wkhadgar)
 * SPDX-License-Identifier: Apache-2.0
 *
 * A periodic timer feeding a work queue from its expiry, and a one-shot timer
 * that keeps being re-armed.
 */

#include <zephyr/kernel.h>

#include "bench.h"
#include "dynamic.h"

#define TICK_PERIOD_MS  250
#define ONESHOT_ARM_MS  3000
#define ONESHOT_IDLE_MS 2000
#define WORKQ_STACK     768
#define WORKQ_PRIO      6
#define WORK_HOLD_MS    120

static void tick_expiry(struct k_timer *timer);

K_TIMER_DEFINE(bench_tick, tick_expiry, NULL);
K_TIMER_DEFINE(bench_oneshot, NULL, NULL);

K_THREAD_STACK_DEFINE(bench_workq_stack, WORKQ_STACK);
static struct k_work_q bench_workq;
static struct k_work tick_work;
static struct k_work trail_work;

static void work_handler(struct k_work *work)
{
	ARG_UNUSED(work);

	k_msleep(WORK_HOLD_MS);
}

/* Runs in ISR context, so submitting is all it does. */
static void tick_expiry(struct k_timer *timer)
{
	ARG_UNUSED(timer);

	k_work_submit_to_queue(&bench_workq, &tick_work);
	k_work_submit_to_queue(&bench_workq, &trail_work);
}

static void timer_thread(void *p1, void *p2, void *p3)
{
	ARG_UNUSED(p1);
	ARG_UNUSED(p2);
	ARG_UNUSED(p3);

	k_work_queue_start(&bench_workq, bench_workq_stack,
			   K_THREAD_STACK_SIZEOF(bench_workq_stack), WORKQ_PRIO,
			   &(struct k_work_queue_config){.name = "bench_workq"});
	k_work_init(&tick_work, work_handler);
	k_work_init(&trail_work, work_handler);

	k_timer_start(&bench_tick, K_MSEC(TICK_PERIOD_MS), K_MSEC(TICK_PERIOD_MS));

	while (1) {
		k_timer_start(&bench_oneshot, K_MSEC(ONESHOT_ARM_MS), K_NO_WAIT);
		k_msleep(ONESHOT_ARM_MS + ONESHOT_IDLE_MS);
	}
}

K_THREAD_DEFINE(timer_id, SYNC_STACK, timer_thread, NULL, NULL, NULL, SYNC_PRIO, 0,
		BENCH_START_DELAY_MS);

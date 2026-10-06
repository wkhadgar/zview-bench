/*
 * Copyright (c) 2026 Paulo Santos (@wkhadgar)
 * SPDX-License-Identifier: Apache-2.0
 *
 * Two semaphores: bench_slots, whose count sweeps from empty to its limit, and
 * bench_gate, with threads parked on its wait queue.
 */

#include <zephyr/kernel.h>

#include "bench.h"
#include "dynamic.h"

#define SEM_LIMIT    4
#define SEM_GIVE_MS  500
#define SEM_DRAIN_MS 3500
#define GATE_OPEN_MS 2500

K_SEM_DEFINE(bench_slots, 0, SEM_LIMIT);
K_SEM_DEFINE(bench_gate, 0, 1);

static void sem_giver_thread(void *p1, void *p2, void *p3)
{
	ARG_UNUSED(p1);
	ARG_UNUSED(p2);
	ARG_UNUSED(p3);

	while (1) {
		k_sem_give(&bench_slots);
		k_msleep(SEM_GIVE_MS);
	}
}

/* Takes one more than the limit, so it drains the count and then waits. */
static void sem_burst_thread(void *p1, void *p2, void *p3)
{
	ARG_UNUSED(p1);
	ARG_UNUSED(p2);
	ARG_UNUSED(p3);

	force_stack_watermark(1);

	while (1) {
		k_msleep(SEM_DRAIN_MS);

		for (int taken = 0; taken < SEM_LIMIT + 1; taken++) {
			k_sem_take(&bench_slots, K_FOREVER);
		}
	}
}

K_THREAD_DEFINE(sem_giver_id, SYNC_STACK, sem_giver_thread, NULL, NULL, NULL, SYNC_PRIO, 0,
		BENCH_START_DELAY_MS);

K_THREAD_DEFINE(sem_burst_id, SYNC_STACK, sem_burst_thread, NULL, NULL, NULL, SYNC_PRIO, 0,
		BENCH_START_DELAY_MS);

static void gate_keeper_thread(void *p1, void *p2, void *p3)
{
	ARG_UNUSED(p1);
	ARG_UNUSED(p2);
	ARG_UNUSED(p3);

	force_stack_watermark(2);

	while (1) {
		k_msleep(GATE_OPEN_MS);
		k_sem_give(&bench_gate);
	}
}

/* Two of these park on the gate, and each opening lets one through. */
static void gate_waiter_thread(void *p1, void *p2, void *p3)
{
	ARG_UNUSED(p1);
	ARG_UNUSED(p2);
	ARG_UNUSED(p3);

	while (1) {
		k_sem_take(&bench_gate, K_FOREVER);
	}
}

K_THREAD_DEFINE(gate_keeper_id, SYNC_STACK, gate_keeper_thread, NULL, NULL, NULL, SYNC_PRIO, 0,
		BENCH_START_DELAY_MS);

K_THREAD_DEFINE(gate_waiter_a_id, SYNC_STACK, gate_waiter_thread, NULL, NULL, NULL, SYNC_PRIO, 0,
		BENCH_START_DELAY_MS);

K_THREAD_DEFINE(gate_waiter_b_id, SYNC_STACK, gate_waiter_thread, NULL, NULL, NULL, SYNC_PRIO, 0,
		BENCH_START_DELAY_MS);

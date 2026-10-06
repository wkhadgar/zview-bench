/*
 * Copyright (c) 2026 Paulo Santos (@wkhadgar)
 * SPDX-License-Identifier: Apache-2.0
 *
 * A message queue filled faster than it drains, so it sits full with the
 * sender waiting, then empties in one burst.
 */

#include <stdint.h>

#include <zephyr/kernel.h>

#include "bench.h"
#include "dynamic.h"

#define MSGQ_CAPACITY 8
#define MSGQ_PUT_MS   500
#define MSGQ_DRAIN_MS 5000

K_MSGQ_DEFINE(bench_q, sizeof(uint32_t), MSGQ_CAPACITY, 4);

static void msgq_tx_thread(void *p1, void *p2, void *p3)
{
	ARG_UNUSED(p1);
	ARG_UNUSED(p2);
	ARG_UNUSED(p3);

	uint32_t seq = 0;

	force_stack_watermark(1);

	while (1) {
		(void)k_msgq_put(&bench_q, &seq, K_FOREVER);
		seq++;
		k_msleep(MSGQ_PUT_MS);
	}
}

static void msgq_rx_thread(void *p1, void *p2, void *p3)
{
	ARG_UNUSED(p1);
	ARG_UNUSED(p2);
	ARG_UNUSED(p3);

	uint32_t msg;

	force_stack_watermark(2);

	while (1) {
		k_msleep(MSGQ_DRAIN_MS);

		for (int taken = 0; taken <= MSGQ_CAPACITY; taken++) {
			(void)k_msgq_get(&bench_q, &msg, K_FOREVER);
		}
	}
}

K_THREAD_DEFINE(msgq_tx_id, SYNC_STACK, msgq_tx_thread, NULL, NULL, NULL, SYNC_PRIO, 0,
		BENCH_START_DELAY_MS);
K_THREAD_DEFINE(msgq_rx_id, SYNC_STACK, msgq_rx_thread, NULL, NULL, NULL, SYNC_PRIO, 0,
		BENCH_START_DELAY_MS);

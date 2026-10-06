/*
 * Copyright (c) 2026 Paulo Santos (@wkhadgar)
 * SPDX-License-Identifier: Apache-2.0
 *
 * A heap kept fragmented, and a thread waiting on it for a run it rarely has.
 */

#include <zephyr/kernel.h>

#include "bench.h"
#include "dynamic.h"

#define FRAG_STACK      1024
#define HEAP_SIZE       2048
#define ALLOCS_COUNT    128
#define ALLOC_PERIOD_MS 20
#define ALLOC_SIZE      ((HEAP_SIZE / ALLOCS_COUNT) - 8)

K_HEAP_DEFINE(bench_heap, HEAP_SIZE + 72);

/* Frees every other block, so no two frees coalesce. */
static void frag_thread(void *p1, void *p2, void *p3)
{
	ARG_UNUSED(p1);
	ARG_UNUSED(p2);
	ARG_UNUSED(p3);

	void *ptrs[ALLOCS_COUNT] = {0};

	while (1) {
		for (int i = 0; i < ALLOCS_COUNT; i++) {
			ptrs[i] = k_heap_alloc(&bench_heap, ALLOC_SIZE, K_NO_WAIT);
			k_msleep(ALLOC_PERIOD_MS / 2);
		}
		for (int i = 0; i < ALLOCS_COUNT; i += 2) {
			if (ptrs[i] != NULL) {
				k_heap_free(&bench_heap, ptrs[i]);
				ptrs[i] = NULL;
				k_msleep(ALLOC_PERIOD_MS);
			}
		}
		k_msleep(2000);
		for (int i = 0; i < ALLOCS_COUNT; i++) {
			if (ptrs[i] != NULL) {
				k_heap_free(&bench_heap, ptrs[i]);
				ptrs[i] = NULL;
			}
		}
	}
}

K_THREAD_DEFINE(frag_id, FRAG_STACK, frag_thread, NULL, NULL, NULL, WORKER_PRIO, 0,
		BENCH_START_DELAY_MS);

#define HEAP_WAIT_STACK   512
#define HEAP_WAIT_SIZE    256
#define HEAP_WAIT_MS      1500
#define HEAP_WAIT_HOLD_MS 400
#define HEAP_WAIT_IDLE_MS 900

/* Asks for a run the checkerboard rarely leaves free, so the request waits. */
static void heap_waiter_thread(void *p1, void *p2, void *p3)
{
	ARG_UNUSED(p1);
	ARG_UNUSED(p2);
	ARG_UNUSED(p3);

	while (1) {
		void *block = k_heap_alloc(&bench_heap, HEAP_WAIT_SIZE, K_MSEC(HEAP_WAIT_MS));

		if (block != NULL) {
			k_msleep(HEAP_WAIT_HOLD_MS);
			k_heap_free(&bench_heap, block);
		}

		k_msleep(HEAP_WAIT_IDLE_MS);
	}
}

K_THREAD_DEFINE(heap_waiter_id, HEAP_WAIT_STACK, heap_waiter_thread, NULL, NULL, NULL, WORKER_PRIO,
		0, BENCH_START_DELAY_MS);

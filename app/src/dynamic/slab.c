/*
 * Copyright (c) 2026 Paulo Santos (@wkhadgar)
 * SPDX-License-Identifier: Apache-2.0
 *
 * A memory slab taken one block at a time to exhaustion, then freed at once.
 */

#include <zephyr/kernel.h>

#include "bench.h"
#include "dynamic.h"

#define SLAB_BLOCKS     8
#define SLAB_BLOCK_SIZE 64
#define SLAB_STEP_MS    400
#define SLAB_HOLD_MS    300
#define SLAB_FREE_MS    2500

K_MEM_SLAB_DEFINE(bench_slab, SLAB_BLOCK_SIZE, SLAB_BLOCKS, 4);

static void slab_thread(void *p1, void *p2, void *p3)
{
	ARG_UNUSED(p1);
	ARG_UNUSED(p2);
	ARG_UNUSED(p3);

	void *blocks[SLAB_BLOCKS] = {0};

	force_stack_watermark(1);

	while (1) {
		for (int i = 0; i < SLAB_BLOCKS; i++) {
			if (k_mem_slab_alloc(&bench_slab, &blocks[i], K_FOREVER) != 0) {
				blocks[i] = NULL;
			}
			k_msleep(SLAB_STEP_MS);
		}

		k_msleep(SLAB_HOLD_MS);

		for (int i = 0; i < SLAB_BLOCKS; i++) {
			if (blocks[i] != NULL) {
				k_mem_slab_free(&bench_slab, blocks[i]);
				blocks[i] = NULL;
			}
		}

		k_msleep(SLAB_FREE_MS);
	}
}

K_THREAD_DEFINE(slab_id, SYNC_STACK, slab_thread, NULL, NULL, NULL, SYNC_PRIO, 0,
		BENCH_START_DELAY_MS);

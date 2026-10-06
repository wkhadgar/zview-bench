/*
 * Copyright (c) 2026 Paulo Santos (@wkhadgar)
 * SPDX-License-Identifier: Apache-2.0
 *
 * CPU load that steps through a fixed set of duty cycles.
 */

#include <stdint.h>

#include <zephyr/kernel.h>
#include <zephyr/sys/util.h>

#include "bench.h"
#include "dynamic.h"

#define LOAD_STACK     1024
#define LOAD_PERIOD_MS 100
#define LOAD_STEP_MS   2000

static const uint8_t load_steps[] = {10, 35, 70, 35};

static void load_thread(void *p1, void *p2, void *p3)
{
	ARG_UNUSED(p1);
	ARG_UNUSED(p2);
	ARG_UNUSED(p3);

	force_stack_watermark(2);

	while (1) {
		for (size_t step = 0; step < ARRAY_SIZE(load_steps); step++) {
			const uint32_t percent = load_steps[step];
			const uint32_t busy_us = (LOAD_PERIOD_MS * 1000U * percent) / 100U;
			const uint32_t sleep_ms =
				LOAD_PERIOD_MS - (LOAD_PERIOD_MS * percent / 100U);

			for (uint32_t held = 0; held < LOAD_STEP_MS; held += LOAD_PERIOD_MS) {
				k_busy_wait(busy_us);
				k_msleep(sleep_ms);
			}
		}
	}
}

K_THREAD_DEFINE(load_id, LOAD_STACK, load_thread, NULL, NULL, NULL, WORKER_PRIO, 0,
		BENCH_START_DELAY_MS);

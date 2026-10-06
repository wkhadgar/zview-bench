/*
 * ZView reference workload.
 *
 * Copyright (c) 2026 Paulo Santos (@wkhadgar)
 * SPDX-License-Identifier: Apache-2.0
 *
 * ZVIEW_BENCH_MODE picks one of two workloads, each built from its own sources:
 *   STEADY  - steady.c, a metronome thread on an absolute deadline, for
 *             measuring a probe's timing perturbation.
 *   DYNAMIC - dynamic/, threads that keep every object ZView reads in motion.
 */

#include <zephyr/kernel.h>
#include <zephyr/sys/printk.h>

#include "bench.h"

int main(void)
{
	instrument_init();

#if defined(CONFIG_ZVIEW_BENCH_MODE_STEADY)
	printk("zview-bench: steady mode, %d ms period\n", CONFIG_ZVIEW_BENCH_PERIOD_MS);
#else
	printk("zview-bench: dynamic mode\n");
#endif

	while (1) {
		k_msleep(1000);
	}

	return 0;
}

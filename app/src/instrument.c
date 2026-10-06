/*
 * Copyright (c) 2026 Paulo Santos (@wkhadgar)
 * SPDX-License-Identifier: Apache-2.0
 */

#include <string.h>

#include <zephyr/drivers/gpio.h>
#include <zephyr/linker/section_tags.h>
#include <zephyr/timing/timing.h>

#include "bench.h"

#if HAVE_TOGGLE
const struct gpio_dt_spec bench_toggle = GPIO_DT_SPEC_GET(DT_ALIAS(led0), gpios);
#endif

uint32_t bench_period_cycles[BENCH_RING_LEN] __noinit;
uint32_t bench_period_head __noinit;

void instrument_init(void)
{
	timing_init();
	timing_start();

#if HAVE_TOGGLE
	if (gpio_is_ready_dt(&bench_toggle)) {
		gpio_pin_configure_dt(&bench_toggle, GPIO_OUTPUT_INACTIVE);
	}
#endif

	bench_period_head = 0U;
	memset(bench_period_cycles, 0, sizeof(bench_period_cycles));
}

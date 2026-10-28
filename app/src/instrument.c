/*
 * Copyright (c) 2026 Paulo Santos (@wkhadgar)
 * SPDX-License-Identifier: Apache-2.0
 */

#include <zephyr/drivers/gpio.h>
#include <zephyr/timing/timing.h>

#include "bench.h"

#if HAVE_TOGGLE
const struct gpio_dt_spec bench_toggle = GPIO_DT_SPEC_GET(DT_ALIAS(led0), gpios);
#endif

void instrument_init(void)
{
	timing_init();
	timing_start();

#if HAVE_TOGGLE
	if (gpio_is_ready_dt(&bench_toggle)) {
		gpio_pin_configure_dt(&bench_toggle, GPIO_OUTPUT_INACTIVE);
	}
#endif
}

/*
 * Copyright (c) 2026 Paulo Santos (@wkhadgar)
 * SPDX-License-Identifier: Apache-2.0
 *
 * Shared by every workload: the thread start delay, the stack watermark
 * helper and the instrumentation, an optional scope edge on led0. Each mode
 * keeps its own record for the host to read after a run: the steady mode a
 * ring of measured periods, the dynamic mode a log of mutex holds.
 */

#ifndef ZVIEW_BENCH_BENCH_H_
#define ZVIEW_BENCH_BENCH_H_

#include <stdint.h>

#include <zephyr/drivers/gpio.h>

/* main() arms the timing source before any thread reads the cycle counter. */
#define BENCH_START_DELAY_MS 10

/* Optional scope edge on led0. A board without the alias builds without it. */
#if DT_NODE_EXISTS(DT_ALIAS(led0))
#define HAVE_TOGGLE 1
extern const struct gpio_dt_spec bench_toggle;
#else
#define HAVE_TOGGLE 0
#endif

void instrument_init(void);

/* Uses depth + 1 frames of 128 bytes and more on the calling thread's stack. */
void force_stack_watermark(int depth);

static inline void toggle_set(int value)
{
#if HAVE_TOGGLE
	if (gpio_is_ready_dt(&bench_toggle)) {
		gpio_pin_set_dt(&bench_toggle, value);
	}
#else
	ARG_UNUSED(value);
#endif
}

#endif /* ZVIEW_BENCH_BENCH_H_ */

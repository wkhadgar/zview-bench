/*
 * Copyright (c) 2026 Paulo Santos (@wkhadgar)
 * SPDX-License-Identifier: Apache-2.0
 *
 * Shared by every workload: the thread start delay and the instrumentation,
 * an optional scope edge on led0 and the ring of measured periods.
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

/* No-init, so a probe reading these never aliases the measured state. */
#define BENCH_RING_LEN 1024U
extern uint32_t bench_period_cycles[BENCH_RING_LEN];
extern uint32_t bench_period_head;

void instrument_init(void);

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

static inline void ring_record(uint32_t cycles)
{
	bench_period_cycles[bench_period_head] = cycles;
	bench_period_head = (bench_period_head + 1U) % BENCH_RING_LEN;
}

#endif /* ZVIEW_BENCH_BENCH_H_ */

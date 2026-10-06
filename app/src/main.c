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
 *
 * In either mode, pressing button0 overflows main's stack on purpose.
 */

#include <errno.h>

#include <zephyr/drivers/gpio.h>
#include <zephyr/kernel.h>
#include <zephyr/sys/atomic.h>
#include <zephyr/sys/printk.h>

#include "bench.h"

/* Optional crash button. A board without the alias builds without it. */
#if DT_NODE_EXISTS(DT_ALIAS(button0))
#define HAVE_CRASH_BUTTON 1
#else
#define HAVE_CRASH_BUTTON 0
#endif

#if HAVE_CRASH_BUTTON

#define CRASH_DEPTH 8

BUILD_ASSERT((CRASH_DEPTH + 1) * 128 > CONFIG_MAIN_STACK_SIZE,
	     "button0 would no longer overflow main's stack");

static const struct gpio_dt_spec crash_button = GPIO_DT_SPEC_GET(DT_ALIAS(button0), gpios);
static struct gpio_callback crash_button_cb;
static atomic_t crash_requested;

/* ISR context, so it only latches the press; main overflows its own stack. */
static void crash_button_pressed(const struct device *port, struct gpio_callback *cb,
				 gpio_port_pins_t pins)
{
	ARG_UNUSED(port);
	ARG_UNUSED(cb);
	ARG_UNUSED(pins);

	atomic_set(&crash_requested, 1);
}

static int crash_button_init(void)
{
	int err;

	if (!gpio_is_ready_dt(&crash_button)) {
		return -ENODEV;
	}

	err = gpio_pin_configure_dt(&crash_button, GPIO_INPUT);
	if (err != 0) {
		return err;
	}

	err = gpio_pin_interrupt_configure_dt(&crash_button, GPIO_INT_EDGE_TO_ACTIVE);
	if (err != 0) {
		return err;
	}

	gpio_init_callback(&crash_button_cb, crash_button_pressed, BIT(crash_button.pin));

	return gpio_add_callback_dt(&crash_button, &crash_button_cb);
}

#endif /* HAVE_CRASH_BUTTON */

int main(void)
{
	instrument_init();

#if defined(CONFIG_ZVIEW_BENCH_MODE_STEADY)
	printk("zview-bench: steady mode, %d ms period\n", CONFIG_ZVIEW_BENCH_PERIOD_MS);
#else
	printk("zview-bench: dynamic mode\n");
#endif

#if HAVE_CRASH_BUTTON
	int err = crash_button_init();

	if (err != 0) {
		printk("zview-bench: button0 unavailable (%d)\n", err);
	}
#endif

	while (1) {
		k_msleep(1000);

#if HAVE_CRASH_BUTTON
		if (atomic_clear(&crash_requested)) {
			printk("zview-bench: button0 pressed, overflowing main's stack\n");
			force_stack_watermark(CRASH_DEPTH);
		}
#endif
	}

	return 0;
}

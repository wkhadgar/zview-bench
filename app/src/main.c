/*
 * ZView reference workload.
 *
 * Copyright (c) 2026 Paulo Santos (@wkhadgar)
 * SPDX-License-Identifier: Apache-2.0
 *
 * ZVIEW_BENCH_MODE picks one of two workloads:
 *   STEADY  - a metronome thread on an absolute deadline, for measuring a
 *             probe's timing perturbation.
 *   DYNAMIC - threads that keep every object ZView reads in motion.
 */

#include <string.h>

#include <zephyr/drivers/gpio.h>
#include <zephyr/kernel.h>
#include <zephyr/linker/section_tags.h>
#include <zephyr/sys/printk.h>
#include <zephyr/timing/timing.h>

/* main() arms the timing source before any thread reads the cycle counter. */
#define BENCH_START_DELAY_MS 10

/* Instrumentation */

/* Optional scope edge. A board without the alias builds without it. */
#if DT_NODE_EXISTS(DT_ALIAS(bench_toggle))
#define HAVE_TOGGLE 1
static const struct gpio_dt_spec bench_toggle = GPIO_DT_SPEC_GET(DT_ALIAS(bench_toggle), gpios);
#else
#define HAVE_TOGGLE 0
#endif

/* No-init, so a probe reading these never aliases the measured state. */
#define BENCH_RING_LEN 1024U
uint32_t bench_period_cycles[BENCH_RING_LEN] __noinit;
uint32_t bench_period_head __noinit;

static void instrument_init(void)
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

/* Steady-state mode */

#if defined(CONFIG_ZVIEW_BENCH_MODE_STEADY)

#define METRO_STACK   2048
#define METRO_PRIO    7
#define PERIOD_MS     CONFIG_ZVIEW_BENCH_PERIOD_MS
#define STREAM_WORDS  CONFIG_ZVIEW_BENCH_STREAM_WORDS
#define STREAM_PASSES CONFIG_ZVIEW_BENCH_STREAM_PASSES

/* Larger than the data cache, so each pass crosses the bus a probe reads. */
static volatile uint32_t stream_buf[STREAM_WORDS];
static volatile uint32_t stream_sink;

static void do_fixed_work(void)
{
	uint32_t acc = 1U;

	for (int pass = 0; pass < STREAM_PASSES; pass++) {
		for (size_t i = 0; i < STREAM_WORDS; i++) {
			acc += stream_buf[i];
			stream_buf[i] = acc;
		}
	}
	stream_sink = acc;
}

static void metronome(void *p1, void *p2, void *p3)
{
	ARG_UNUSED(p1);
	ARG_UNUSED(p2);
	ARG_UNUSED(p3);

	for (size_t i = 0; i < STREAM_WORDS; i++) {
		stream_buf[i] = (uint32_t)i;
	}

	/* Warm-up, discarded. */
	do_fixed_work();

	int64_t next = k_uptime_ticks();
	const int64_t period_ticks = k_ms_to_ticks_ceil64(PERIOD_MS);

	while (1) {
		timing_t t0 = timing_counter_get();
		toggle_set(1);

		do_fixed_work();

		toggle_set(0);
		timing_t t1 = timing_counter_get();

		ring_record((uint32_t)timing_cycles_get(&t0, &t1));

		next += period_ticks;
		k_sleep(K_TIMEOUT_ABS_TICKS(next));
	}
}

K_THREAD_DEFINE(metro_id, METRO_STACK, metronome, NULL, NULL, NULL, METRO_PRIO, 0,
		BENCH_START_DELAY_MS);

#endif /* CONFIG_ZVIEW_BENCH_MODE_STEADY */

/* Dynamic mode. Every state holds for several polling periods, so a poll can
 * read it instead of blurring into the next.
 */

#if defined(CONFIG_ZVIEW_BENCH_MODE_DYNAMIC)

#define FRAG_STACK      1024
#define LOAD_STACK      1024
#define WORKER_PRIO     7

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

#define TARGET_LOAD_PERCENT 25
#define LOAD_PERIOD_MS      100

/* Push the watermark deep once so the thread shows a non-trivial stack usage. */
static void force_stack_watermark(int depth)
{
	volatile char bloat[128];

	memset((void *)bloat, 0xBB, sizeof(bloat));
	if (depth > 0) {
		force_stack_watermark(depth - 1);
	}
}

/* Fixed duty cycle so ZView reports a stable, non-zero CPU load. */
static void load_thread(void *p1, void *p2, void *p3)
{
	ARG_UNUSED(p1);
	ARG_UNUSED(p2);
	ARG_UNUSED(p3);

	force_stack_watermark(3);

	const uint32_t busy_us = (LOAD_PERIOD_MS * 1000U * TARGET_LOAD_PERCENT) / 100U;
	const uint32_t sleep_ms = LOAD_PERIOD_MS - (LOAD_PERIOD_MS * TARGET_LOAD_PERCENT / 100U);

	while (1) {
		k_busy_wait(busy_us);
		k_msleep(sleep_ms);
	}
}

K_THREAD_DEFINE(load_id, LOAD_STACK, load_thread, NULL, NULL, NULL, WORKER_PRIO, 0,
		BENCH_START_DELAY_MS);

/* Synchronization objects. Static, so each one carries a symbol. */

/*
 * Statically defined, so both objects carry a symbol a host can resolve. The
 * lock is held, and the semaphore left drained, for longer than a typical
 * polling period.
 */
K_MUTEX_DEFINE(bench_lock);
K_SEM_DEFINE(bench_slots, 0, 4);

#define SYNC_STACK   768
#define SYNC_PRIO    7

#define LOCK_HOLD_MS 150
#define LOCK_IDLE_MS 250
#define SEM_GIVE_MS  250
#define SEM_WORK_MS  50

static void lock_owner_thread(void *p1, void *p2, void *p3)
{
	ARG_UNUSED(p1);
	ARG_UNUSED(p2);
	ARG_UNUSED(p3);

	while (1) {
		k_mutex_lock(&bench_lock, K_FOREVER);
		k_msleep(LOCK_HOLD_MS);
		k_mutex_unlock(&bench_lock);
		k_msleep(LOCK_IDLE_MS);
	}
}

/* Blocks behind the owner for as long as the lock is held. */
static void lock_waiter_thread(void *p1, void *p2, void *p3)
{
	ARG_UNUSED(p1);
	ARG_UNUSED(p2);
	ARG_UNUSED(p3);

	while (1) {
		k_mutex_lock(&bench_lock, K_FOREVER);
		k_mutex_unlock(&bench_lock);
		k_msleep(LOCK_HOLD_MS / 2);
	}
}

static void sem_giver_thread(void *p1, void *p2, void *p3)
{
	ARG_UNUSED(p1);
	ARG_UNUSED(p2);
	ARG_UNUSED(p3);

	while (1) {
		k_sem_give(&bench_slots);
		k_msleep(SEM_GIVE_MS);
	}
}

/* Two of these run against one giver, leaving the semaphore drained. */
static void sem_taker_thread(void *p1, void *p2, void *p3)
{
	ARG_UNUSED(p1);
	ARG_UNUSED(p2);
	ARG_UNUSED(p3);

	while (1) {
		k_sem_take(&bench_slots, K_FOREVER);
		k_msleep(SEM_WORK_MS);
	}
}

K_THREAD_DEFINE(lock_owner_id, SYNC_STACK, lock_owner_thread, NULL, NULL, NULL, SYNC_PRIO, 0,
		BENCH_START_DELAY_MS);

K_THREAD_DEFINE(lock_waiter_id, SYNC_STACK, lock_waiter_thread, NULL, NULL, NULL, SYNC_PRIO, 0,
		BENCH_START_DELAY_MS);

K_THREAD_DEFINE(sem_giver_id, SYNC_STACK, sem_giver_thread, NULL, NULL, NULL, SYNC_PRIO, 0,
		BENCH_START_DELAY_MS);

K_THREAD_DEFINE(sem_taker_a_id, SYNC_STACK, sem_taker_thread, NULL, NULL, NULL, SYNC_PRIO, 0,
		BENCH_START_DELAY_MS);

K_THREAD_DEFINE(sem_taker_b_id, SYNC_STACK, sem_taker_thread, NULL, NULL, NULL, SYNC_PRIO, 0,
		BENCH_START_DELAY_MS);

#endif /* CONFIG_ZVIEW_BENCH_MODE_DYNAMIC */

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

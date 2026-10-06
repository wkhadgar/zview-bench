/*
 * Copyright (c) 2026 Paulo Santos (@wkhadgar)
 * SPDX-License-Identifier: Apache-2.0
 *
 * Dynamic mode: threads that keep every object ZView reads in motion. Every
 * state holds for several polling periods, so a poll can read it instead of
 * blurring into the next. The kernel objects are defined statically, so each
 * one carries a symbol.
 */

#ifndef ZVIEW_BENCH_DYNAMIC_H_
#define ZVIEW_BENCH_DYNAMIC_H_

/* Heap and CPU load threads. */
#define WORKER_PRIO 7

/* Kernel object threads. */
#define SYNC_STACK 768
#define SYNC_PRIO  7

#endif /* ZVIEW_BENCH_DYNAMIC_H_ */

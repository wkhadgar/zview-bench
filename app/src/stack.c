/*
 * Copyright (c) 2026 Paulo Santos (@wkhadgar)
 * SPDX-License-Identifier: Apache-2.0
 */

#include <string.h>

#include "bench.h"

/* One frame per level. The buffer is read after the call, so it is not reused. */
void force_stack_watermark(int depth)
{
	volatile char bloat[128];

	memset((void *)bloat, 0xBB, sizeof(bloat));
	if (depth > 0) {
		force_stack_watermark(depth - 1);
	}

	(void)bloat[0];
}

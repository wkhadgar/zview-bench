# zview-bench

Reference Zephyr application for exercising and benchmarking
[ZView](https://github.com/wkhadgar/zview).

It serves as a controlled target that drives ZView's observation paths (threads,
stack watermarks, CPU load, heap fragmentation, and kernel objects) and as the
device under test for measuring ZView's effect on a running system.

## Layout

A T2 (application) Zephyr workspace, mirroring the upstream
[example-application](https://github.com/zephyrproject-rtos/example-application)
conventions:

```
zview-bench/
  .clang-format     # Zephyr's C style, copied so editors find it
  west.yml          # manifest: Zephyr and its HALs, the zbook board, ZView
  app/
    CMakeLists.txt  # picks the sources of the selected mode
    Kconfig
    prj.conf        # ZView observation prerequisites
    VERSION
    sample.yaml
    src/
      main.c          # arms the instrumentation, then idles; button0 overflows its stack
      bench.h         # thread start delay, led0 edge, period ring
      instrument.c
      stack.c         # stack watermark helper
      steady.c        # steady mode: the metronome
      dynamic/        # dynamic mode, one file per object family
        heap.c  load.c  mutex.c  sem.c  msgq.c  slab.c  timers.c
    boards/
      nucleo_h753zi.overlay   # moves led0 to an external probe point, names button0
      fpb_ra6e2.overlay       # names button0
      zbook_rp2350b_m33.conf  # turns off the board's SD card filesystem
```

## Getting started

```sh
west init -m https://github.com/wkhadgar/zview-bench --mr main zview-bench-workspace
cd zview-bench-workspace
west update
west build -b nucleo_h753zi zview-bench/app
west flash
```

## Targets

The primary board is the zbook P1. `led0` carries the scope edge and
`button0` overflows main's stack; the overlays name them where a board does not.

| Board | Build target | `led0` | `button0` |
| --- | --- | --- | --- |
| Nucleo-H753ZI (STM32H753ZI, Cortex-M7) | `nucleo_h753zi` | PB8, Arduino D15 | B1, PC13 |
| FPB-RA6E2 (RA6E2, Cortex-M33) | `fpb_ra6e2` | LED1, P207 | S1, P304 |
| zbook P2 (RP2350B, Cortex-M33) | `zbook@p2/rp2350b/m33` | LED0, GPIO24 | BUTTON0, GPIO23 |
| zbook P1 (RP2350B, Cortex-M33) | `zbook@p1/rp2350b/m33` | blue LED, GPIO0 | BTN_UP, GPIO22 |

The zbook's LEDs are active low, so its scope edge is inverted.

## License

Apache-2.0. Derived in part from Zephyr's `samples/basic/sys_heap`.

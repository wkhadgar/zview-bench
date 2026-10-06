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
  west.yml          # manifest: imports upstream Zephyr (cmsis_6, hal_stm32, hal_renesas)
  app/
    CMakeLists.txt  # picks the sources of the selected mode
    Kconfig
    prj.conf        # ZView observation prerequisites
    VERSION
    sample.yaml
    src/
      main.c          # arms the instrumentation, then idles
      bench.h         # thread start delay, led0 edge, period ring
      instrument.c
      steady.c        # steady mode: the metronome
      dynamic/        # dynamic mode, one file per object family
        heap.c  load.c  mutex.c  sem.c  msgq.c  slab.c  timers.c
        stack.c       # stack watermark helper shared by the threads
    boards/
      nucleo_h753zi.overlay   # moves led0 to an external probe point
```

## Getting started

```sh
west init -m https://github.com/wkhadgar/zview-bench --mr main zview-bench-workspace
cd zview-bench-workspace
west update
west build -b nucleo_h753zi zview-bench/app
west flash
```

## Target

Primary board: `nucleo_h753zi` (STM32H753ZI, Cortex-M7). The board overlay
points the `led0` alias at Arduino D15 / PB8 as an external timing reference.

## License

Apache-2.0. Derived in part from Zephyr's `samples/basic/sys_heap`.

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
  west.yml          # manifest: imports upstream Zephyr (cmsis_6, hal_stm32)
  app/
    CMakeLists.txt
    Kconfig
    prj.conf        # ZView observation prerequisites
    VERSION
    sample.yaml
    src/main.c
    boards/
      nucleo_h753zi.overlay   # external probe-point GPIO
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
exposes `bench_toggle` (Arduino D15 / PB8) as an external timing reference.

## License

Apache-2.0. Derived in part from Zephyr's `samples/basic/sys_heap`.

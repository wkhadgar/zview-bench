# Footprint measurement app

The build target for `tools/kconfig_footprint.py`, and the app the published
ZView Kconfig footprint figures were measured on.

It is Zephyr's `samples/synchronization`, vendored unchanged except for one
`K_HEAP_DEFINE` and one `K_MEM_SLAB_DEFINE`, each touched once from `main`.

## Why those two additions

Two of the options ZView can use are accounted per object rather than globally:
`CONFIG_SYS_HEAP_RUNTIME_STATS` costs per heap and
`CONFIG_MEM_SLAB_TRACE_MAX_UTILIZATION` per slab. An app that declares neither
measures both as zero, which understates the bill. Adding one of each gives them
a real object to account for.

`prj.conf` is deliberately empty: the sweep supplies every Kconfig through an
overlay, including a baseline that forces all of them off, so that nothing the
app sets can hide a cost.

## Running the sweep

```
tools/kconfig_footprint.py \
    --west-topdir ~/zephyrproject \
    --board rpi_pico2/rp2350a/m33 \
    --app tools/footprint_app
```

Figures as measured on 2026-09-13, `rpi_pico2/rp2350a/m33`, Zephyr
`c64cf28f71f`, against a baseline of 20880 B flash and 7776 B RAM:

| Option | Flash | RAM |
| --- | --- | --- |
| `CONFIG_INIT_STACKS` | +32 | 0 |
| `CONFIG_THREAD_MONITOR` | +136 | +120 |
| `CONFIG_THREAD_STACK_INFO` | +32 | +80 |
| all required | **+176** | **+160** |
| `CONFIG_THREAD_NAME` | +156 | +160 |
| `CONFIG_THREAD_RUNTIME_STATS` | +248 | +104 |
| `CONFIG_SYS_HEAP_RUNTIME_STATS` | +96 | 0 |
| `CONFIG_MEM_SLAB_TRACE_MAX_UTILIZATION` | +12 | +8 |
| all optional | **+488** | **+272** |
| everything | **+640** | **+440** |

Singles do not sum to the subtotals, because the options share code and struct
space. Quote a subtotal, not a sum.

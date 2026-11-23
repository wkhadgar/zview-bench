# SBOM of the measured firmware

SPDX 2.3 documents (`west spdx`, Zephyr v4.4.2) for the four firmware images of the measurement
campaign: zbook (`zbook@p1/rp2350b/m33`) and FPB-RA6E2 (`fpb_ra6e2`), dynamic and steady modes.
Each folder holds `app.spdx`, `zephyr.spdx`, `build.spdx` and `modules-deps.spdx`.

Generated with:

    west spdx --init -d build-sbom-<board>-<mode>
    west build -p always -b <board> zview-bench/app -d build-sbom-<board>-<mode> -- \
        -DCONFIG_ZVIEW_BENCH_MODE_<MODE>=y -DCONFIG_BUILD_OUTPUT_META=y
    west spdx -d build-sbom-<board>-<mode>

Each rebuilt `zephyr.bin` has the same SHA256 as the image used in the datasets:

| Folder | SHA256 of zephyr.bin |
| --- | --- |
| `zbook-dynamic` | `8006f3dfee906f8d78eed344482018a2a415f7d14d280c5dc775bccb3ca73814` |
| `zbook-steady` | `cd0b779372682abfb634b97a2d9838c8d0d743dda1d699db5521d3382a513feb` |
| `ra6e2-dynamic` | `e3c0d4aed8c392bfa5bcb72d6c12790e50347781564db1ed7584ab096a31583e` |
| `ra6e2-steady` | `d55bb8403cf5d63d4ad0db638088ee81ad16c9b217df1830aa5bdf624d8ff535` |

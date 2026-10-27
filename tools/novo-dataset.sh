#!/usr/bin/env bash
# Run one measurement and keep everything the thesis needs to cite it.
#
#   tools/novo-dataset.sh EXPERIMENT BOARD BACKEND [LABEL] -- COMMAND...
#
# Creates zview-bench/data/<date>-<EXPERIMENT>-<BOARD>-<BACKEND>[-<LABEL>]/, writes meta.txt
# (versions, commits, USB probes, the command line), runs COMMAND inside that directory with its
# output in run.log, and appends the exit status, the duration and the tail of ZView's own log.
# Fill in the "TO FILL" lines of meta.txt by hand (probe model and firmware, scope setup).
#
# Example (Q2, full read shape, J-Link on the FPB-RA6E2):
#   tools/novo-dataset.sh q2 fpb_ra6e2 jlink full-0.10s -- \
#     west zview record -e ../../build-ra6e2/zephyr/zephyr.elf -r jlink -t R7FA6E2BB \
#       --frequency 4M --period 0.10 --duration 140 -o rec.ndjson.gz
set -euo pipefail

ws="${ZVIEW_BENCH_WS:-$HOME/repos/zview-bench-ws}"
bench="$ws/zview-bench"

if [[ $# -lt 5 ]]; then
    sed -n '2,15p' "$0" >&2
    exit 2
fi
experiment="$1" board="$2" backend="$3"
shift 3
label=""
if [[ "$1" != "--" ]]; then
    label="-$1"
    shift
fi
[[ "$1" == "--" ]] || { echo "missing -- before the command" >&2; exit 2; }
shift

stamp="$(date +%Y%m%d-%H%M%S)"
dir="$bench/data/$stamp-$experiment-$board-$backend$label"
mkdir -p "$dir"

describe() { git -C "$1" describe --tags --always --dirty 2>/dev/null || echo "not a git tree"; }
version() { local out; out=$("$@" 2>/dev/null) || { echo "not found"; return; }; echo "${out%%$'\n'*}"; }
pyver() {
    "$ws/.venv-zview-bench/bin/python" -c "import importlib.metadata as m; print(m.version('$1'))" \
        2>/dev/null || echo "not found"
}

{
    echo "experiment: $experiment"
    echo "board: $board"
    echo "backend: $backend"
    echo "label: ${label#-}"
    echo "started: $(date --iso-8601=seconds)"
    echo "host: $(uname -srmo)"
    echo
    echo "zview: $(describe "$ws/modules/tools/zview")"
    echo "zview-bench: $(describe "$bench")"
    echo "zephyr: $(describe "$ws/zephyr")"
    for module in modules/boards/zbook modules/hal/renesas modules/hal/stm32 modules/hal/rpi_pico; do
        if [[ -d "$ws/$module" ]]; then echo "$module: $(describe "$ws/$module")"; fi
    done
    west_bin="$ws/.venv-zview-bench/bin/west"
    [[ -x "$west_bin" ]] || west_bin=west
    echo "west: $(version "$west_bin" --version)"
    echo "python: $(version "$ws/.venv-zview-bench/bin/python" --version)"
    echo "pyocd: $(pyver pyocd)"
    echo "pylink-square: $(pyver pylink-square)"
    echo "scipy: $(pyver scipy)"
    echo "statsmodels: $(pyver statsmodels)"
    if [[ -f /opt/SEGGER/JLink/libjlinkarm.so ]]; then
        echo "jlink software: $(basename "$(readlink -f /opt/SEGGER/JLink/libjlinkarm.so)")"
    fi
    echo
    echo "usb probes (lsusb, vendor:product and bcdDevice):"
    for id in 1366 2e8a 0483 045b 0d28; do
        { lsusb -d "$id:" 2>/dev/null || true; } | while read -r line; do
            bus=$(awk '{print $2}' <<<"$line") dev=$(awk '{print $4}' <<<"$line" | tr -d :)
            bcd=$({ lsusb -v -s "$bus:$dev" 2>/dev/null || true; } | awk '/bcdDevice/ && !f {print $2; f = 1}')
            echo "  $line  bcdDevice=${bcd:-unknown}"
        done
    done
    echo
    echo "TO FILL: probe model and firmware:"
    echo "TO FILL: board revision and chip revision (H753 REV_ID):"
    echo "TO FILL: SWD clock as the tool logged it:"
    echo "TO FILL: oscilloscope model, probe, timebase, trigger (Q1 only):"
    echo "TO FILL: reset before this session (yes/no):"
    echo "TO FILL: notes:"
    echo
    printf 'command:'
    printf ' %q' "$@"
    echo
} >"$dir/meta.txt"

echo "dataset: $dir"
start=$(date +%s)
set +e
(cd "$dir" && "$@") 2>&1 | tee "$dir/run.log"
status=${PIPESTATUS[0]}
set -e
{
    echo "finished: $(date --iso-8601=seconds)"
    echo "duration_s: $(( $(date +%s) - start ))"
    echo "exit_status: $status"
} >>"$dir/meta.txt"

zlog="$HOME/.cache/zview/zview.log"
if [[ -f "$zlog" ]]; then tail -n 200 "$zlog" >"$dir/zview-log-tail.txt"; fi
echo "exit status $status; fill the TO FILL lines in $dir/meta.txt"
exit "$status"

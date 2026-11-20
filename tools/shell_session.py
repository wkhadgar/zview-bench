#!/usr/bin/env python3
# Copyright (c) 2026 Paulo Santos (@wkhadgar)
#
# SPDX-License-Identifier: Apache-2.0
"""Q4 shell cross-check session, run inside a dataset directory on the shell build.

While ZView records the target at a 16 s period, the shell is asked `kernel thread list` about
once a second over the serial port, and each reply is stamped with time.perf_counter(), the clock
the recording uses. After the recording, `kernel thread stacks` and a ZView dump read the stacks
one right after the other. A 16 s window keeps each 32-bit cycle delta below one wrap at 200 MHz.

Writes rec.ndjson.gz, shell-list.jsonl (host time and text per reply), shell-stacks.txt and
dump.json. Run from the west workspace with the bench venv active.

Usage: shell_session.py ELF SERIAL_PORT
"""

import json
import subprocess
import sys
import threading
import time

import serial

ELF, PORT = sys.argv[1], sys.argv[2]
ZV = ["west", "zview"]
JL = ["-e", ELF, "-r", "jlink", "-t", "R7FA6E2BB", "--frequency", "4M"]
PROMPT = b"uart:~$ "


def command(port, cmd, timeout=5.0):
    """Send one shell command and return the reply text up to the next prompt."""
    port.reset_input_buffer()
    port.write(cmd.encode() + b"\r")
    buf = b""
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        buf += port.read(port.in_waiting or 1)
        # The echo carries one prompt; the reply ends at the next.
        if (
            buf.count(PROMPT) >= 1
            and buf.rstrip().endswith(PROMPT.rstrip())
            and cmd.encode() in buf
        ):
            break
    return buf.decode(errors="replace")


def main():
    port = serial.Serial(PORT, 115200, timeout=0.05)
    command(port, "")
    stop = threading.Event()
    replies = open("shell-list.jsonl", "w")

    def poll():
        while not stop.is_set():
            t0 = time.perf_counter()
            text = command(port, "kernel thread list")
            replies.write(
                json.dumps({"host_start": t0, "host_end": time.perf_counter(), "text": text}) + "\n"
            )
            replies.flush()
            time.sleep(max(0.0, 1.0 - (time.perf_counter() - t0)))

    worker = threading.Thread(target=poll)
    worker.start()
    time.sleep(2)
    subprocess.run(
        ZV + ["record"] + JL + ["--period", "16", "--duration", "40", "-o", "rec.ndjson.gz"],
        check=True,
    )
    stop.set()
    worker.join()
    replies.close()
    with open("shell-stacks.txt", "w") as f:
        f.write(json.dumps({"host_start": time.perf_counter()}) + "\n")
        f.write(command(port, "kernel thread stacks"))
    with open("dump.json", "w") as f:
        subprocess.run(ZV + ["dump"] + JL + ["--json"], check=True, stdout=f)
    print("shell session done")


if __name__ == "__main__":
    main()

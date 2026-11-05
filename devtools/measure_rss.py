"""
measure_rss.py -- peak resident memory (RSS) of the engine while thinking.

Spawns the target (python main.py or the packaged executable), drives it
to a 6-second midgame search via the protocol, and samples RSS every
50 ms with psutil. Reports peak and idle RSS in MB.

Usage:
    python devtools/measure_rss.py python main.py
    python devtools/measure_rss.py dist/main.exe
Dev tool only.
"""

import subprocess
import sys
import time

import psutil

MIDGAME = ["black JJ", "white JKKJ", "black ILKK", "white HHIH",
           "black GHJI", "white JGKH"]


def measure(cmd):
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE,
                            stdout=subprocess.PIPE, text=True)
    p = psutil.Process(proc.pid)
    # consume banner
    time.sleep(1.5)
    idle = p.memory_info().rss / 1e6
    for m in MIDGAME:
        proc.stdin.write(m + "\n")
    proc.stdin.write("depth 6\nnext\n")
    proc.stdin.flush()
    peak = idle
    t0 = time.time()
    while time.time() - t0 < 8.5:
        try:
            rss = p.memory_info().rss / 1e6
        except psutil.Error:
            break
        peak = max(peak, rss)
        time.sleep(0.05)
    proc.stdin.write("exit\n")
    proc.stdin.flush()
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()
    return idle, peak


if __name__ == "__main__":
    label = " ".join(sys.argv[1:])
    idle, peak = measure(sys.argv[1:])
    print(f"{label}: idle RSS {idle:.1f} MB, peak RSS during 6 s search "
          f"{peak:.1f} MB")

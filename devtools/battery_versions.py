"""
battery_versions.py -- cross-version tactical battery (guide session 5):
run v1-v4 on the SAME preset positions, same budget, and tabulate
move / time / nodes / verdict for the report.

Usage: python devtools/battery_versions.py [--depth 4]
Dev tool only.
"""

import argparse
import os
import re
import subprocess
import sys

EXES = {
    "v1": "dist/v1_main.exe",
    "v2": "dist/v2_main.exe",
    "v3": "dist/v3_main.exe",
    "v4": "dist/main.exe",
}

# (name, preset, pass-criterion description, predicate on move string)
TESTS = [
    ("W1", "black JJ white ASBS black KJLJ black MJNJ white APBP",
     "winning pair on row J", lambda mv: ("IJ" in mv) or ("OJ" in mv) or ("HJ" in mv) or ("PJ" in mv)),
    ("D1f", "black PANA white KJLJ black LAHA white MJNJ black HBFB white OJPC",
     "exact forced pair JJPJ", lambda mv: mv == "JJPJ"),
    ("D1a", "black OJPC white KJLJ black PANA white MJNJ black LAHA white SBSD",
     "contains the mark JJ", lambda mv: "JJ" in mv),
    ("W2", "black HJIJ white SASB black JJKM white PCPD black KLKK white OAOB",
     "junction KJ taken", lambda mv: "KJ" in mv),
    ("D2", "white HJIJ black SASB white JJKM black PCPD white KLKK black OAOB",
     "junction KJ occupied", lambda mv: "KJ" in mv),
]


def run(exe, preset, depth):
    cmds = ["name"] + preset.split() + [f"depth {depth}", "next", "exit"]
    # interleave correctly: tokens are colour/move pairs
    toks = preset.split()
    lines = ["name"]
    for i in range(0, len(toks), 2):
        lines.append(f"{toks[i]} {toks[i+1]}")
    lines += [f"depth {depth}", "next", "exit"]
    inp = "\n".join(lines) + "\n"
    p = subprocess.run([exe], input=inp, capture_output=True, text=True,
                       timeout=120)
    out = p.stdout
    move = ""
    m = re.findall(r"^move (\S+)", out, re.M)
    if m:
        move = m[-1]
    def num(pat):
        mm = re.search(pat, out)
        return mm.group(1) if mm else "-"
    return move, num(r"AB Time:\s*([\d.]+)"), num(r"Node:\s*(\d+)"), \
        num(r"Pruned:\s*(\d+)")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--depth", type=int, default=4)
    args = ap.parse_args()

    print(f"cross-version battery (budget {args.depth}s), "
          f"same machine, same presets")
    print(f"{'pos':4} {'ver':3} {'move':6} {'time':>7} {'nodes':>7} "
          f"{'pruned':>7}  verdict")
    for tname, preset, desc, pred in TESTS:
        for v, exe in EXES.items():
            move, t, n, pr = run(exe, preset, args.depth)
            ok = bool(move) and pred(move)
            print(f"{tname:4} {v:3} {move:6} {t:>7} {n:>7} {pr:>7}  "
                  f"{'PASS' if ok else 'FAIL'} ({desc})")
        print()


if __name__ == "__main__":
    main()

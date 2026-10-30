"""
benchmark_eval.py -- cost of static evaluation: naive full scan vs
IncrementalEvaluator (report Section 4.4).

Measures, on identical positions (defence / midgame / dense):
- naive:        evaluate_board(board) full 924-window scan, repeated
- incremental:  per-leaf cost in a search-like pattern:
                make(random pair) -> score() -> unmake, plus score() alone
- construction: IncrementalEvaluator(board) initial scan (once per search)

Usage: python devtools/benchmark_eval.py [--out results.txt]
Dev tool only.
"""

import argparse
import os
import random
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from defines import Defines, StoneMove           # noqa: E402
from tools import init_board, make_move, msg2move  # noqa: E402
from evaluation import evaluate_board, IncrementalEvaluator  # noqa: E402

POSITIONS = [
    ("defence", [("white", "JJ"), ("black", "AA"), ("white", "KJ"),
                 ("black", "AB"), ("white", "LJ"), ("white", "MJ"),
                 ("white", "NJ"), ("white", "AS")]),
    ("midgame", [("black", "JJ"), ("white", "JKKJ"), ("black", "ILKK"),
                 ("white", "HHIH"), ("black", "GHJI"), ("white", "JGKH")]),
    ("dense", [("black", "JJ"), ("white", "JKKJ"), ("black", "ILKK"),
               ("white", "HHIH"), ("black", "GHJI"), ("white", "JGKH"),
               ("black", "HIIF"), ("white", "JHIG"), ("black", "KILH"),
               ("white", "GIJF"), ("black", "FJLD"), ("white", "IKLI"),
               ("black", "JLKG"), ("white", "JEMH"), ("black", "OFJD"),
               ("white", "KFLG")]),
]

N_NAIVE = 2000
N_INCR = 2000


def build(moves):
    board = [[0] * Defines.GRID_NUM for _ in range(Defines.GRID_NUM)]
    init_board(board)
    for color, m in moves:
        make_move(board, msg2move(m),
                  Defines.BLACK if color == "black" else Defines.WHITE)
    return board


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out")
    args = ap.parse_args()

    lines = []

    def emit(s=""):
        print(s)
        lines.append(s)

    emit("evaluation cost benchmark -- " + time.strftime("%Y-%m-%d"))
    emit(f"{'position':10} {'naive us/call':>13} {'naive evals/s':>13} "
         f"{'incr score us':>13} {'incr make+score us':>19} "
         f"{'init scan ms':>12}")
    for name, moves in POSITIONS:
        board = build(moves)

        t0 = time.perf_counter()
        for _ in range(N_NAIVE):
            evaluate_board(board)
        naive_us = (time.perf_counter() - t0) / N_NAIVE * 1e6

        ev = IncrementalEvaluator(board)
        rng = random.Random(42)
        empties = [(x, y) for x in range(1, 20) for y in range(1, 20)
                   if board[x][y] == Defines.NOSTONE]

        t0 = time.perf_counter()
        for _ in range(N_INCR):
            ev.score(Defines.BLACK)
        score_us = (time.perf_counter() - t0) / N_INCR * 1e6

        mv = StoneMove()
        t0 = time.perf_counter()
        for i in range(N_INCR):
            (x1, y1), (x2, y2) = empties[(2 * i) % len(empties)], \
                empties[(2 * i + 1) % len(empties)]
            mv.positions[0].x, mv.positions[0].y = x1, y1
            mv.positions[1].x, mv.positions[1].y = x2, y2
            ev.make(mv, Defines.BLACK)
            ev.score(Defines.BLACK)
            ev.unmake(mv)
        cycle_us = (time.perf_counter() - t0) / N_INCR * 1e6

        t0 = time.perf_counter()
        IncrementalEvaluator(board)
        init_ms = (time.perf_counter() - t0) * 1e3

        emit(f"{name:10} {naive_us:13.1f} {1e6 / naive_us:13.0f} "
             f"{score_us:13.2f} {cycle_us:19.1f} {init_ms:12.1f}")

    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")


if __name__ == "__main__":
    main()

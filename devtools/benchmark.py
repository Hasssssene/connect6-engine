"""
benchmark.py -- in-process search metrics for the report (Practice 1).

Runs the SearchEngine directly (no protocol subprocess) on fixed positions
and measures: expanded nodes, pruned nodes, wall time, chosen move, score.

Matrix (per position):
  - minimax vs alpha-beta at equal depth (same move/ordering expected)
  - alpha-beta with probe ordering vs reversed (worst-case) ordering
  - iterative deepening under 4/5/6 s budgets (depth reached)

Usage:
    python devtools/benchmark.py [--out results.txt]

Dev tool only -- not part of the delivered engine.
"""

import argparse
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from defines import Defines            # noqa: E402
from tools import init_board, make_move, msg2move, move2msg  # noqa: E402
from search_engine import SearchEngine  # noqa: E402
from defines import StoneMove          # noqa: E402

# Positions: (label, [(colour, msg), ...], colour_to_move)
POSITIONS = [
    ("defence",
     [("white", "JJ"), ("black", "AA"), ("white", "KJ"), ("black", "AB"),
      ("white", "LJ"), ("white", "MJ"), ("white", "NJ"), ("white", "AS")],
     "black"),
    ("midgame",
     [("black", "JJ"), ("white", "JKKJ"), ("black", "ILKK"), ("white", "HHIH"),
      ("black", "GHJI"), ("white", "JGKH")],
     "black"),
]


def build_board(moves):
    board = [[0] * Defines.GRID_NUM for _ in range(Defines.GRID_NUM)]
    init_board(board)
    for color, m in moves:
        make_move(board, msg2move(m),
                  Defines.BLACK if color == "black" else Defines.WHITE)
    return board


def run_one(cfg, moves, color, seconds=None):
    color_id = Defines.BLACK if color == "black" else Defines.WHITE
    se = SearchEngine()
    for k, v in cfg.items():
        setattr(se, k, v)
    board = build_board(moves)
    se.before_search(board, color_id, 1)
    best = StoneMove()
    dummy = StoneMove()          # (0,0)/(0,0) -> border cell, never a win
    t0 = time.perf_counter()
    score = se.alpha_beta_search(seconds if seconds else 1,
                                 Defines.MININT, Defines.MAXINT,
                                 color_id, best, dummy)
    dt = time.perf_counter() - t0
    msg = move2msg(best)
    return dict(nodes=se.m_total_nodes, pruned=se.m_pruned_nodes,
                depth=se.m_reached_depth, time=dt, score=score, move=msg)


FIXED_CONFIGS = [
    # label, ITERATIVE, USE_ALPHABETA, ORDER_MOVES, FIXED_DEPTH
    ("minimax d2",          False, False, True,  2),
    ("minimax d3",          False, False, True,  3),
    ("alphabeta d2",        False, True,  True,  2),
    ("alphabeta d3",        False, True,  True,  3),
    ("alphabeta d4",        False, True,  True,  4),
    ("alphabeta d2 no-ord", False, True,  False, 2),
    ("alphabeta d3 no-ord", False, True,  False, 3),
]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", help="write results to this file as well")
    args = ap.parse_args()

    lines = []

    def emit(s=""):
        print(s)
        lines.append(s)

    emit("v2 search benchmark (in-process) -- " + time.strftime("%Y-%m-%d %H:%M"))
    emit("positions: " + ", ".join(f"{n} ({c} to move)" for n, _, c in POSITIONS))
    emit()

    # --- fixed-depth matrix -------------------------------------------------
    emit(f"{'position':10} {'config':20} {'nodes':>8} {'pruned':>8} "
         f"{'time s':>8} {'score':>8}  move")
    for pname, moves, color in POSITIONS:
        for label, it, ab, order, depth in FIXED_CONFIGS:
            cfg = dict(ITERATIVE=it, USE_ALPHABETA=ab, ORDER_MOVES=order,
                       FIXED_DEPTH=depth)
            r = run_one(cfg, moves, color)
            emit(f"{pname:10} {label:20} {r['nodes']:8d} {r['pruned']:8d} "
                 f"{r['time']:8.2f} {r['score']:8.0f}  {r['move']}")
        emit()

    # --- iterative deepening budgets ---------------------------------------
    emit(f"{'position':10} {'budget':>8} {'depth':>6} {'nodes':>8} {'pruned':>8} "
         f"{'time s':>8}  move")
    for pname, moves, color in POSITIONS:
        for budget in (4, 5, 6):
            r = run_one(dict(ITERATIVE=True, USE_ALPHABETA=True, ORDER_MOVES=True),
                        moves, color, seconds=budget)
            emit(f"{pname:10} {budget:7d}s {r['depth']:6d} {r['nodes']:8d} "
                 f"{r['pruned']:8d} {r['time']:8.2f}  {r['move']}")
        emit()

    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")


if __name__ == "__main__":
    main()

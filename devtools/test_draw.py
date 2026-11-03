"""
test_draw.py -- draw-detection evidence (report Session 1 / guide item).

Fills the 19x19 board with a 2x2-block checkerboard
(colour = ((x-1)//2 + (y-1)//2) % 2), a pattern in which no line of six
same-colour stones can exist (max run in any row/column/diagonal is 2),
then verifies:
  1. no six-in-a-row exists for either colour (win checks negative)
  2. IncrementalEvaluator.is_full() == True (draw condition)
  3. the search, asked to move on the full board, returns the draw score 0
     and generates no candidate moves

Usage: python devtools/test_draw.py
Dev tool only.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from defines import Defines, StoneMove             # noqa: E402
from tools import init_board, is_win_by_premove    # noqa: E402
from evaluation import IncrementalEvaluator        # noqa: E402
from search_engine import SearchEngine             # noqa: E402


def main():
    board = [[0] * Defines.GRID_NUM for _ in range(Defines.GRID_NUM)]
    init_board(board)
    last = {}
    for x in range(1, 20):
        for y in range(1, 20):
            # period-5 stripe pattern: arg steps +1 (columns), +2 (rows),
            # +3/-1 (diagonals) mod 5 -> same-colour runs of at most 2 in
            # every direction (2x2 checkerboards fail: monochrome diagonals)
            color = 1 if ((x - 1) + 2 * (y - 1)) % 5 < 2 else 2
            board[x][y] = color
            last[color] = (x, y)

    ok = True

    # 1) no six-in-a-row for either colour
    for color, (x, y) in last.items():
        mv = StoneMove()
        mv.positions[0].x = mv.positions[1].x = x
        mv.positions[0].y = mv.positions[1].y = y
        win = is_win_by_premove(board, mv)
        print(("PASS" if not win else "FAIL"),
              f"- no six-in-a-row for colour {color}")
        ok &= not win

    # 2) full-board detection
    ev = IncrementalEvaluator(board)
    full = ev.is_full()
    print(("PASS" if full else "FAIL"),
          f"- is_full() == True (stones={ev.m_stones}/361)")
    ok &= full

    # 3) search on a full board returns the draw score and no move
    se = SearchEngine()
    se.before_search(board, Defines.BLACK, 1)
    best = StoneMove()
    dummy = StoneMove()
    score = se.alpha_beta_search(1, Defines.MININT, Defines.MAXINT,
                                 Defines.BLACK, best, dummy)
    no_cand = (score == 0 and se.m_total_nodes == 0)
    print(("PASS" if no_cand else "FAIL"),
          f"- search on full board: score={score}, nodes={se.m_total_nodes} "
          "(draw score, no candidates)")
    ok &= no_cand

    print("\nALL PASS" if ok else "\nSOME TESTS FAILED")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())

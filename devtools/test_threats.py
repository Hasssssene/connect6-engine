"""
test_threats.py -- unit tests for threats.py and the v3 IncrementalEvaluator.

Checks, against hand-derived cases from Wu & Huang's definitions:
- threat counting on a line (4-run, 5-run, two separated runs, blocked line)
- win_empties of threat windows (immediate winning pairs)
- incremental evaluator consistency (feature + legacy scores) under
  make/unmake of random pairs vs. a fresh re-scan

Usage: python devtools/test_threats.py
"""

import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from defines import Defines                     # noqa: E402
from tools import init_board                    # noqa: E402
from threats import LINES, LINES_THROUGH, line_threat_info, threat_scan  # noqa: E402
from evaluation import IncrementalEvaluator, evaluate_board  # noqa: E402

B, W, N = Defines.BLACK, Defines.WHITE, Defines.NOSTONE


def board_with(black=(), white=()):
    board = [[N] * Defines.GRID_NUM for _ in range(Defines.GRID_NUM)]
    init_board(board)
    for x, y in black:
        board[x][y] = B
    for x, y in white:
        board[x][y] = W
    return board


def check(name, cond):
    print(("PASS" if cond else "FAIL"), "-", name)
    return cond


def main():
    ok = True
    print("lines:", len(LINES), "(expect 92: 19 rows + 19 cols + 27 + 27 diag)")
    ok &= check("line count", len(LINES) == 92)

    # --- line threat counting ------------------------------------------------
    # NOTE on expectations (Definition 1): a NAKED 4-run in open space spans
    # two 6-windows (cells left of the run / right of it), so t = 2 -- the
    # defender must occupy both marked squares. Same for an open 5-run
    # (block both ends = our IJOJ double-block behaviour).
    board = board_with(black=[(5, y) for y in (5, 6, 7, 8)])
    row = next(l for l in LINES if l == [(5, y) for y in range(1, 20)])
    t, marked, we = line_threat_info(board, B, row)
    ok &= check("open 4-run: two threats (both flanks)", t == 2)
    ok &= check("open 4-run: two marked squares", len(marked) == 2)
    ok &= check("open 4-run: win pair fills left window",
                we == [(5, 3), (5, 4)])

    # 5-run: also two threats (left window y3..8, right window y5..10)
    board = board_with(black=[(5, y) for y in (5, 6, 7, 8, 9)])
    t, marked, we = line_threat_info(board, B, row)
    ok &= check("open 5-run: two threats", t == 2)

    # two 4-runs separated by 5 empty cells: window marking merges the
    # shared flank -> 3 threats (defence = {y6, y10, y16}; 3 independent
    # winning pairs = an UNDEFENDABLE attack per the paper's >=3 rule)
    board = board_with(black=[(5, y) for y in (2, 3, 4, 5, 11, 12, 13, 14)])
    t, marked, we = line_threat_info(board, B, row)
    ok &= check("two open 4-runs (5 apart): three threats", t == 3)
    ok &= check("two open 4-runs (5 apart): three marks", len(marked) == 3)

    # blocked line: white stone inside the run -> no threats
    board = board_with(black=[(5, y) for y in (5, 6, 7, 9)],
                       white=[(5, 8)])
    t, _, we = line_threat_info(board, B, row)
    ok &= check("blocked line: no threat", t == 0 and we is None)

    # gap pattern BBBB.B: two threats; the gap cell completes six alone
    board = board_with(black=[(5, y) for y in (5, 6, 7, 8, 10)])
    t, marked, we = line_threat_info(board, B, row)
    ok &= check("gap pattern BBBB.B: two threats", t == 2)
    ok &= check("gap pattern: gap is a defence mark", (5, 9) in marked)

    # --- whole-board scan + defence squares ----------------------------------
    board = board_with(black=[(5, y) for y in (5, 6, 7, 8)],          # black open 4-run
                       white=[(10, 10), (10, 11), (10, 12), (10, 13)])  # white open 4-run
    Tb, sqb, web = threat_scan(board, B)
    Tw, sqw, wew = threat_scan(board, W)
    ok &= check("scan: open 4-runs give T=2 each", Tb == 2 and Tw == 2)
    ok &= check("scan: win empties for both", web is not None and wew is not None)

    # --- incremental evaluator consistency -----------------------------------
    rng = random.Random(42)
    for trial in range(20):
        board = board_with()
        empties = [(x, y) for x in range(1, 20) for y in range(1, 20)]
        rng.shuffle(empties)
        for _ in range(rng.randint(4, 30)):
            x, y = empties.pop()
            board[x][y] = rng.choice((B, W))
        ev = IncrementalEvaluator(board)
        fresh_feat = ev.score_black()
        fresh_legacy = ev.legacy_score_black()
        if not check(f"trial {trial}: initial scores match naive scan",
                     abs(ev.score_black() - (ev.m_bfeat - ev.m_wfeat)) < 1e-9 and
                     ev.legacy_score_black() == evaluate_board(board)):
            ok = False
            break
        # random make/unmake pairs
        for _ in range(30):
            if len(empties) < 2:
                break
            c1, c2 = empties[-1], empties[-2]
            from defines import StoneMove
            mv = StoneMove()
            mv.positions[0].x, mv.positions[0].y = c1
            mv.positions[1].x, mv.positions[1].y = c2
            color = rng.choice((B, W))
            ev.make(mv, color)
            empties.pop(), empties.pop()
            ref = IncrementalEvaluator(board)
            if abs(ev.score_black() - ref.score_black()) > 1e-6 or \
               ev.legacy_score_black() != ref.legacy_score_black() or \
               ev.is_full() != ref.is_full():
                ok &= check(f"trial {trial}: incremental == fresh after make", False)
                break
            ev.unmake(mv)
            empties.extend((c1, c2))
            ref = IncrementalEvaluator(board)
            if abs(ev.score_black() - ref.score_black()) > 1e-6 or \
               ev.legacy_score_black() != ref.legacy_score_black():
                ok &= check(f"trial {trial}: incremental == fresh after unmake", False)
                break
        else:
            continue
        break
    else:
        ok &= check("20 randomized make/unmake trials: all consistent", True)

    print("\nALL PASS" if ok else "\nSOME TESTS FAILED")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())

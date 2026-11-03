"""
preset_check.py -- validate a headless_match --start preset position.

Checks (the mistakes this tool exists to prevent):
  - every move decodes and is legal (distinct cells, empty cells, A-S range)
  - alternation/parity -> reports which colour moves next
  - threat state of BOTH colours (exact scan): a battery preset usually
    wants T=0 for both sides unless a threat is the point of the test
  - accidental pre-existing wins

Usage:
    python devtools/preset_check.py "black KSKR white PISA ..."
Dev tool only.
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from defines import Defines                    # noqa: E402
from tools import init_board, make_move, msg2move  # noqa: E402
from threats import threat_scan                # noqa: E402


def check(preset):
    board = [[0] * Defines.GRID_NUM for _ in range(Defines.GRID_NUM)]
    init_board(board)
    moves = 0
    toks = preset.split()
    if len(toks) % 2:
        print("MALFORMED: odd number of tokens")
        return 1
    for i in range(0, len(toks), 2):
        color_tok, cmd = toks[i], toks[i + 1]
        color = Defines.BLACK if color_tok == "black" else Defines.WHITE
        try:
            mv = msg2move(cmd)
        except Exception as e:
            print(f"MALFORMED move {cmd}: {e}")
            return 1
        for p in mv.positions:
            if not (1 <= p.x <= 19 and 1 <= p.y <= 19):
                print(f"ILLEGAL {cmd}: cell off board")
                return 1
            if board[p.x][p.y] != Defines.NOSTONE:
                print(f"ILLEGAL {cmd}: cell ({p.x},{p.y}) already occupied")
                return 1
        if len(mv.positions) == 2 and (mv.positions[0].x, mv.positions[0].y) == \
           (mv.positions[1].x, mv.positions[1].y) and moves != 0:
            print(f"ILLEGAL {cmd}: duplicated cell in a non-first move")
            return 1
        make_move(board, mv, color)
        moves += 1

    next_color = "black" if moves % 2 == 0 else "white"
    print(f"legal preset: {moves} moves -> {next_color} to move")
    ok = True
    for name, c in (("black", Defines.BLACK), ("white", Defines.WHITE)):
        T, marks, we = threat_scan(board, c)
        line = f"{name}: T={T} marks={sorted(marks)}"
        if we is not None:
            line += f" WIN-IN-1-EXISTS via {we}"
            ok = False
        print(line)
        if T > 0:
            ok = False
    print("STATUS:", "CLEAN (no standing threats)" if ok
          else "STANDING THREATS PRESENT (intended?)")
    return 0


if __name__ == "__main__":
    sys.exit(check(" ".join(sys.argv[1:])))

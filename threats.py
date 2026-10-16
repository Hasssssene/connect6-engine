"""
threats.py -- exact Connect6 threat analysis.

Implements the threat definitions and counting algorithm of Wu & Huang,
"A New Family of k-in-a-Row Games" (ACG-11, LNCS, 2006), Section 4:

- Definition 1 (Connect6: delta = k - p = 4): a player has *t* threats on
  a line iff the opponent must place *t* stones to prevent that player
  from winning on their next move.
- Counting algorithm (proved exact by Lemma 1): slide a 6-window along the
  line; a window is a *threat window* if it contains no opponent stones,
  no previously marked squares, and >= 4 own stones. Each threat window
  adds one threat and marks its rightmost empty square; defending the
  marked squares is sufficient and t stones are necessary.

Properties used by the engine:

1. A threat window of the SIDE TO MOVE contains >= 4 own stones and
   <= 2 empty cells -> the mover can fill it THIS TURN: the window's empty
   cells are an immediate winning pair (both empties for a 4-stone window;
   the single empty + any cell for a 5-stone window).
2. Threat windows of the opponent demand defence: t = 2 -> the two marked
   squares are the forced move; t = 1 -> one stone must anchor on the
   marked square; t >= 3 -> undefendable with 2 stones (lost position).
"""

from defines import Defines

# ---------------------------------------------------------------------------
# Precomputed geometry: all board lines (rows, columns, diagonals) with
# length >= 6, plus the reverse map cell -> indices of lines through it.
# ---------------------------------------------------------------------------


def _build_lines():
    lo, hi = 1, Defines.GRID_NUM - 2          # playable range 1..19
    lines = []
    for x in range(lo, hi + 1):               # rows
        lines.append([(x, y) for y in range(lo, hi + 1)])
    for y in range(lo, hi + 1):               # columns
        lines.append([(x, y) for x in range(lo, hi + 1)])
    for dx, dy in ((1, 1), (1, -1)):          # diagonals
        starts = [(lo, y) for y in range(lo, hi + 1)]
        edge = hi if dy == -1 else lo         # walk direction decides 2nd edge
        starts += [(x, edge) for x in range(lo + 1, hi + 1)]
        for sx, sy in starts:
            cells = []
            x, y = sx, sy
            while lo <= x <= hi and lo <= y <= hi:
                cells.append((x, y))
                x += dx
                y += dy
            if len(cells) >= 6:
                lines.append(cells)
    lines_through = {}
    for i, cells in enumerate(lines):
        for c in cells:
            lines_through.setdefault(c, []).append(i)
    return lines, lines_through


LINES, LINES_THROUGH = _build_lines()          # 92 lines; a cell lies on <= 4


def line_threat_info(board, color, line):
    """Threat analysis of ONE line for ONE colour.

    Returns (t, marked, win_empties):
      t            number of threat windows (paper's algorithm)
      marked       marked (defence) squares of this line
      win_empties  empty cells of the first threat window (immediate winning
                   pair for the side to move), or None
    """
    opp = color ^ 3
    n = len(line)
    t = 0
    marked = set()
    win_empties = None
    for start in range(n - 5):
        own = 0
        empties = []
        ok = True
        for idx in range(start, start + 6):
            x, y = line[idx]
            v = board[x][y]
            if v == opp:
                ok = False
                break
            if v == color:
                own += 1
            elif (x, y) in marked:
                ok = False
                break
            else:
                empties.append((x, y))
        if ok and own >= 4:
            t += 1
            # mark rightmost empty square of the window (Lemma 1)
            for idx in range(start + 5, start - 1, -1):
                x, y = line[idx]
                if board[x][y] == Defines.NOSTONE:
                    marked.add((x, y))
                    break
            if win_empties is None:
                win_empties = empties
    return t, marked, win_empties


def threat_scan(board, color):
    """Whole-board threat analysis for one colour.

    Returns (T, squares, win_empties):
      T            total threats over all lines
      squares      union of marked defence squares
      win_empties  empties of the first threat window found (see above)
    """
    total = 0
    squares = set()
    win_empties = None
    for line in LINES:
        t, marked, we = line_threat_info(board, color, line)
        total += t
        squares |= marked
        if we is not None and win_empties is None:
            win_empties = we
    return total, squares, win_empties

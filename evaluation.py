"""
evaluation.py -- static evaluation for Connect6.

v1 (naive, Practice 1 guide session 1):
- The board is scanned as 6-length windows ("lines") in the 4 directions.
- A window that contains stones of exactly one colour is a LIVE set for
  that colour (it can still grow into a winning row of 6).
- Board score, black perspective:  sum over live windows of k^2,
  where k = number of that colour's stones in the window (k^2 favours
  longer runs -- two separate stones are worth less than a pair).

Two implementations of the same quantity:
- evaluate_board(board)          naive full scan (reference / tests / comparisons)
- IncrementalEvaluator           maintains the score while stones are made and
                                 unmade, so search leaves cost O(1) (decision D-003:
                                 measure first, then optimise -- this is the single
                                 biggest win for pure-Python search speed)

Terminal scores are NOT computed here: the search detects wins via
is_win_by_premove() and full boards via IncrementalEvaluator.is_full().
"""

from defines import Defines

# ---------------------------------------------------------------------------
# Precomputed geometry (built once at import).
# ---------------------------------------------------------------------------

_DIRS = ((0, 1), (1, 0), (1, 1), (1, -1))   # horizontal, vertical, 2 diagonals


def _build_geometry():
    """All 6-cell windows fully inside the 19x19 board, plus the reverse
    map cell -> window indices it belongs to."""
    lo, hi = 1, Defines.GRID_NUM - 2          # playable range 1..19
    windows = []
    cell_windows = {}
    for x in range(lo, hi + 1):
        for y in range(lo, hi + 1):
            for dx, dy in _DIRS:
                ex, ey = x + 5 * dx, y + 5 * dy
                if lo <= ex <= hi and lo <= ey <= hi:
                    widx = len(windows)
                    windows.append(tuple((x + i * dx, y + i * dy) for i in range(6)))
                    for i in range(6):
                        cell_windows.setdefault((x + i * dx, y + i * dy), []).append(widx)
    return windows, cell_windows


WINDOWS, CELL_WINDOWS = _build_geometry()     # 924 windows; a cell belongs to <= 24

# Evaluation clamp: keeps static scores safely below terminal scores
# (Defines.MAXINT = 20000) even on dense boards.
EVAL_CLAMP = 9000


def _clamp(v):
    return max(-EVAL_CLAMP, min(EVAL_CLAMP, v))


# ---------------------------------------------------------------------------
# Naive reference implementation (full board scan).
# ---------------------------------------------------------------------------

def evaluate_board(board):
    """Naive live-set score from BLACK's perspective (positive = black better)."""
    black = 0
    white = 0
    for w in WINDOWS:
        b = 0
        wt = 0
        for x, y in w:
            v = board[x][y]
            if v == Defines.BLACK:
                b += 1
            elif v == Defines.WHITE:
                wt += 1
        if b and not wt:
            black += b * b
        elif wt and not b:
            white += wt * wt
    return black - white


# ---------------------------------------------------------------------------
# Incremental evaluator used by the search.
# ---------------------------------------------------------------------------

class IncrementalEvaluator:
    """Maintains the naive live-set score while the search makes/unmakes moves.

    - make(move, color)   places both stones of a 2-stone move and updates counts
    - unmake(move)        removes them again
    - score(color)        current static score from `color`'s perspective
    - is_full()           True when the board is full (draw condition)

    Window bookkeeping: for each window we store (b, w) stone counts and keep
    running sums m_black / m_white of k^2 over live windows. A window stops
    contributing for a colour the moment it contains a stone of the other colour.
    """

    def __init__(self, board):
        self.m_board = board
        n = len(WINDOWS)
        self.m_wb = [0] * n
        self.m_ww = [0] * n
        self.m_black = 0
        self.m_white = 0
        self.m_stones = 0
        # initial full scan
        for wi, w in enumerate(WINDOWS):
            b = 0
            wt = 0
            for x, y in w:
                v = board[x][y]
                if v == Defines.BLACK:
                    b += 1
                elif v == Defines.WHITE:
                    wt += 1
            self.m_wb[wi] = b
            self.m_ww[wi] = wt
            if b and not wt:
                self.m_black += b * b
            elif wt and not b:
                self.m_white += wt * wt
        lo, hi = 1, Defines.GRID_NUM - 2
        for x in range(lo, hi + 1):
            row = board[x]
            for y in range(lo, hi + 1):
                if row[y] != Defines.NOSTONE:
                    self.m_stones += 1

    # -- stone placement ----------------------------------------------------

    def make(self, move, color):
        board = self.m_board
        for p in move.positions:
            x, y = p.x, p.y
            if board[x][y] != Defines.NOSTONE:
                continue                      # guard: duplicated cell (first move)
            board[x][y] = color
            self.m_stones += 1
            for wi in CELL_WINDOWS[(x, y)]:
                if color == Defines.BLACK:
                    b = self.m_wb[wi]
                    w = self.m_ww[wi]
                    if w == 0:
                        self.m_black += (b + 1) * (b + 1) - b * b
                    elif b == 0 and w > 0:
                        self.m_white -= w * w                 # black kills white's window
                    self.m_wb[wi] = b + 1
                else:
                    b = self.m_wb[wi]
                    w = self.m_ww[wi]
                    if b == 0:
                        self.m_white += (w + 1) * (w + 1) - w * w
                    elif w == 0 and b > 0:
                        self.m_black -= b * b                 # white kills black's window
                    self.m_ww[wi] = w + 1

    def unmake(self, move):
        board = self.m_board
        for p in move.positions:
            x, y = p.x, p.y
            color = board[x][y]
            if color == Defines.NOSTONE:
                continue                      # guard: cell was never placed
            self.m_stones -= 1
            for wi in CELL_WINDOWS[(x, y)]:
                if color == Defines.BLACK:
                    b = self.m_wb[wi]
                    w = self.m_ww[wi]
                    if w == 0:
                        self.m_black += (b - 1) * (b - 1) - b * b
                    elif b == 1 and w > 0:
                        self.m_white += w * w                 # black gone -> white's window revives
                    self.m_wb[wi] = b - 1
                else:
                    b = self.m_wb[wi]
                    w = self.m_ww[wi]
                    if b == 0:
                        self.m_white += (w - 1) * (w - 1) - w * w
                    elif w == 1 and b > 0:
                        self.m_black += b * b                 # white gone -> black's window revives
                    self.m_ww[wi] = w - 1
            board[x][y] = Defines.NOSTONE

    # -- queries --------------------------------------------------------------

    def score_black(self):
        return self.m_black - self.m_white

    def score(self, color):
        """Clamped static score from `color`'s perspective (leaf evaluation)."""
        s = self.score_black()
        if color != Defines.BLACK:
            s = -s
        return _clamp(s)

    def raw(self, color):
        """UNclamped score for delta computations (candidate probes)."""
        s = self.score_black()
        return -s if color != Defines.BLACK else s

    def is_full(self):
        return self.m_stones >= Defines.GRID_COUNT

"""
search_engine.py -- v2 search: ALPHA-BETA pruning + ITERATIVE DEEPENING
under a per-turn time budget.

Practice 1 guide, sessions 1-2:
- v1 (kept for comparisons): plain minimax over 2-stone moves.
- v2 (default): alpha-beta over the same move space. With equal move
  ordering the root value is identical to minimax, but cutoffs skip
  subtrees that cannot change the decision -- measured by m_pruned_nodes.
- Iterative deepening: search depth 1, 2, 3, ... reusing the previous
  iteration's best move as the first root move (ordering across
  iterations). A deadline stops the search; the best move of the LAST
  COMPLETED iteration is played. Depth 1 always completes (no deadline),
  guaranteeing a legal answer in milliseconds.
- Time semantics (statement section 5.10 / decision D-002): the `depth d`
  command value is interpreted as SECONDS per move (GUI sends 4/5/6;
  game_engine clamps it to 1..9, always far below the GUI's 30 s timeout).

Search flags (used by devtools/benchmark.py for report comparisons):
- ITERATIVE     True  -> time-budgeted iterative deepening (v2 default)
                   False -> single fixed-depth pass at FIXED_DEPTH (v1 mode)
- USE_ALPHABETA True  -> alpha-beta;  False -> plain minimax (v1 algorithm)
- ORDER_MOVES   True  -> probe-ordered moves; False -> reversed order
                   (worst-case ordering, to measure pruning sensitivity)

NOTE on SearchTimeUp: the exception can interrupt make/unmake sequences,
leaving the IncrementalEvaluator dirty. This is safe: evaluator state is
created per search (before_search) and never reused after the exception --
only the already-computed best move of the previous iteration is returned.
"""

from tools import *
from defines import Defines
from evaluation import IncrementalEvaluator
from threats import LINES, LINES_THROUGH, line_threat_info, threat_scan
import time

# --- tunables ----------------------------------------------------------------

CAND_RADIUS = 2           # Chebyshev radius for candidate cells
MAX_CANDIDATE_CELLS = 20  # cap on candidate cells kept after ranking
TOP_K = 10                # cells combined into 2-stone moves -> 45 pairs
MAX_DEPTH = 8             # iterative-deepening ceiling (deadline stops earlier)
DEFAULT_TIME_BUDGET = 6.0 # seconds, when no valid `depth d` was received
NODE_LIMIT = 200000       # hard safety cap on expanded nodes

# Neighbourhood offsets for candidate scoring (radius 2, without (0,0)).
_R2_OFFSETS = [(dx, dy) for dx in range(-CAND_RADIUS, CAND_RADIUS + 1)
               for dy in range(-CAND_RADIUS, CAND_RADIUS + 1) if dx or dy]

WIN_SCORE = Defines.MAXINT - 100   # scores at/above this mean "forced win found"

# --- v3 threat-layer tunables -------------------------------------------------

# v4: root pair-scoring weight per threat (capped at 3) -- GA-optimised
# together with the feature weights (champion genome gene 'threat').
THREAT_WEIGHT = 377.0
ROOT_FIRST_STONES = 8     # w: first stones tried in two-level generation (paper 4.3)


class SearchTimeUp(Exception):
    """Raised internally when the per-turn deadline is exceeded."""


class SearchEngine():
    # Search configuration flags (see module docstring).
    ITERATIVE = True
    USE_ALPHABETA = True
    ORDER_MOVES = True
    FIXED_DEPTH = 2         # used when ITERATIVE is False

    def __init__(self):
        self.m_board = None
        self.m_chess_type = None
        self.m_alphabeta_depth = None
        self.m_total_nodes = 0     # expanded nodes
        self.m_pruned_nodes = 0    # moves skipped by cutoffs / early win exit
        self.m_reached_depth = 0   # deepest COMPLETED iteration (turns)
        self._eval = None
        self._deadline = None

    def before_search(self, board, color, alphabeta_depth):
        self.m_board = [row[:] for row in board]
        self.m_chess_type = color
        self.m_alphabeta_depth = alphabeta_depth
        self.m_total_nodes = 0
        self.m_pruned_nodes = 0
        self.m_reached_depth = 0
        self._deadline = None

    # ------------------------------------------------------------------
    # Entry point (skeleton-compatible signature; depth = seconds, D-002).
    # ------------------------------------------------------------------

    def alpha_beta_search(self, depth, alpha, beta, ourColor, bestMove, preMove):
        self.m_total_nodes = 0
        self.m_pruned_nodes = 0
        self.m_reached_depth = 0

        # Defensive: the opponent's last move already ended the game.
        if is_win_by_premove(self.m_board, preMove):
            return -(Defines.MAXINT - 1)

        # Opening: empty board -> play the centre (black's single stone).
        if self.check_first_move():
            c = (Defines.GRID_NUM - 1) // 2
            bestMove.positions[0].x = bestMove.positions[1].x = c
            bestMove.positions[0].y = bestMove.positions[1].y = c
            bestMove.score = 0
            return 0

        try:
            budget = float(depth)
        except (TypeError, ValueError):
            budget = DEFAULT_TIME_BUDGET
        if budget <= 0:
            budget = DEFAULT_TIME_BUDGET

        self._eval = IncrementalEvaluator(self.m_board)

        # v3 root layer: exact threat analysis -> win-now / forced / anchored /
        # two-level candidate pairs (Wu & Huang Sec. 4; see threats.py).
        root_moves, forced = self._root_moves(ourColor, ourColor ^ 3)
        if not root_moves:
            return 0                       # board full: nothing to play

        start = time.perf_counter()

        if self.ITERATIVE:
            # Depth 1 always completes (deadline disabled) -> legal answer fast.
            self._deadline = None
            best_move, best_score = self._root_pass(1, root_moves, ourColor)
            self.m_reached_depth = 1
            self._deadline = start + budget
            d = 2
            while (not forced) and d <= MAX_DEPTH and best_score < WIN_SCORE:
                try:
                    self._order_root(root_moves, best_move)
                    m, s = self._root_pass(d, root_moves, ourColor)
                except SearchTimeUp:
                    break                  # keep the last completed iteration
                best_move, best_score = m, s
                self.m_reached_depth = d
                d += 1
        else:
            # Fixed-depth mode (v1 behaviour / report comparisons).
            d = max(1, min(self.FIXED_DEPTH, MAX_DEPTH))
            best_move, best_score = self._root_pass(d, root_moves, ourColor)
            self.m_reached_depth = d

        if best_move is not None:
            bestMove.positions[0].x = best_move.positions[0].x
            bestMove.positions[0].y = best_move.positions[0].y
            bestMove.positions[1].x = best_move.positions[1].x
            bestMove.positions[1].y = best_move.positions[1].y
            bestMove.score = best_move.score
        return best_score

    # ------------------------------------------------------------------
    # Root: iterate the ordered candidate moves, maximising.
    # ------------------------------------------------------------------

    def _root_pass(self, depth, moves, color):
        alpha = Defines.MININT
        best = None
        for i, mv in enumerate(moves):
            self._eval.make(mv, color)
            if self.USE_ALPHABETA:
                score = self._alpha_beta(depth - 1, alpha, Defines.MAXINT,
                                         color ^ 3, 1, mv)
            else:
                score = self._minimax(depth - 1, color ^ 3, 1, mv)
            self._eval.unmake(mv)
            if best is None or score > alpha:
                alpha = score
                best = mv
            if alpha >= WIN_SCORE:
                # Forced win found: stop searching, play it.
                self.m_pruned_nodes += len(moves) - i - 1
                break
        return best, alpha

    def _order_root(self, moves, best):
        """Move the previous iteration's best move to the front."""
        if best is None:
            return
        target = {(best.positions[0].x, best.positions[0].y),
                  (best.positions[1].x, best.positions[1].y)}
        for i, m in enumerate(moves):
            cells = {(m.positions[0].x, m.positions[0].y),
                     (m.positions[1].x, m.positions[1].y)}
            if cells == target:
                moves.insert(0, moves.pop(i))
                return

    # ------------------------------------------------------------------
    # v3 root layer: threat-driven move construction (Wu & Huang Sec. 4).
    # ------------------------------------------------------------------

    def _make_pair(self, c1, c2, score=0.0):
        mv = StoneMove()
        mv.positions[0].x, mv.positions[0].y = c1
        mv.positions[1].x, mv.positions[1].y = c2
        mv.score = score
        return mv

    def _root_moves(self, color, opp):
        """Build the root move list from exact threat analysis.

        Priority (returns (moves, forced)):
        1. own threat window -> immediate winning pair (forced);
        2. opponent threats >= 3 -> best-effort double block (forced, lost);
           opponent threats == 2 -> the two marked squares (forced);
           opponent threats == 1 -> anchored pairs (mark + free partner);
        3. two-level generation (paper Sec. 4.3): place first stone,
           re-rank, pick partners; pairs scored by threat/feature deltas.
        """
        board = self.m_board
        cells = self._candidate_cells(color)         # probe-ranked [(x, y, t)]

        own_line_t = []
        opp_line_t = []
        opp_marks = set()
        T_own = T_opp = 0
        win_empties = None
        for li, line in enumerate(LINES):
            t, _, we = line_threat_info(board, color, line)
            own_line_t.append(t)
            T_own += t
            if we is not None and win_empties is None:
                win_empties = we
            t2, mk, _ = line_threat_info(board, opp, line)
            opp_line_t.append(t2)
            T_opp += t2
            opp_marks |= mk

        # 1) own threat window: fill it this turn and win.
        if win_empties:
            if len(win_empties) >= 2:
                return [self._make_pair(win_empties[0], win_empties[1], 1e9)], True
            e = win_empties[0]
            partner = next(((c[0], c[1]) for c in cells if (c[0], c[1]) != e), None)
            if partner is None:
                partner = self._any_empty_except(e)
            return [self._make_pair(e, partner, 1e9)], True

        # 2) opponent threats: forced or anchored defence.
        if T_opp >= 2 and len(opp_marks) >= 2:
            s = sorted(opp_marks)
            return [self._make_pair(s[0], s[1], 0.0)], True
        if T_opp >= 1 and opp_marks:
            anchor = sorted(opp_marks)[0]
            partners = [(c[0], c[1]) for c in cells if (c[0], c[1]) != anchor]
            if not partners:
                partners = [self._any_empty_except(anchor)]
            moves = []
            base_raw = self._eval.raw(color)
            for p in partners[:ROOT_FIRST_STONES + 4]:
                mv = self._make_pair(anchor, p)
                mv.score = self._pair_tactical(mv, color, opp, base_raw,
                                               own_line_t, opp_line_t, T_own, T_opp)
                moves.append(mv)
            moves.sort(key=lambda m: -m.score)
            return moves, False

        # 3) two-level generation with threat-aware pair scoring.
        top = cells[:ROOT_FIRST_STONES]
        if len(top) < 2:
            return self.generate_candidate_moves(color), False
        base_raw = self._eval.raw(color)
        scratch = StoneMove()
        seen = set()
        moves = []
        for i, (x1, y1, s1) in enumerate(top):
            # place the first stone and RE-RANK cells (paper: synergy)
            scratch.positions[0].x = scratch.positions[1].x = x1
            scratch.positions[0].y = scratch.positions[1].y = y1
            self._eval.make(scratch, color)
            re_cells = self._candidate_cells(color)
            self._eval.unmake(scratch)
            w_i = ROOT_FIRST_STONES - i              # decreasing width
            for (x2, y2, s2) in re_cells[:w_i]:
                if (x2, y2) == (x1, y1):
                    continue
                key = frozenset(((x1, y1), (x2, y2)))
                if key in seen:
                    continue
                seen.add(key)
                mv = self._make_pair((x1, y1), (x2, y2))
                mv.score = self._pair_tactical(mv, color, opp, base_raw,
                                               own_line_t, opp_line_t, T_own, T_opp)
                moves.append(mv)
        moves.sort(key=lambda m: -m.score)
        return moves, False

    def _pair_tactical(self, mv, color, opp, base_raw,
                       own_line_t, opp_line_t, T_own, T_opp):
        """Score a candidate pair: feature delta + threats created/allowed.

        Threats are recomputed only on the (<= 8) lines through the pair's
        cells; unaffected lines reuse the base per-line counts.
        """
        board = self.m_board
        affected = set()
        for p in mv.positions:
            affected.update(LINES_THROUGH.get((p.x, p.y), ()))
        self._eval.make(mv, color)
        own_after = T_own - sum(own_line_t[i] for i in affected) \
            + sum(line_threat_info(board, color, LINES[i])[0] for i in affected)
        opp_after = T_opp - sum(opp_line_t[i] for i in affected) \
            + sum(line_threat_info(board, opp, LINES[i])[0] for i in affected)
        ev = self._eval.raw(color) - base_raw
        self._eval.unmake(mv)
        return (ev
                + THREAT_WEIGHT * min(own_after, 3)
                - THREAT_WEIGHT * min(opp_after, 3))

    def _any_empty_except(self, cell):
        board = self.m_board
        for x in range(1, Defines.GRID_NUM - 1):
            for y in range(1, Defines.GRID_NUM - 1):
                if board[x][y] == Defines.NOSTONE and (x, y) != cell:
                    return (x, y)
        return cell

    # ------------------------------------------------------------------
    # v2: alpha-beta (fail-hard) over 2-stone moves. `depth` counts TURNS.
    # ------------------------------------------------------------------

    def _alpha_beta(self, depth, alpha, beta, to_move, ply, pre_move):
        self.m_total_nodes += 1
        self._check_time()
        if is_win_by_premove(self.m_board, pre_move):
            winner = to_move ^ 3
            if winner == self.m_chess_type:
                return Defines.MAXINT - ply
            return -(Defines.MAXINT - ply)
        if self._eval.is_full():
            return 0
        if depth <= 0:
            return self._eval.score(self.m_chess_type)
        if self.m_total_nodes >= NODE_LIMIT:
            return self._eval.score(self.m_chess_type)

        maximizing = (to_move == self.m_chess_type)
        moves = self.generate_candidate_moves(to_move)
        if not moves:
            return 0
        if not self.ORDER_MOVES:
            moves = moves[::-1]

        best = None
        for i, mv in enumerate(moves):
            self._eval.make(mv, to_move)
            score = self._alpha_beta(depth - 1, alpha, beta,
                                     to_move ^ 3, ply + 1, mv)
            self._eval.unmake(mv)
            if maximizing:
                if best is None or score > best:
                    best = score
                if best > alpha:
                    alpha = best
                if alpha >= beta:                      # beta cutoff
                    self.m_pruned_nodes += len(moves) - i - 1
                    break
            else:
                if best is None or score < best:
                    best = score
                if best < beta:
                    beta = best
                if alpha >= beta:                      # alpha cutoff
                    self.m_pruned_nodes += len(moves) - i - 1
                    break
        return best

    # ------------------------------------------------------------------
    # v1: plain minimax (kept verbatim for comparisons).
    # ------------------------------------------------------------------

    def _minimax(self, depth, to_move, ply, pre_move):
        self.m_total_nodes += 1
        self._check_time()
        if is_win_by_premove(self.m_board, pre_move):
            winner = to_move ^ 3
            if winner == self.m_chess_type:
                return Defines.MAXINT - ply
            return -(Defines.MAXINT - ply)
        if self._eval.is_full():
            return 0
        if depth <= 0:
            return self._eval.score(self.m_chess_type)
        if self.m_total_nodes >= NODE_LIMIT:
            return self._eval.score(self.m_chess_type)

        maximizing = (to_move == self.m_chess_type)
        moves = self.generate_candidate_moves(to_move)
        if not moves:
            return 0
        if not self.ORDER_MOVES:
            moves = moves[::-1]

        best = None
        for mv in moves:
            self._eval.make(mv, to_move)
            score = self._minimax(depth - 1, to_move ^ 3, ply + 1, mv)
            self._eval.unmake(mv)
            if best is None:
                best = score
            elif maximizing:
                if score > best:
                    best = score
            else:
                if score < best:
                    best = score
        return best

    def _check_time(self):
        if self._deadline is not None and (self.m_total_nodes & 63) == 0:
            if time.perf_counter() >= self._deadline:
                raise SearchTimeUp()

    # ------------------------------------------------------------------
    # Candidate move generation (guide sessions 1-2: capped, ranked).
    # ------------------------------------------------------------------

    def check_first_move(self):
        for i in range(1, len(self.m_board) - 1):
            for j in range(1, len(self.m_board[i]) - 1):
                if self.m_board[i][j] != Defines.NOSTONE:
                    return False
        return True

    def _candidate_cells(self, to_move):
        """Empty cells within CAND_RADIUS of any stone, ranked by tactical value.

        Ranking = evaluation-delta probes with the IncrementalEvaluator:
        for each cell we measure the score change (to_move perspective) of
        placing our stone (attack value) and of placing the opponent's stone
        (defence value = damage they would do), plus immediate win/block flags.
        This makes line extensions and forced blocks outrank generic
        development cells (fix for the proximity-ranking miss found in testing).
        Returns [(x, y, score)] sorted descending, capped at MAX_CANDIDATE_CELLS.
        """
        board = self.m_board
        lo, hi = 1, Defines.GRID_NUM - 2
        near = set()
        for x in range(lo, hi + 1):
            row = board[x]
            for y in range(lo, hi + 1):
                if row[y] == Defines.NOSTONE:
                    continue
                for dx, dy in _R2_OFFSETS:
                    nx, ny = x + dx, y + dy
                    if lo <= nx <= hi and lo <= ny <= hi and board[nx][ny] == Defines.NOSTONE:
                        near.add((nx, ny))
        if not near:
            return []

        opp = to_move ^ 3
        scratch = StoneMove()
        base = self._eval.raw(to_move)
        scored = []
        for x, y in near:
            scratch.positions[0].x = scratch.positions[1].x = x
            scratch.positions[0].y = scratch.positions[1].y = y
            # attack probe: our stone on this cell
            self._eval.make(scratch, to_move)
            s_own = self._eval.raw(to_move) - base
            own_win = is_win_by_premove(self.m_board, scratch)
            self._eval.unmake(scratch)
            # defence probe: opponent's stone on this cell
            self._eval.make(scratch, opp)
            s_opp = self._eval.raw(to_move) - base          # <= 0 for us
            opp_win = is_win_by_premove(self.m_board, scratch)
            self._eval.unmake(scratch)

            if own_win:
                t = 1000000                                  # we win by playing here
            elif opp_win:
                t = 500000                                   # must block: they win here
            else:
                t = 2 * s_own - 2 * s_opp                    # attack + defence, equal weight
            scored.append((x, y, t))
        scored.sort(key=lambda r: r[2], reverse=True)
        return scored[:MAX_CANDIDATE_CELLS]

    def generate_candidate_moves(self, to_move):
        """Ordered 2-stone moves from the top candidate cells (distinct cells)."""
        cells = self._candidate_cells(to_move)
        if not cells:
            return []
        top = cells[:TOP_K]
        moves = []
        for i in range(len(top)):
            x1, y1, s1 = top[i]
            for j in range(i + 1, len(top)):
                x2, y2, s2 = top[j]
                mv = StoneMove()
                mv.positions[0].x, mv.positions[0].y = x1, y1
                mv.positions[1].x, mv.positions[1].y = x2, y2
                mv.score = s1 + s2
                moves.append(mv)
        if len(top) == 1:
            # Degenerate endgame: pair the single candidate with any empty cell.
            x1, y1, s1 = top[0]
            board = self.m_board
            for x in range(1, Defines.GRID_NUM - 1):
                for y in range(1, Defines.GRID_NUM - 1):
                    if board[x][y] == Defines.NOSTONE and (x, y) != (x1, y1):
                        mv = StoneMove()
                        mv.positions[0].x, mv.positions[0].y = x1, y1
                        mv.positions[1].x, mv.positions[1].y = x, y
                        mv.score = s1
                        moves.append(mv)
                        break
                if moves:
                    break
        moves.sort(key=lambda m: m.score, reverse=True)
        return moves

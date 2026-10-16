"""
search_engine.py -- v1 search: fixed-depth MINIMAX over 2-stone moves.

Practice 1 guide, session 1:
- candidate generation: empty cells within Chebyshev radius 2 of any stone,
  weighted by proximity (opponent stones weighted slightly higher -> mild
  defence bias), capped, ranked; the TOP_K cells are combined into ordered
  2-stone moves (always two DISTINCT cells, decision D-004).
- evaluation: IncrementalEvaluator (evaluation.py) -> O(1) leaf scores.
- terminal conditions: win via is_win_by_premove (score MAXINT - ply, so
  faster wins score higher), draw (full board) = 0.
- NODE_LIMIT safety valve guarantees a bounded search (real-time demand).

Interface note (D-004): the entry point alpha_beta_search(...) keeps the
skeleton's signature so game_engine.py is untouched. v1 implements plain
minimax and IGNORES alpha/beta; v2 will turn them into real alpha-beta.

`depth` handling in v1: the GUI sends depth 4/5/6 but v1 clamps the search
to V1_MAX_DEPTH turns (each turn = one 2-stone move). Statement redefines
'depth d' as a per-turn TIME limit -- full time management arrives in v2
with iterative deepening (decision D-002).
"""

from tools import *
from defines import Defines
from evaluation import IncrementalEvaluator

# --- tunables (v1) ----------------------------------------------------------

CAND_RADIUS = 2          # Chebyshev radius for candidate cells
MAX_CANDIDATE_CELLS = 20 # cap on candidate cells kept after ranking
TOP_K = 10               # cells combined into 2-stone moves -> 45 pairs
V1_MAX_DEPTH = 2         # turns; root move + opponent reply
NODE_LIMIT = 60000       # hard safety cap on expanded nodes

# Neighbourhood offsets for candidate scoring (radius 2, without (0,0)).
_R2_OFFSETS = [(dx, dy) for dx in range(-CAND_RADIUS, CAND_RADIUS + 1)
               for dy in range(-CAND_RADIUS, CAND_RADIUS + 1) if dx or dy]


class SearchEngine():
    def __init__(self):
        self.m_board = None
        self.m_chess_type = None
        self.m_alphabeta_depth = None
        self.m_total_nodes = 0
        self._eval = None

    def before_search(self, board, color, alphabeta_depth):
        self.m_board = [row[:] for row in board]
        self.m_chess_type = color
        self.m_alphabeta_depth = alphabeta_depth
        self.m_total_nodes = 0

    # ------------------------------------------------------------------
    # Entry point (skeleton-compatible signature).
    # ------------------------------------------------------------------

    def alpha_beta_search(self, depth, alpha, beta, ourColor, bestMove, preMove):
        self.m_total_nodes = 0

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

        depth = min(depth, V1_MAX_DEPTH)
        self._eval = IncrementalEvaluator(self.m_board)

        root_moves = self.generate_candidate_moves(ourColor)
        if not root_moves:
            return 0                       # board full: nothing to play

        best_score = None
        for mv in root_moves:
            self._eval.make(mv, ourColor)
            score = self._minimax(depth - 1, ourColor ^ 3, 1, mv)
            self._eval.unmake(mv)
            if best_score is None or score > best_score:
                best_score = score
                bestMove.positions[0].x = mv.positions[0].x
                bestMove.positions[0].y = mv.positions[0].y
                bestMove.positions[1].x = mv.positions[1].x
                bestMove.positions[1].y = mv.positions[1].y
                bestMove.score = mv.score
            if best_score >= Defines.MAXINT - 100:
                break                      # forced win found: play it now
            if self.m_total_nodes >= NODE_LIMIT:
                break                      # safety valve (never hit at v1 sizes)
        return best_score

    # ------------------------------------------------------------------
    # Plain minimax over 2-stone moves. `depth` counts TURNS.
    # ------------------------------------------------------------------

    def _minimax(self, depth, to_move, ply, pre_move):
        self.m_total_nodes += 1

        # Previous mover (opponent of to_move) completed 6 with pre_move.
        if is_win_by_premove(self.m_board, pre_move):
            winner = to_move ^ 3
            if winner == self.m_chess_type:
                return Defines.MAXINT - ply   # prefer faster wins
            return -(Defines.MAXINT - ply)

        if self._eval.is_full():
            return 0                          # draw

        if depth <= 0:
            return self._eval.score(self.m_chess_type)

        if self.m_total_nodes >= NODE_LIMIT:  # safety valve
            return self._eval.score(self.m_chess_type)

        maximizing = (to_move == self.m_chess_type)
        moves = self.generate_candidate_moves(to_move)
        if not moves:
            return 0

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

    # ------------------------------------------------------------------
    # Candidate move generation (guide session 1: capped, ranked).
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

"""
headless_match.py -- Run a scripted Connect6 match between two engines
without the Tkinter GUI.

Reuses the GUI's protocol wrapper (Connect6GUI-master/engine.py) and
replicates the GUI's game rules (ConnectMore.py):
  - turn order (black plays first, 1 stone; then 2 stones per turn)
  - move validation (impossible / duplicated moves lose the game)
  - win detection (6+ in a row) and draw (full board)
  - per-move timeout (default 30 s, like the GUI)

Usage (from Connect6Engine-master/):
    python devtools/headless_match.py --black dist/main.exe --white ../Connect6GUI-master/engines/cloudict.exe
    python devtools/headless_match.py --black a.exe --white b.exe --depth 5 --novcf --out match.txt

Dev tool only -- not part of the delivered engine.
"""

import argparse
import os
import sys
import time

# Import the GUI protocol wrapper without touching the GUI repo.
GUI_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                       '..', '..', 'Connect6GUI-master')
sys.path.insert(0, GUI_DIR)

from engine import GameEngine, Move  # noqa: E402


class RuleError(Exception):
    """Raised when an engine breaks the game rules (loses the game)."""


def connected_by_direction(board, x, y, dx, dy):
    """Count consecutive same-colour stones through (x, y) along (dx, dy)."""
    cnt = 1
    xx, yy = dx, dy
    while Move.isValidPosition(x + xx, y + yy) and board[x][y] == board[x + xx][y + yy]:
        xx += dx
        yy += dy
        cnt += 1
    xx, yy = -dx, -dy
    while Move.isValidPosition(x + xx, y + yy) and board[x][y] == board[x + xx][y + yy]:
        xx -= dx
        yy -= dy
        cnt += 1
    return cnt


def connected_by(board, x, y):
    for dx, dy in ((1, 1), (1, -1), (1, 0), (0, 1)):
        if connected_by_direction(board, x, y, dx, dy) >= 6:
            return True
    return False


def next_color(moves):
    return Move.BLACK if len(moves) % 2 == 0 else Move.WHITE


def wait_for_move(eng, color, timeout, verbose, transcript):
    """Read engine stdout until a valid 'move ...' line appears.

    Mirrors the GUI: non-move diagnostic lines are ignored (but recorded).
    Raises RuleError if the engine process dies.
    """
    t0 = time.perf_counter()
    while True:
        line = eng.proc.stdout.readline().decode(errors='replace')
        if line == '':
            raise RuleError(f'engine {eng.name} died (closed stdout)')
        line = line.rstrip('\n')
        transcript.append(line)
        if verbose:
            print(f'    [{eng.name}] {line}')
        move = Move.fromCmd(line, color)
        if move is not None:
            if not move.isValidated():
                raise RuleError(f'engine {eng.name} sent invalid move: {line!r}')
            return move, time.perf_counter() - t0
        if time.perf_counter() - t0 > timeout:
            raise TimeoutError(f'engine {eng.name} exceeded {timeout:.0f}s thinking time')


def apply_move(board, move, moves):
    """Validate + place a move. Raises RuleError on illegal moves."""
    first = len(moves) == 0
    single = first and (move.x1, move.y1) == (move.x2, move.y2)
    cells = [(move.x1, move.y1)] if single else [(move.x1, move.y1), (move.x2, move.y2)]
    for x, y in cells:
        if board[x][y] != Move.NONE:
            raise RuleError(
                f'colour {move.color} played on occupied cell ({x},{y}) -- duplicated move')
        board[x][y] = move.color
    moves.append(move)


def play(black_path, white_path, depth, vcf, timeout, max_turns, verbose):
    engines = {Move.BLACK: GameEngine(), Move.WHITE: GameEngine()}
    print(f'Loading black: {black_path}')
    engines[Move.BLACK].init(black_path, depth, vcf)
    print(f'Loading white: {white_path}')
    engines[Move.WHITE].init(white_path, depth, vcf)

    board = [[Move.NONE] * Move.EDGE for _ in range(Move.EDGE)]
    moves = []
    times = []
    transcript = []
    result = None      # Move.BLACK / Move.WHITE / Move.NONE (draw) / -1 (undecided)
    error = None

    try:
        while result is None:
            color = next_color(moves)
            eng = engines[color]
            eng.color = color
            eng.next(moves)  # sends 'new xxx' + replayed moves + 'next'
            try:
                # Current mover is responsible for rule/time violations.
                move, dt = wait_for_move(eng, color, timeout, verbose, transcript)
                times.append(dt)
                apply_move(board, move, moves)
            except (RuleError, TimeoutError) as e:
                error = str(e)
                result = Move.WHITE if color == Move.BLACK else Move.BLACK
                print(f'==> {e}')
                print(f'==> {"BLACK" if result == Move.BLACK else "WHITE"} wins '
                      f'by opponent rule violation')
                break

            transcript.append(f'{"black" if color == Move.BLACK else "white"} {move.cmd()}')
            print(f'turn {len(moves):3d} | {"B" if color == Move.BLACK else "W"} | '
                  f'{move.cmd()} | {dt:6.2f}s')

            # Win / draw checks (GUI order: stones just placed, then full board).
            single = len(moves) == 1 and (move.x1, move.y1) == (move.x2, move.y2)
            placed = [(move.x1, move.y1)] if single else \
                     [(move.x1, move.y1), (move.x2, move.y2)]
            if any(connected_by(board, x, y) for x, y in placed):
                result = color
                print(f'==> {"BLACK" if color == Move.BLACK else "WHITE"} wins by Connect6 '
                      f'on turn {len(moves)}')
            elif all(board[x][y] != Move.NONE
                     for x in range(Move.EDGE) for y in range(Move.EDGE)):
                result = Move.NONE
                print('==> DRAW (full board)')
            elif len(moves) >= max_turns:
                print(f'==> UNDECIDED after {max_turns} turns (safety stop)')
                result = -1
    finally:
        for eng in engines.values():
            eng.release()
    return result, error, moves, times, transcript


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--black', required=True, help='path to black engine executable')
    ap.add_argument('--white', required=True, help='path to white engine executable')
    ap.add_argument('--depth', type=int, default=4,
                    help='depth/level sent to engines (GUI default 4)')
    ap.add_argument('--novcf', action='store_true', help='send unvcf instead of vcf')
    ap.add_argument('--timeout', type=float, default=30.0,
                    help='per-move timeout in seconds (GUI: 30)')
    ap.add_argument('--max-turns', type=int, default=200, help='safety stop')
    ap.add_argument('--verbose', action='store_true', help='print all engine output lines')
    ap.add_argument('--out', help='write transcript to this file')
    args = ap.parse_args()

    result, error, moves, times, transcript = play(
        args.black, args.white, args.depth, not args.novcf,
        args.timeout, args.max_turns, args.verbose)

    if args.out:
        with open(args.out, 'w', encoding='utf-8') as f:
            f.write('\n'.join(transcript) + '\n')
            f.write(f'RESULT: {result}\n')
            if error:
                f.write(f'ERROR: {error}\n')
            f.write('TIMES: ' + ' '.join(f'{t:.2f}' for t in times) + '\n')

    for name, ts in (('black', times[0::2]), ('white', times[1::2])):
        if ts:
            print(f'{name}: moves={len(ts)} avg={sum(ts) / len(ts):.2f}s max={max(ts):.2f}s')
    return 0


if __name__ == '__main__':
    sys.exit(main())

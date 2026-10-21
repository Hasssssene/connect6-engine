"""
tournament.py -- headless round-robin tournament between engine builds.

Reuses the GUI's tournament module (Connect6GUI-master/tournament.py) for
game scheduling, scoring (2/1/0, Buchholz tie-break) and the results
export format, and the proven headless_match.play() for game execution.

Usage:
    python devtools/tournament.py --out ../connect6-vault/05-Report/assets/2026-10-21_tournament.txt

Players (hardcoded, all at depth 4 like the GUI's default AI level):
    v1 (minimax), v2 (alpha-beta), v3 (threats), v4 (GA weights), cloudict

Dev tool only -- not part of the delivered engine.
"""

import argparse
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from headless_match import play                      # noqa: E402

GUI_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                       '..', '..', 'Connect6GUI-master')
sys.path.insert(0, GUI_DIR)

from tournament import RoundRobinTournament, BotPlayer  # noqa: E402
from engine import Move                              # noqa: E402

PLAYERS = [
    ("v1-minimax", "dist/v1_main.exe"),
    ("v2-alphabeta", "dist/v2_main.exe"),
    ("v3-threats", "dist/v3_main.exe"),
    ("v4-GA", "dist/main.exe"),
    ("cloudict", os.path.join(GUI_DIR, "engines", "cloudict.exe")),
]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--depth", type=int, default=4)
    args = ap.parse_args()

    t = RoundRobinTournament(1)
    for name, path in PLAYERS:
        p = BotPlayer()
        p.path = os.path.abspath(path)
        p.name = name
        p.id = len(t.players)
        t.players.append(p)
    t.generate_games()
    print(f"tournament: {len(t.players)} players, {len(t.games)} games\n")

    t0 = time.time()
    for i, game in enumerate(t.games, 1):
        bname, wname = game.black.name, game.white.name
        print(f"game {i:2d}/{len(t.games)}: {bname} (B) vs {wname} (W) ...",
              flush=True)
        result, error, moves, times, transcript = play(
            game.black.path, game.white.path, args.depth, True, 30.0, 200,
            False)
        if result == -1:
            result = Move.NONE                    # undecided -> scored as draw
        game.result = result
        game.moves = moves
        game.times = times
        game.feedback = "Connect6" if result in (Move.BLACK, Move.WHITE) else \
                        ("Full board" if result == Move.NONE else "error")
        if error:
            game.feedback = error
        winner = {Move.BLACK: f"{bname} (B)", Move.WHITE: f"{wname} (W)",
                  Move.NONE: "draw"}[result]
        print(f"   -> {winner} on turn {len(moves)}  "
              f"({time.time() - t0:.0f}s elapsed)", flush=True)

    with open(args.out, "w", encoding="utf-8") as f:
        t.save_results(f)
    print("\nresults written to", args.out)

    # console summary
    classification, cross = t.get_classification()
    print("\nRK  PLAYER         PTS  BUCH  TIMEOUTS  INCORRECT")
    for i, (player, score, buch, to, inc) in enumerate(classification, 1):
        print(f"{i:2d}  {player.name:14} {score:3d}  {buch:4d}  {to:8d}  {inc:9d}")


if __name__ == "__main__":
    main()

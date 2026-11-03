"""
ga_heldout.py -- evaluate the GA champion vs the hand-tuned baseline on
UNSEEN randomized openings (held-out seeds, disjoint from training and
champion-selection seeds: training used Random(7) values in [1,1e6);
champion selection used 424242+i*1337; held-out uses 990001+i*7919).

Reports aggregate fitness (10 games: 5 seeds x both colours) AND the
per-game record, which the aggregate fitness hides.

Usage: python devtools/ga_heldout.py [--budget 0.15]
Dev tool only.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from defines import Defines                       # noqa: E402
from ga_tuning import play_game, BASELINE, MAX_TURNS  # noqa: E402

CHAMPION = [2.21, 7.87, 35.73, 91.74, 377.0]
SEEDS = [990001 + i * 7919 for i in range(5)]


def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--budget", type=float, default=0.15)
    args = ap.parse_args()

    w = d = l = 0
    points = 0.0
    print(f"held-out evaluation: champion vs baseline, {len(SEEDS)} unseen "
          f"seeds x both colours, {args.budget}s/move")
    for seed in SEEDS:
        for black, white, champ_color in ((CHAMPION, BASELINE, "B"),
                                          (BASELINE, CHAMPION, "W")):
            winner, turns = play_game(black, white, args.budget, seed)
            me = Defines.BLACK if champ_color == "B" else Defines.WHITE
            if winner == me:
                pts = 2.0 + 0.5 * (1.0 - turns / MAX_TURNS)
                res = "WIN"
                w += 1
            elif winner in (0, -1):
                pts = 1.0
                res = "draw"
                d += 1
            else:
                pts = 0.2 * turns / MAX_TURNS
                res = "loss"
                l += 1
            points += pts
            print(f"  seed {seed} champion as {champ_color}: {res:4s} "
                  f"(turn {turns:3d}, {pts:.2f} pts)", flush=True)
    print(f"\nRECORD: {w}-{d}-{l}   held-out fitness: {points:.2f} "
          f"(theoretical max 15, all-draw 6)")


if __name__ == "__main__":
    main()

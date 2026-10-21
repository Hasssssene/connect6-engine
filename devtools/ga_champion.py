"""
ga_champion.py -- fair final selection among the GA's generation champions.

The GA's per-generation fitness uses fresh randomized openings, so scores
are not comparable across generations (seed noise). This script collects
each generation's best genome from ga_run_history.json and re-evaluates
all of them against the SAME baseline on a common fixed seed set; the
winner is the champion that gets baked into the engine.

Usage:
    python devtools/ga_champion.py --history ga_run_history.json \
        --seeds 3 --budget 0.15 --out ga_champion.json
"""

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ga_tuning import fitness_of, BASELINE, GENES  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--history", default="ga_run_history.json")
    ap.add_argument("--seeds", type=int, default=3,
                    help="common opening seeds (x2 colours per seed)")
    ap.add_argument("--budget", type=float, default=0.15)
    ap.add_argument("--seed-base", type=int, default=424242)
    ap.add_argument("--out", default="ga_champion.json")
    args = ap.parse_args()

    with open(args.history) as f:
        hist = json.load(f)

    # unique generation champions (rounded to avoid near-duplicates)
    seen = set()
    candidates = []
    for h in hist:
        key = tuple(round(g, 2) for g in h["best_genome"])
        if key not in seen:
            seen.add(key)
            candidates.append((h["gen"], h["best_genome"]))

    common_seeds = [args.seed_base + i * 1337 for i in range(args.seeds)]

    results = []
    print(f"re-evaluating {len(candidates)} champions + baseline on "
          f"{len(common_seeds)} common seeds ({args.seeds * 2} games each)")
    for gen, genome in candidates:
        f = fitness_of(genome, BASELINE, args.budget, common_seeds)
        results.append((f, gen, genome))
        print(f"  gen {gen:2d} champion [{', '.join(f'{x:.1f}' for x in genome)}]"
              f" -> fitness {f:5.2f}", flush=True)

    # baseline reference under the same seeds (self-play -> ~2.0 per game pair
    # ... actually self-play wins both ways; just report for context)
    base_f = fitness_of(BASELINE, BASELINE, args.budget, common_seeds)
    print(f"  baseline self-play reference: {base_f:.2f} (inflated by definition)")

    results.sort(key=lambda t: -t[0])
    champ_f, champ_gen, champ = results[0]
    print(f"\nCHAMPION: gen {champ_gen} genome "
          f"[{', '.join(f'{x:.2f}' for x in champ)}] fitness {champ_f:.2f}")

    if args.out:
        with open(args.out, "w") as f:
            json.dump(dict(champion=champ, fitness=champ_f,
                           source_generation=champ_gen,
                           baseline=BASELINE,
                           results=[dict(gen=g, fitness=round(fv, 3), genome=list(gn))
                                    for fv, g, gn in results]), f, indent=1)
        print("wrote", args.out)


if __name__ == "__main__":
    main()

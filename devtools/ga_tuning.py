"""
ga_tuning.py -- evolutionary optimisation of the evaluation weights (v4).

Genome (5 genes): [w1, w2, w3, w4, threat]
  w1..w4   FEATURE_WEIGHTS buckets F1..F4 (live windows with 1/2/3/>=4 own
           stones) -- the GA-ready parameter vector designed in v3
  threat   search_engine.THREAT_WEIGHT (root pair-scoring weight per threat)

Fitness: each individual plays 2 head-to-head games IN-PROCESS against the
BASELINE configuration (v3.1 hand-tuned weights), one per colour, from
fresh randomized openings (engines are deterministic; random openings give
the population varied positions every generation).

  win   -> 2.0 + 0.5 * (1 - turns/max_turns)   (faster wins score higher)
  draw  -> 1.0
  loss  -> 0.2 * turns/max_turns               (longer resistance scores higher)

Weights are injected by swapping module globals (evaluation.FEATURE_WEIGHTS,
search_engine.THREAT_WEIGHT) before each side's turn -- turn-based play
makes this safe with a single thread.

Operators: tournament selection (k=2), blend crossover, per-gene Gaussian
mutation, sort-repair of w1..w4 (concentration must be monotone), elitism 2,
bounds clipping. Logs per-generation fitness to CSV/JSON; optionally plots.

Usage:
    python devtools/ga_tuning.py --gens 10 --pop 8 --budget 0.2
    python devtools/ga_tuning.py --plot ga_history.json --out fig.png
Dev tool only -- best weights are baked into the sources afterwards.
"""

import argparse
import csv
import json
import os
import random
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import evaluation                    # noqa: E402
import search_engine                 # noqa: E402
from defines import Defines, StoneMove  # noqa: E402
from tools import init_board, make_move, is_win_by_premove  # noqa: E402
from search_engine import SearchEngine  # noqa: E402

# gene: (name, low, high, init)
GENES = [
    ("w1", 0.5, 6.0, 2.0),
    ("w2", 2.0, 24.0, 8.0),
    ("w3", 8.0, 96.0, 30.0),
    ("w4", 32.0, 384.0, 120.0),
    ("threat", 100.0, 800.0, 350.0),
]
BASELINE = [g[3] for g in GENES]     # v3.1 hand-tuned configuration
MAX_TURNS = 100


# ---------------------------------------------------------------------------
# In-process game
# ---------------------------------------------------------------------------

def _rand_opening(board, rng):
    """Place a slightly randomized opening: black centre+jitter, white reply."""
    cx = 10 + rng.randint(-2, 2)
    cy = 10 + rng.randint(-2, 2)

    def near(x, y):
        while True:
            nx = x + rng.randint(-2, 2)
            ny = y + rng.randint(-2, 2)
            if 1 <= nx <= 19 and 1 <= ny <= 19 and board[nx][ny] == Defines.NOSTONE \
               and (nx, ny) != (x, y):
                return nx, ny

    b = StoneMove()
    b.positions[0].x = b.positions[1].x = cx
    b.positions[0].y = b.positions[1].y = cy
    make_move(board, b, Defines.BLACK)

    w1 = near(cx, cy)
    w2 = near(cx, cy)
    while w2 == w1:
        w2 = near(cx, cy)
    w = StoneMove()
    w.positions[0].x, w.positions[0].y = w1
    w.positions[1].x, w.positions[1].y = w2
    make_move(board, w, Defines.WHITE)
    return w                         # last move (white played)


def _engine_move(board, color, genome, last_move, budget):
    evaluation.FEATURE_WEIGHTS = (0.0, genome[0], genome[1], genome[2], genome[3])
    search_engine.THREAT_WEIGHT = genome[4]
    se = SearchEngine()
    se.before_search(board, color, 1)
    best = StoneMove()
    dummy = StoneMove()
    if last_move is not None:
        dummy = last_move
    se.alpha_beta_search(budget, Defines.MININT, Defines.MAXINT, color, best, dummy)
    return best


def play_game(genome_a, genome_b, budget, seed, max_turns=MAX_TURNS):
    """genome_a plays BLACK, genome_b WHITE. Returns (winner, turns)."""
    rng = random.Random(seed)
    board = [[0] * Defines.GRID_NUM for _ in range(Defines.GRID_NUM)]
    init_board(board)
    last = _rand_opening(board, rng)
    turns = 2

    while turns < max_turns:
        color = Defines.BLACK if turns % 2 == 0 else Defines.WHITE
        genome = genome_a if color == Defines.BLACK else genome_b
        mv = _engine_move(board, color, genome, last, budget)
        for p in mv.positions:                   # sanity: legal cells
            if board[p.x][p.y] != Defines.NOSTONE:
                return (Defines.WHITE if color == Defines.BLACK else Defines.BLACK), turns
        make_move(board, mv, color)
        last = mv
        turns += 1
        if is_win_by_premove(board, mv):
            return color, turns
        full = all(board[x][y] != Defines.NOSTONE
                   for x in range(1, 20) for y in range(1, 20))
        if full:
            return 0, turns
    return -1, turns                              # undecided


# ---------------------------------------------------------------------------
# GA
# ---------------------------------------------------------------------------

def clamp(i, low, high):
    return max(low, min(high, i))


def repair(genome):
    g = list(genome)
    g[0:4] = sorted(g[0:4])                       # monotone concentration
    for i, (_, lo, hi, _) in enumerate(GENES):
        g[i] = clamp(g[i], lo, hi)
    return g


def random_individual(rng, around=None, spread=0.5):
    if around is None:
        return repair([rng.uniform(lo, hi) for _, lo, hi, _ in GENES])
    g = []
    for i, (_, lo, hi, init) in enumerate(GENES):
        base = around[i]
        sigma = (hi - lo) * spread * 0.25
        g.append(clamp(rng.gauss(base, sigma), lo, hi))
    return repair(g)


def crossover(p1, p2, rng):
    alpha = [rng.random() for _ in GENES]
    child = [a * x + (1 - a) * y for a, x, y in zip(alpha, p1, p2)]
    return repair(child)


def mutate(genome, rng, prob=0.35):
    g = list(genome)
    for i, (_, lo, hi, _) in enumerate(GENES):
        if rng.random() < prob:
            g[i] = clamp(rng.gauss(g[i], (hi - lo) * 0.12), lo, hi)
    return repair(g)


def fitness_of(genome, baseline, budget, seeds):
    f = 0.0
    for si, seed in enumerate(seeds):
        for ci, (black, white) in enumerate(((genome, baseline), (baseline, genome))):
            gseed = seed * 977 + si * 31 + ci
            winner, turns = play_game(black, white, budget, gseed)
            me = Defines.BLACK if black is genome else Defines.WHITE
            if winner == me:
                f += 2.0 + 0.5 * (1.0 - turns / MAX_TURNS)
            elif winner == 0 or winner == -1:
                f += 1.0
            else:
                f += 0.2 * turns / MAX_TURNS
    return f


def run_ga(pop_size, gens, budget, out_prefix, seed=7):
    rng = random.Random(seed)
    baseline = list(BASELINE)
    # NOTE: the population must NOT contain the exact baseline genome:
    # baseline-vs-baseline self-play inflates fitness ("me" wins every
    # decisive game by definition), which elitism would lock in forever.
    # The baseline appears only as the fixed opponent.
    pop = [random_individual(rng, around=baseline) for _ in range(pop_size - 1)]
    pop.append(random_individual(rng))           # one fully random explorer

    history = []
    t0 = time.time()
    for gen in range(1, gens + 1):
        seeds = [rng.randrange(1, 10 ** 6) for _ in range(2)]
        scored = []
        for ind in pop:
            f = fitness_of(ind, baseline, budget, seeds)
            scored.append((f, ind))
        scored.sort(key=lambda t: -t[0])
        fits = [f for f, _ in scored]
        best_f, best_g = scored[0]
        mean_f = sum(fits) / len(fits)
        history.append(dict(gen=gen, best=best_f, mean=mean_f,
                            worst=min(fits), baseline_ref=2.0,
                            best_genome=list(best_g)))
        print(f"gen {gen:2d}/{gens} | best {best_f:5.2f} | mean {mean_f:5.2f} | "
              f"worst {min(fits):5.2f} | best genome "
              f"[{', '.join(f'{x:.1f}' for x in best_g)}] | "
              f"{time.time() - t0:6.0f}s", flush=True)

        # next generation: elitism + tournament + crossover + mutation
        elite = [list(g) for _, g in scored[:2]]
        nxt = elite[:]
        while len(nxt) < pop_size:
            p1 = max(rng.sample(scored, 2), key=lambda t: t[0])[1]
            p2 = max(rng.sample(scored, 2), key=lambda t: t[0])[1]
            child = crossover(list(p1), list(p2), rng) if rng.random() < 0.8 \
                else list(p1)
            nxt.append(mutate(child, rng))
        pop = nxt

    if out_prefix:
        with open(out_prefix + "_history.json", "w") as f:
            json.dump(history, f, indent=1)
        with open(out_prefix + "_history.csv", "w", newline="") as f:
            w = csv.writer(f)
            w.writerow(["gen", "best", "mean", "worst"])
            for h in history:
                w.writerow([h["gen"], h["best"], h["mean"], h["worst"]])
        with open(out_prefix + "_best.json", "w") as f:
            json.dump(dict(genome=history[-1]["best_genome"],
                           fitness=history[-1]["best"],
                           baseline=baseline), f, indent=1)

    best = history[-1]["best_genome"]
    print("\nFINAL BEST:", [round(x, 2) for x in best],
          "fitness", round(history[-1]["best"], 2))
    print("BASELINE :", baseline)
    return best


def plot_history(history_path, out_png):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    with open(history_path) as f:
        hist = json.load(f)
    gens = [h["gen"] for h in hist]
    plt.figure(figsize=(7, 4))
    plt.plot(gens, [h["best"] for h in hist], "o-", label="best")
    plt.plot(gens, [h["mean"] for h in hist], "s--", label="mean")
    plt.plot(gens, [h["worst"] for h in hist], "^:", label="worst")
    plt.axhline(2.0, color="gray", lw=1, label="baseline (self-play)")
    plt.xlabel("generation")
    plt.ylabel("fitness (2 games vs baseline, both colours)")
    plt.title("GA evolution of evaluation weights (v4)")
    plt.legend()
    plt.grid(alpha=0.3)
    plt.tight_layout()
    plt.savefig(out_png, dpi=150)
    print("wrote", out_png)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--gens", type=int, default=10)
    ap.add_argument("--pop", type=int, default=8)
    ap.add_argument("--budget", type=float, default=0.2,
                    help="seconds per move in fitness games")
    ap.add_argument("--out", default=None, help="output prefix (json/csv)")
    ap.add_argument("--plot", default=None, help="plot existing history JSON")
    ap.add_argument("--plot-out", default="ga_fitness.png")
    args = ap.parse_args()

    if args.plot:
        plot_history(args.plot, args.plot_out)
        return

    prefix = args.out or os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "ga_run")
    run_ga(args.pop, args.gens, args.budget, prefix)


if __name__ == "__main__":
    main()

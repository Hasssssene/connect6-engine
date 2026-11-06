================================================================================
CONNECT6 GAME ENGINE - DELIVERY BUNDLE
Authors:   Hassene Bouamama · Ayoub Charchaoui
Engine:    v4 (final) - registered name "TIA.Connect6"
Course:    Practica 1, Grado en Ingenieria Informatica, University of Alicante
================================================================================

CONTENTS
--------
  Connect6_Game_Engine_Report.pdf   Full project report (27 pages): architecture,
                                    ML-trained heuristics, experiments, evidence map.
  main                              Linux executable (built on Ubuntu 24.04 LTS,
                                    PyInstaller onefile, ~7.5 MB, pure ELF).
  connect6-engine-source.zip        Complete source code + development tools +
                                    Linux build scripts.
  requirements.txt                  Python requirements (the engine itself is pure
                                    standard library; pyinstaller is only needed
                                    to package it).
  evidence/                         Raw artefacts (transcripts, logs, plots) backing
                                    every result reported in the document.
  README.txt                        This file.

QUICK START - LINUX EXECUTABLE
------------------------------
    chmod +x main
    ./main

The engine speaks the course text protocol on stdin/stdout; the course GUI
launches it the same way and pipes the identical commands.

QUICK START - FROM SOURCE (any OS with Python 3.10+)
----------------------------------------------------
    python main.py                 # run directly, no build step needed
    pip install pyinstaller        # only if you want a standalone executable
    pyinstaller --onefile main.py  # -> dist/main (Linux) or dist/main.exe (Windows)

On Ubuntu the one-command build + self-test is:  bash build.sh
(see README_for_lab.txt for details).

TEXT PROTOCOL (what the engine accepts)
---------------------------------------
    name        - print the name of the engine ("name TIA.Connect6").
    print       - print the board.
    black XXXX  - place the black stones on position XXXX.
    white XXXX  - place the white stones on position XXXX.
    next        - the engine searches and plays its next move.
    move XXXX   - tell the engine the opponent played XXXX, then search.
    new black   - start a new game, engine plays Black.
    new white   - start a new game, engine plays White.
    depth d     - set the per-turn TIME LIMIT in seconds (statement 5.10;
                  default 6). The engine searches iteratively deeper and
                  stops when the budget is exhausted.
    help        - print the command list.
    exit / quit - quit the game.

A position XXXX is given as letters A-S: one square = column letter + row
letter (19x19 board, e.g. "JJ" = column J, row J), and a move = two squares
(4 letters, e.g. "ASBS" = squares AS and BS), except Black's very first turn
which places a single stone (2 letters).
Example session:

    new black
    black JJ          (opponent's opening stone)
    next              (engine replies "move XXXXYYYY" with its two stones)

Debug extras (not part of the course protocol): vcf, unvcf - threat-layer
diagnostics used during development.

EVIDENCE FOLDER
---------------
Every number in the report is backed by a raw artefact here, named by date.
The mapping table from reported results to files is in the report appendix
(Section 6, "Evidence map"). Additional transcripts in evidence/ back the
remaining match records cited in Section 4 (version head-to-heads, the GA
held-out evaluation, the full position battery, evaluation-cost benchmark).

SOURCE ZIP
----------
  main.py            entry point (protocol loop)
  game_engine.py     command handling, board state, win/draw detection
  search_engine.py   iterative-deepening alpha-beta search (v2+)
  threats.py         exact threat-window counting (Wu-Huang lemma, v3+)
  evaluation.py      incremental window-bucket evaluation (F1-F8) with the
                     GA-optimised weight vector (v4)
  defines.py, tools.py   board constants and helpers
  ga_champion.json   the evolved weight genome baked into the v4 evaluation
  ga_run_*.{json,csv}    GA run history (backs Figure 5)
  devtools/          every experiment in the report: headless_match.py,
                     tournament.py, battery_versions.py, preset_check.py,
                     ga_tuning.py, ga_heldout.py, measure_rss.py,
                     benchmark.py, benchmark_eval.py, test_threats.py,
                     test_draw.py, gui_capture.py
  build.sh, verify.sh   one-command Linux build + smoke/verification tests

Engine version history (each plays its colour in the report's matches):
  v0 skeleton -> v1 minimax -> v2 alpha-beta + time budget -> v3 exact threat
  layer -> v4 evolutionary-tuned evaluation weights (delivered version).
================================================================================

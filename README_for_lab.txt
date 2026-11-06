CONNECT6 ENGINE - REBUILDING THE LINUX EXECUTABLE ON UBUNTU
===========================================================

The delivery already contains the built Linux executable (file "main" in the
bundle root, built and smoke-tested on Ubuntu 24.04 LTS). This note is only
needed if you want to rebuild it from source on a lab PC or any Ubuntu machine.

WHAT YOU NEED
-------------
- Python 3 (python3); no admin rights required.
- Network access once, for a single pip install (pyinstaller).
- ~5-10 minutes.

STEPS
-----
1. Unzip connect6-engine-source.zip anywhere and open a terminal in the folder.
2. Run:

       bash build.sh

   The script:
     - installs pyinstaller (venv preferred, --user fallback),
     - builds the executable as dist/main (PyInstaller onefile),
     - runs a protocol smoke test (expects "name TIA.Connect6" and a legal
       move within a 1 s budget) and prints "SMOKE TEST: PASS",
     - additionally plays one verification game against the course engine
       cloudict.linux if the course GUI folder (Connect6GUI-master) is next
       to the source folder (optional, skipped otherwise).
3. The full record is written to build_log.txt; the game transcript (if the
   verification match ran) to verify_match.txt.

VERIFYING THE DELIVERED BINARY INSTEAD
--------------------------------------
To smoke-test the already-built "main" from the bundle without rebuilding:

    chmod +x main
    printf 'name\ndepth 1\nblack JJ\nnext\nexit\n' | ./main

Expected: the reply "name TIA.Connect6" followed by a "move ..." line.

IF SOMETHING FAILS
------------------
- "python3 not found": try python3.10 / python3.11 / python3.12 explicitly.
- pip blocked or venv unavailable: build.sh automatically falls back to
  `pip3 install --user`; the log shows which path it took.
- PyInstaller errors: check build_log.txt - it contains the full trace.

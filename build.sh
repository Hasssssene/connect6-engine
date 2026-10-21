#!/usr/bin/env bash
# ============================================================================
# Connect6 engine -- one-command build + self-test for Ubuntu lab PCs.
#
# Usage:   bash build.sh
# Output:  dist/main  (the Linux executable to deliver)
#          build_log.txt (bring this back)
#
# No network needed beyond pip (pyinstaller); works with venv OR --user pip
# if the PC has no python3-venv / admin rights.
# ============================================================================
set -u
cd "$(dirname "$0")"

LOG=build_log.txt
STATUS=OK

note() { echo; echo "=== $* ==="; }

{
note "Connect6 engine build"
date
bash --version | head -1
lsb_release -a 2>/dev/null || echo "(lsb_release not available)"
ldd --version 2>/dev/null | head -1 || echo "(ldd not available)"
python3 --version 2>&1 || { echo "FAIL: python3 not found"; exit 1; }

# ---- 1) install pyinstaller (venv preferred, --user fallback) -------------
note "installing pyinstaller"
PYBIN=python3
if python3 -m venv .venv 2>/dev/null && [ -x .venv/bin/python ]; then
    echo "using virtual environment .venv"
    .venv/bin/pip install --quiet --upgrade pip
    .venv/bin/pip install --quiet pyinstaller || { echo "FAIL: pip install (venv)"; exit 1; }
    PIPINSTALL=".venv/bin/pyinstaller"
else
    echo "venv unavailable -> trying pip3 --user (no admin needed)"
    python3 -m pip install --user --quiet pyinstaller || \
        pip3 install --user --quiet pyinstaller || { echo "FAIL: pip install (--user)"; exit 1; }
    USERBASE=$(python3 -m site --user-base)
    export PATH="$PATH:$USERBASE/bin"
    PIPINSTALL="python3 -m PyInstaller"
fi
$PIPINSTALL --version || { echo "FAIL: pyinstaller not runnable"; exit 1; }

# ---- 2) build --------------------------------------------------------------
note "building dist/main (pyinstaller --onefile)"
$PIPINSTALL --onefile --noconfirm main.py || { echo "FAIL: build"; exit 1; }
ls -la dist/main || { echo "FAIL: dist/main missing"; exit 1; }
file dist/main 2>/dev/null || true

# ---- 3) protocol smoke test -------------------------------------------------
note "smoke test (1s budget)"
printf 'name\ndepth 1\nblack JJ\nnext\nexit\n' | ./dist/main > smoke_out.txt 2>&1
echo "--- engine output (first 40 lines) ---"
head -40 smoke_out.txt
echo "--------------------------------------"
if grep -q "name TIA.Connect6" smoke_out.txt && grep -q "^move " smoke_out.txt; then
    echo "SMOKE TEST: PASS (name reply + legal move found)"
else
    echo "SMOKE TEST: FAIL (see smoke_out.txt)"
    STATUS=SMOKE_FAILED
fi

# ---- 4) optional verification match (needs ../Connect6GUI-master) ----------
if [ -x ../Connect6GUI-master/engines/cloudict.linux ] || [ -f ../Connect6GUI-master/engines/cloudict.linux ]; then
    note "verification match vs cloudict.linux (optional)"
    chmod +x ../Connect6GUI-master/engines/cloudict.linux 2>/dev/null
    python3 devtools/headless_match.py \
        --black dist/main \
        --white ../Connect6GUI-master/engines/cloudict.linux \
        --depth 4 --out verify_match.txt && echo "verify_match.txt written" \
        || echo "verification match failed (non-fatal)"
else
    echo
    echo "(cloudict.linux not found -- skipping verification match; run verify.sh if needed)"
fi

note "DONE: $STATUS"
echo "Bring back: build_log.txt, smoke_out.txt, verify_match.txt (if present), dist/main"
} 2>&1 | tee "$LOG"

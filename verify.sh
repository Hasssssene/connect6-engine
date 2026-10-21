#!/usr/bin/env bash
# Verification only: play one headless match against cloudict.linux.
# (build.sh runs this automatically when the GUI folder is present;
#  use this script separately if you skipped it.)
set -u
cd "$(dirname "$0")"
chmod +x ../Connect6GUI-master/engines/cloudict.linux 2>/dev/null
python3 devtools/headless_match.py \
    --black dist/main \
    --white ../Connect6GUI-master/engines/cloudict.linux \
    --depth 4 --out verify_match.txt
echo "wrote verify_match.txt"

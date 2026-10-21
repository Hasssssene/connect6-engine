"""
gui_capture.py -- automated GUI evidence capture (screenshots).

Launches the ConnectMore Tkinter GUI with both engines wired up
programmatically (no click-through needed), runs an AI-vs-AI game with
result dialogs suppressed, and captures periodic screenshots of the
window to PNG files for the report.

Usage (from Connect6Engine-master/):
    python devtools/gui_capture.py --black dist/main.exe \
        --white ../Connect6GUI-master/engines/cloudict.exe \
        --out ../connect6-vault/05-Report/assets/2026-10-21_gui_v4_vs_cloudict \
        --interval 15 --max-shots 30

Notes:
- a GUI window will appear on screen while capturing (the session must be
  unlocked and the window not minimized);
- file dialogs and message boxes are stubbed so nothing blocks automation;
- the PNGs land directly in the vault assets folder.

Dev tool only -- not part of the delivered engine.
"""

import argparse
import os
import sys
import time

GUI_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                       '..', '..', 'Connect6GUI-master')
sys.path.insert(0, GUI_DIR)

# Stub dialogs BEFORE the GUI modules load their references.
import tkinter.filedialog as _fd  # noqa: E402
import tkinter.messagebox as _mb  # noqa: E402

_last_file_dialog = {"path": None}


def _fake_askopenfilename(**kw):
    return _last_file_dialog["path"] or ""


def _fake_asksaveasfile(**kw):
    import io
    return io.StringIO()


_fd.askopenfilename = _fake_askopenfilename
_fd.asksaveasfile = _fake_asksaveasfile
_mb.showinfo = lambda *a, **k: None

from tkinter import Tk  # noqa: E402
import ConnectMore  # noqa: E402
from engine import Move  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--black", required=True)
    ap.add_argument("--white", required=True)
    ap.add_argument("--out", required=True, help="output prefix for PNG shots")
    ap.add_argument("--level", type=int, default=4, help="AI level (depth 4/5/6)")
    ap.add_argument("--interval", type=float, default=15.0, help="seconds between shots")
    ap.add_argument("--max-shots", type=int, default=30)
    ap.add_argument("--max-seconds", type=float, default=900.0)
    args = ap.parse_args()

    # resolve relative paths BEFORE switching CWD to the GUI directory
    args.out = os.path.abspath(args.out)
    args.black = os.path.abspath(args.black)
    args.white = os.path.abspath(args.white)

    from PIL import ImageGrab  # after stubs; pillow is a dev dependency

    os.chdir(GUI_DIR)               # GUI loads imgs/ and engines/ relatively

    root = Tk()
    app = ConnectMore.App(root)
    app.master.title("Connect6 engine test capture")

    # Wire engines programmatically instead of the load dialogs.
    app.botPlayerBlack.path = args.black
    _last_file_dialog["path"] = args.black
    app.initGameEngine(app.botPlayerBlack, Move.BLACK)
    app.botPlayerBlack.release()
    app.setBlackBot()

    app.botPlayerWhite.path = args.white
    _last_file_dialog["path"] = args.white
    app.initGameEngine(app.botPlayerWhite, Move.WHITE)
    app.botPlayerWhite.release()
    app.setWhiteBot()

    app.aiLevel.set(args.level)
    app.vcf.set(1)

    state = {"shots": 0, "t0": time.time(), "done": False}

    def window_bbox():
        root.update_idletasks()
        x = root.winfo_rootx()
        y = root.winfo_rooty()
        w = root.winfo_width()
        h = root.winfo_height()
        return (max(0, x - 8), max(0, y - 32), x + w + 8, y + h + 8)

    def snap(final=False):
        try:
            img = ImageGrab.grab(bbox=window_bbox())
            tag = "final" if final else f"{state['shots']:02d}"
            path = f"{args.out}_{tag}.png"
            img.save(path)
            print("saved", path, flush=True)
        except Exception as e:
            print("capture failed:", e, flush=True)

    def tick():
        if state["done"]:
            return
        elapsed = time.time() - state["t0"]
        if app.gameState in (ConnectMore.GameState.Win, ConnectMore.GameState.Draw):
            snap(final=True)
            state["done"] = True
            print("game over -- closing in 5s", flush=True)
            root.after(5000, root.destroy)
            return
        snap()
        state["shots"] += 1
        if state["shots"] >= args.max_shots or elapsed >= args.max_seconds:
            snap(final=True)
            state["done"] = True
            root.after(2000, root.destroy)
            return
        root.after(int(args.interval * 1000), tick)

    app.showDisplayMsg = False
    root.after(1500, tick)          # let the first moves appear
    app.newSingleGame()
    root.mainloop()
    print("done:", state["shots"], "shots")


if __name__ == "__main__":
    main()

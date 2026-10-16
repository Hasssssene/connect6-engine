from game_engine import GameEngine
import sys

def main():
    gameEngine = GameEngine('TIA.Connect6')
    gameEngine.run()
    # The GUI terminates us by closing pipes / killing the bootloader parent.
    # Suppress interpreter-shutdown flushes to already-closed pipes so the
    # executable never emits spurious errors on exit (error-free requirement).
    try:
        sys.stdout.flush()
    except Exception:
        pass
    sys.stdout = None
    sys.stderr = None

if __name__ == "__main__":
    main()

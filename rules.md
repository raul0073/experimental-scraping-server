# Rules

_Working agreements for this project. Filled as we go._

1. **`progress.md` is always up to date** — every work session updates what's done and what's next before it ends.
2. **Stage gates are real** — a stage's gate must pass (and be shown passing) before the next stage starts.
3. **No retroactive picks** — predictions are written to the ledger before results exist; backtests are walk-forward only (no data from the future of the predicted match).
4. **No DB** — files on disk; SQLite is the only permitted upgrade path if ever needed.
5. **Calibrate, don't hand-tune** — model constants (xG scaling, home advantage, decay rate) are fit against real results, never guessed and left.

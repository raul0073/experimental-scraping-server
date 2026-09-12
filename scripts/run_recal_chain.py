"""Full recalibration chain after a form-model change, then the second-season
backtest. Sequential; each step's tail is logged.

    calibrate (24/25) -> retrain classifier (11s) -> backtest 25/26
    -> zone blend -> backtest 24/25 (hold-out params fit on 23/24)
"""
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

PY = str(Path(".venv/Scripts/python.exe"))


def run(name, cmd):
    print(f"===== {name} =====", flush=True)
    r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    print(r.stdout[-3500:], flush=True)
    if r.returncode != 0:
        print(f"STEP {name} FAILED rc={r.returncode}\n{r.stderr[-2000:]}", flush=True)
        raise SystemExit(1)


def main() -> int:
    run("calibrate", [PY, "scripts/calibrate_model.py"])

    print("===== retrain-classifier =====", flush=True)
    from models.fbref.fbref_types import LEAGUE_NAME_MAP
    from services.predictions.draw_model import DrawModel
    params = json.loads(Path("data/config/model_params.json").read_text(encoding="utf-8"))
    seasons = ["1415", "1516", "1617", "1718", "1819", "1920", "2021",
               "2122", "2223", "2324", "2425"]
    dm = DrawModel.train(list(LEAGUE_NAME_MAP), seasons, params)
    print("classifier n =", dm.w["train_n"], "nll =", dm.w["train_nll"], flush=True)

    run("backtest-2526", [PY, "scripts/backtest_2526.py"])
    run("zone-blend", [PY, "scripts/calibrate_zone_blend.py"])
    run("backtest-2425", [PY, "scripts/backtest_season.py", "--eval", "2425"])
    print("CHAIN DONE", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

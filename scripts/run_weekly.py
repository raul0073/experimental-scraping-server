"""The one weekly command: refresh data -> grade last week's picks ->
commit this week's picks.

Every step is non-fatal (preseason has empty sources); the summary at the
end says exactly what happened.

Usage (from repo root, ideally scheduled after the round completes):
    .venv\\Scripts\\python.exe scripts\\run_weekly.py
    .venv\\Scripts\\python.exe scripts\\run_weekly.py --start 2026-09-12 --no-refresh
"""
import argparse
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from models.fbref.fbref_types import LEAGUE_NAME_MAP

SEASON = "2627"
STAMP = Path(__file__).resolve().parent.parent / "data" / "reports" / "last_weekly_run.txt"


def step(label, fn):
    try:
        result = fn()
        print(f"OK   {label}: {result}", flush=True)
        return result
    except Exception as e:
        print(f"WARN {label}: {e}", flush=True)
        return None


def _backup_state():
    """Zip the crown jewels (ledger/history/slips/config) — the track record
    is the product's credibility. Keeps the last 10 archives."""
    import zipfile
    root = Path(__file__).resolve().parent.parent
    out_dir = root / "data" / "backups"
    out_dir.mkdir(parents=True, exist_ok=True)
    stampname = datetime.now().strftime("%Y%m%d_%H%M")
    out = out_dir / f"state_{stampname}.zip"
    n = 0
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        for sub in ("ledger", "history", "slips", "config"):
            for f in sorted((root / "data" / sub).glob("*")):
                if f.is_file():
                    z.write(f, f"{sub}/{f.name}")
                    n += 1
    old = sorted(out_dir.glob("state_*.zip"))
    for f in old[:-10]:
        f.unlink()
    return {"files": n, "archive": out.name, "kept": min(len(old), 10)}


def _notify(weekly):
    """Telegram summary of the new window (inert until telegram.json filled)."""
    from services.notify import send_telegram
    win = weekly.get("window") or {}
    lines = [f"⚽ Predictor — window {win.get('start')} → {win.get('end')}"]
    for p in weekly.get("draw_picks", []):
        lines.append(f"  X {p['home']} v {p['away']} ({p['pick_prob']:.0%}, "
                     f"be {1 / p['pick_prob']:.2f})")
    st = weekly.get("strategy") or {}
    slip = st.get("slip") or {}
    if slip:
        lines.append(f"🐒 {slip.get('title_he', '')} · {slip.get('lines', 0)} lines · "
                     f"P(profit) {slip.get('p_profit', 0):.0%}")
    golds = [b for lg, ps in (weekly.get("all_predictions") or {}).items() for b in ps
             if b.get("in_window") and b["confidence"] == "normal"
             and max(b["probabilities"].values()) >= 0.55
             and max(b["probabilities"], key=b["probabilities"].get) != "draw"]
    if golds:
        lines.append(f"🥇 {len(golds)} GOLD favorites (breakeven 1/p — bet only above it)")
    return send_telegram("\n".join(lines))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", type=str, default=None, help="window start date YYYY-MM-DD")
    ap.add_argument("--no-refresh", action="store_true", help="skip scraping, use data on disk")
    ap.add_argument("--if-stale-hours", type=float, default=None,
                    help="exit immediately if the last successful run is younger than this "
                         "(used by the desktop launcher; the daily task runs unconditionally)")
    args = ap.parse_args()

    if args.if_stale_hours is not None and STAMP.exists():
        try:
            age_h = (datetime.now() - datetime.fromisoformat(
                STAMP.read_text(encoding="utf-8").strip())).total_seconds() / 3600
            if age_h < args.if_stale_hours:
                print(f"FRESH: last full run {age_h:.1f}h ago (< {args.if_stale_hours}h) — nothing to do")
                return 0
        except ValueError:
            pass

    if not args.no_refresh:
        from services.fbref.fixtures.fixtures_service import FixturesService
        from services.understat.rosters_service import RostersService
        from services.understat.shot_events_service import ShotEventsService
        from services.understat.understat_service import UnderstatService
        for league in LEAGUE_NAME_MAP:
            step(f"fixtures {league}", lambda lg=league: FixturesService(lg, SEASON, refresh=True).build())
            step(f"understat map {league}", lambda lg=league: UnderstatService(lg, SEASON, refresh=True).learn_name_map())
            step(f"understat {league}", lambda lg=league: UnderstatService(lg, SEASON).build())
            step(f"understat players {league}", lambda lg=league: UnderstatService(lg, SEASON).build_players())
            step(f"shots {league}", lambda lg=league: ShotEventsService(lg, SEASON, refresh=True).build())
            step(f"rosters {league}", lambda lg=league: RostersService(lg, SEASON).build())
        from services.fbref.player_stats_service import FbrefPlayerStatsService
        for league in LEAGUE_NAME_MAP:
            step(f"fbref players {league}",
                 lambda lg=league: FbrefPlayerStatsService(lg, SEASON).build())

    from services.predictions.history_service import HistoryService
    from services.predictions.ledger_service import LedgerService
    step("grade ledger", LedgerService.grade)
    step("grade history", HistoryService.grade)

    from services.predictions.prediction_service import PredictionService
    weekly = step("generate picks", lambda: PredictionService().weekly_picks(args.start))
    if weekly:
        step("commit picks", lambda: LedgerService.commit(weekly))
        step("record history", lambda: HistoryService.record(weekly))
        from services.predictions.gold_ledger import GoldLedger
        from services.predictions.slip_ledger import SlipLedger
        step("grade slips", SlipLedger.grade)
        step("commit slip", lambda: SlipLedger.commit(weekly))
        step("grade gold", GoldLedger.grade)
        step("commit gold", lambda: GoldLedger.commit(weekly))
        step("notify", lambda: _notify(weekly))
        print("\n=== DRAW PICKS ===")
        for p in weekly["draw_picks"]:
            print(f"  {p['rank']}. [{p['league']}] {p['home']} v {p['away']}  "
                  f"P(draw)={p['pick_prob']:.0%}  xg={p['xg']}  {p['kickoff']}")
        print("=== HOME-WIN PICKS ===")
        for p in weekly["home_win_picks"]:
            print(f"  {p['rank']}. [{p['league']}] {p['home']} v {p['away']}  "
                  f"P(home)={p['pick_prob']:.0%}  xg={p['xg']}  {p['kickoff']}")
    def _season_sim():
        import simulate_season  # sibling script; scripts/ is sys.path[0]
        return simulate_season.run(sims=10000, verbose=False)
    step("season simulation", _season_sim)
    step("backup state", _backup_state)

    print("\n=== LEDGER ===")
    print(LedgerService.summary())

    STAMP.parent.mkdir(parents=True, exist_ok=True)
    STAMP.write_text(datetime.now().isoformat(timespec="seconds"), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

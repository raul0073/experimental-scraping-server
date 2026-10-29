"""The one weekly command: refresh data -> grade last week's picks ->
commit this week's picks.

Every step is non-fatal (preseason has empty sources); the summary at the
end says exactly what happened.

Usage (from repo root, ideally scheduled after the round completes):
    .venv\\Scripts\\python.exe scripts\\run_weekly.py
    .venv\\Scripts\\python.exe scripts\\run_weekly.py --start 2026-09-12 --no-refresh
"""
import argparse
import os
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from models.fbref.fbref_types import LEAGUE_NAME_MAP

# ---------------------------------------------------------------------------
# TEXT ENCODING — READ THIS BEFORE CHANGING IT.
#
# This machine's locale is cp1255 (Hebrew). cp1255 encodes Hebrew perfectly
# and CANNOT encode n-tilde, o-umlaut, e-acute or a-grave — which is to say
# it cannot encode the team names of four of the five leagues this pipeline
# builds. Python picks the locale encoding for stdout, so the moment any step
# printed "Koln" with its umlaut, or "Atletico" with its accent, the print
# itself raised UnicodeEncodeError.
#
# In run() that exception escaped from inside the `for line in p.stdout` loop
# — BEFORE the "-> ok / FAILED" line — so the step was recorded as ERROR and
# abandoned with no outcome printed and the child left mid-fetch. On
# 2026-10-12 that was `sources` and all five `events` steps: six steps with
# no result line in the log, a WhoScored event store three weeks stale for
# England, Spain and Germany, and every rating, payload and page after them
# computed on events from September. The daily appeared to run fine and
# published stale data, every single day.
#
# Two fixes, because one is not enough:
#   1. this process writes utf-8 and never dies on a character;
#   2. CHILD_ENV forces the same on every child, so a step cannot die the
#      way the parent just stopped dying.
# errors="replace" is deliberate: a mangled character in a log line must
# never be able to abort a scrape again.
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):       # not a reconfigurable stream
        pass

CHILD_ENV = {**os.environ, "PYTHONUTF8": "1", "PYTHONIOENCODING": "utf-8"}


SEASON = "2627"
STAMP = Path(__file__).resolve().parent.parent / "data" / "reports" / "last_weekly_run.txt"


def _say(msg: str) -> None:
    """Print without ever being the reason a step fails — see the encoding
    note above. `understat map ESP-La Liga` and `understat map
    GER-Bundesliga` both died here on 2026-10-12, reporting a charmap error
    for n-tilde and o-umlaut while the work itself had succeeded."""
    try:
        print(msg, flush=True)
    except (UnicodeError, OSError):
        try:
            print(msg.encode("ascii", "replace").decode("ascii"), flush=True)
        except (UnicodeError, OSError):
            pass


def step(label, fn):
    try:
        result = fn()
        _say(f"OK   {label}: {result}")
        return result
    except Exception as e:
        _say(f"WARN {label}: {e}")
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
    ap.add_argument("--sources-only", action="store_true",
                    help="refresh the sources and stop, without grading, "
                         "predicting or simulating — lets the caller rebuild "
                         "the ratings the predictor depends on IN BETWEEN")
    # 🐛 WITHOUT THIS, --league MEANT NOTHING TO THE SOURCE REFRESH.
    # run_daily --league "ENG-Premier League" filtered only its OWN loops and
    # then shelled out to this script, which looped LEAGUE_NAME_MAP and
    # rebuilt fixtures, the Understat name map, Understat, players, shots,
    # rosters, fbref players and injuries for ALL FIVE LEAGUES — 40 source
    # builds, several of them with refresh=True, to collect the handful of
    # English matches played yesterday. That is why an "England only" daily
    # sat in its first step for over ten minutes.
    ap.add_argument("--league", action="append", dest="leagues",
                    help="restrict the source refresh to these leagues "
                         "(repeatable); default is all of them")
    ap.add_argument("--if-stale-hours", type=float, default=None,
                    help="exit immediately if the last successful run is younger than this "
                         "(used by the desktop launcher; the daily task runs unconditionally)")
    args = ap.parse_args()

    # One list, used by every source loop below. LEAGUE_NAME_MAP stays the
    # default so nothing that called this without --league changes behaviour.
    refresh_leagues = [lg for lg in LEAGUE_NAME_MAP
                       if not args.leagues or lg in args.leagues]

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
        for league in refresh_leagues:
            step(f"fixtures {league}", lambda lg=league: FixturesService(lg, SEASON, refresh=True).build())
            step(f"understat map {league}", lambda lg=league: UnderstatService(lg, SEASON, refresh=True).learn_name_map())
            step(f"understat {league}", lambda lg=league: UnderstatService(lg, SEASON).build())
            step(f"understat players {league}", lambda lg=league: UnderstatService(lg, SEASON).build_players())
            step(f"shots {league}", lambda lg=league: ShotEventsService(lg, SEASON, refresh=True).build())
            step(f"rosters {league}", lambda lg=league: RostersService(lg, SEASON).build())
        from services.fbref.player_stats_service import FbrefPlayerStatsService
        for league in refresh_leagues:
            step(f"fbref players {league}",
                 lambda lg=league: FbrefPlayerStatsService(lg, SEASON).build())
        # Absentees for the fixtures about to be played. One preview page per
        # upcoming match — about fifty across the five leagues — and it is
        # genuinely pre-match information, published before kickoff rather
        # than read off a team sheet afterwards. Safe to run daily; each run
        # refreshes only the fixtures still ahead.
        # the window is the scraper's own constant — a second copy of the
        # number here is how it stayed at 7 after the scraper learned better
        from scripts.scrape_injuries import DAYS as INJURY_DAYS
        from scripts.scrape_injuries import run as scrape_injuries
        for league in refresh_leagues:
            step(f"injuries {league}",
                 lambda lg=league: scrape_injuries(lg, SEASON, INJURY_DAYS))

    # SPLIT POINT. Everything above reads the outside world; everything below
    # depends on the RATINGS derived from it. The daily run stops here, fits
    # the Elo and the form/team layers on what was just fetched, and calls
    # this script again with --no-refresh so the predictions are made from
    # today's ratings rather than yesterday's. Without the split the layered
    # triplet is priced from an Elo table that has not seen last night's
    # results, which is a whole day of lag hidden inside a job whose entire
    # purpose is not being a day behind.
    if args.sources_only:
        print("\nsources refreshed — stopping before grading (--sources-only)")
        return 0

    from services.predictions.gold_ledger import GoldLedger
    from services.predictions.history_service import HistoryService
    from services.predictions.ledger_service import LedgerService
    from services.predictions.slip_ledger import SlipLedger
    # ALL THREE ledgers are graded before a slate is generated. The betting
    # window stays live while any row in any ledger is pending, and the gold
    # ledger used to be graded AFTER generate picks: a gold bet whose last
    # leg landed on 10-28 kept the 10-23 window booked through that run, and
    # the window only advanced on 10-29 - after eight of Serie A's ten
    # midweek fixtures had been played.
    step("grade ledger", LedgerService.grade)
    step("grade slips", SlipLedger.grade)
    step("grade gold", GoldLedger.grade)
    step("grade history", HistoryService.grade)

    from services.predictions.prediction_service import PredictionService
    weekly = step("generate picks", lambda: PredictionService().weekly_picks(args.start))
    if weekly:
        step("commit picks", lambda: LedgerService.commit(weekly))
        step("record history", lambda: HistoryService.record(weekly))
        step("commit slip", lambda: SlipLedger.commit(weekly))
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
    def _record_upcoming():
        """The public record is "what we said before kickoff" for EVERY
        fixture, not for the betting slate.

        record history above records weekly_picks' slate, and since 10-11
        that slate stays on the booked betting window while any bet is
        pending. Right for betting, fatal for the record: while the 10-23
        window was open nothing was recorded, the slip grader was broken
        from 10-07 to 10-23 so the window never moved, and the whole
        16-19 October round plus Serie A's midweek round went unrecorded
        in every league. The predictor page showed those calls live and
        then dropped the fixtures the moment they were played, because a
        played fixture is read back from this log.

        So: the soonest unplayed round per league, plus anything kicking
        off within three days (a midweek round butting against a weekend),
        predicted with the same model and recorded through the same
        record() - first recording wins, so nothing already recorded moves.
        """
        from datetime import date, timedelta
        svc = PredictionService()
        horizon = (date.today() + timedelta(days=3)).isoformat()
        preds = {}
        for league in svc.params["leagues"]:
            fx = svc.unplayed_fixtures(league)
            if not fx:
                continue
            soonest = min(fx, key=lambda m: (m["date"], m["week"]))
            chosen = [m for m in fx
                      if m["week"] == soonest["week"] or m["date"] <= horizon]
            preds[league] = svc.predict_fixtures(league, chosen)
        return HistoryService.record({"all_predictions": preds})
    step("record upcoming", _record_upcoming)
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

"""The whole flow, once: scrape, update, check, build, deploy, push.

    .venv/Scripts/python.exe scripts/publish.py

WHY THIS EXISTS. Updating the data and updating the site were two separate
things a human had to remember, and on 2026-10-06 that cost thirteen days:
a scheduled job refreshed England every morning while four other leagues sat
frozen, and the live site served whatever had last been uploaded by hand.
Three commands that must all happen, in order, with nobody checking — so
they are one command now, and it stops rather than publishing something
wrong.

THE ORDER, AND WHY IT IS THIS ORDER:

    1. UPDATE   run_daily, every league with enough history. No --league
                flag anywhere; the set is derived from disk so it can never
                be left pinned to one league by a forgotten argument.
    2. CHECK    the gate. Everything below only runs if the payloads on disk
                are sane, because a deploy of bad data is worse than no
                deploy — the old site was at least correct.
    3. BUILD    pnpm build, then confirm the export carries what it should.
    4. DEPLOY   wrangler, to the live site.
    5. PUSH     git LAST, so the commit means "this is what is live" rather
                than "this is what I hoped to publish". A deploy that fails
                leaves the repo untouched and the working tree still holding
                the change, which is recoverable; the reverse is a commit
                claiming a deployment that never happened.

NOTHING IS SKIPPED SILENTLY. Each stage prints what it did and the summary
at the end says which ran, which were skipped and why. A stage that fails
stops the run and says what to look at.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
PY = str(ROOT / ".venv" / "Scripts" / "python.exe")
WEB = ROOT / "web"
PUB = WEB / "public" / "data"
OUT = WEB / "out"

from services.data_ready import ready_leagues                   # noqa: E402

# A league's payload losing more than this share of its size is treated as a
# half-written build rather than as news. Picked loose on purpose: a real
# day's change is a fraction of a percent, so anything near this is wrong.
SHRINK_LIMIT = 0.5


def slug(league: str) -> str:
    return league.lower().replace(" ", "-").replace("--", "-")


def run(label: str, args: list, cwd: Path = ROOT, shell: bool = False) -> bool:
    """One stage. Output streams live — a pipeline that hides its work is a
    pipeline nobody trusts, and this one is unattended by design."""
    print(f"\n{'=' * 70}\n{label}\n{'=' * 70}", flush=True)
    t0 = time.time()
    rc = subprocess.call(args, cwd=str(cwd), shell=shell)
    secs = time.time() - t0
    print(f"-> {'ok' if rc == 0 else f'FAILED (exit {rc})'} in {secs / 60:.1f} min",
          flush=True)
    return rc == 0


# ---------------------------------------------------------------------------
# the gate
# ---------------------------------------------------------------------------
def sizes_before() -> dict:
    """Payload sizes as they are now, to compare against after the update."""
    out = {}
    for p in PUB.rglob("*.json"):
        try:
            out[str(p.relative_to(PUB))] = p.stat().st_size
        except OSError:
            pass
    return out


def check(before: dict) -> list:
    """Everything that would make a deploy worse than no deploy.

    Returns a list of complaints; empty means publish. Each check exists
    because of a way this has actually gone wrong, or could go wrong
    silently — a deploy that looks fine and serves nothing is the failure
    mode worth paying for.
    """
    bad: list = []
    leagues = ready_leagues()
    if not leagues:
        return ["no league has enough event history — nothing to publish"]

    # 1. EVERY READY LEAGUE IS IN EVERY INDEX. Three separate builders write
    #    these, and all three have at some point written the file WHOLE and
    #    deleted the other leagues. That bug ships a site missing four fifths
    #    of its content and looks entirely normal until you open the dropdown.
    want = {slug(lg) for lg in leagues}
    for layer in ("team", "mental", "managers"):
        idx = PUB / layer / "index.json"
        if not idx.exists():
            bad.append(f"{layer}/index.json missing")
            continue
        try:
            have = {l["key"] for l in json.loads(idx.read_text(encoding="utf-8"))["leagues"]}
        except Exception as e:                                   # noqa: BLE001
            bad.append(f"{layer}/index.json unreadable: {e}")
            continue
        missing = want - have
        if missing:
            bad.append(f"{layer}/index.json is missing {', '.join(sorted(missing))}")

    # 2. THE PREDICTOR HAS FIXTURES WITH REAL PROBABILITIES. The front page is
    #    the predictor; publishing it with an empty or degenerate round is the
    #    single most visible way to be wrong.
    rnd = PUB / "round.json"
    if not rnd.exists():
        rnd = ROOT / "data" / "web" / "round.json"
    if not rnd.exists():
        bad.append("round.json missing — the front page would have no fixtures")
    else:
        try:
            r = json.loads(rnd.read_text(encoding="utf-8"))
            fixtures = [f for d in r.get("leagues", {}).values()
                        for f in d.get("fixtures", [])]
            if not fixtures:
                bad.append("round.json carries no fixtures")
            else:
                flat = [f for f in fixtures if
                        isinstance(f.get("home_p"), (int, float))
                        and abs((f.get("home_p", 0) + f.get("draw_p", 0)
                                 + f.get("away_p", 0)) - 1) > 0.02]
                if flat:
                    bad.append(f"{len(flat)} fixture(s) whose H/D/A does not sum to 1")
        except Exception as e:                                   # noqa: BLE001
            bad.append(f"round.json unreadable: {e}")

    # 3. NOTHING EMPTY, NOTHING COLLAPSED. An empty file is an obvious
    #    failure; a file that lost half its bytes is the dangerous one,
    #    because it still parses and still renders.
    for p in PUB.rglob("*.json"):
        rel = str(p.relative_to(PUB))
        n = p.stat().st_size
        if n == 0:
            bad.append(f"{rel} is empty")
            continue
        was = before.get(rel)
        if was and n < was * SHRINK_LIMIT:
            bad.append(f"{rel} shrank {was:,} -> {n:,} bytes "
                       f"({100 * (1 - n / was):.0f}% smaller)")
    return bad


def check_export() -> list:
    """The built export, after pnpm build. A clean build of a broken copy is
    still broken, so this is cheap insurance on the thing actually uploaded."""
    bad = []
    if not (OUT / "index.html").exists():
        return ["out/index.html missing — the build produced nothing"]
    for layer in ("team", "mental", "managers"):
        if not (OUT / "data" / layer / "index.json").exists():
            bad.append(f"out/data/{layer}/index.json missing from the export")
    if not (OUT / "sitemap.xml").exists():
        bad.append("out/sitemap.xml missing")
    return bad


# ---------------------------------------------------------------------------
def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--skip-update", action="store_true",
                    help="data is already fresh; build, deploy and push only")
    ap.add_argument("--no-deploy", action="store_true",
                    help="do everything except publish and push")
    ap.add_argument("--force", action="store_true",
                    help="passed to run_daily: ignore the no-football gate")
    args = ap.parse_args()

    started = datetime.now()
    print(f"publish  {started:%Y-%m-%d %H:%M}")
    done: list = []

    # ---- 1. update -------------------------------------------------------
    before = sizes_before()
    if args.skip_update:
        done.append(("update", "skipped (--skip-update)"))
    else:
        cmd = [PY, "-u", str(ROOT / "scripts" / "run_daily.py")]
        if args.force:
            cmd.append("--force")
        if not run("1. UPDATE — scrape and rebuild every ready league", cmd):
            print("\nThe update failed. Nothing was built, deployed or pushed.\n"
                  "The live site still serves the last good publish, which is\n"
                  "the point of stopping here.")
            return 1
        done.append(("update", "ok"))

    # ---- 2. the gate -----------------------------------------------------
    print(f"\n{'=' * 70}\n2. CHECK — is this fit to publish?\n{'=' * 70}")
    bad = check(before)
    if bad:
        print("REFUSING TO PUBLISH:")
        for b in bad:
            print(f"   !! {b}")
        print("\nThe data on disk is not right, so nothing was built or\n"
              "deployed. The live site is untouched and still correct.")
        return 1
    print(f"   ok — {len(ready_leagues())} leagues, indexes complete, "
          f"round has fixtures, no payload collapsed")
    done.append(("check", "ok"))

    # ---- 3. build --------------------------------------------------------
    if not run("3. BUILD — pnpm build", ["pnpm", "build"], cwd=WEB, shell=True):
        print("\nThe build failed. Nothing was deployed or pushed.")
        return 1
    bad = check_export()
    if bad:
        print("REFUSING TO PUBLISH — the export is incomplete:")
        for b in bad:
            print(f"   !! {b}")
        return 1
    done.append(("build", "ok"))

    if args.no_deploy:
        done.append(("deploy", "skipped (--no-deploy)"))
        done.append(("push", "skipped (--no-deploy)"))
        summary(started, done)
        return 0

    # ---- 4. deploy -------------------------------------------------------
    if not run("4. DEPLOY — wrangler pages deploy",
               ["npx", "wrangler", "pages", "deploy", "out",
                "--project-name", "predictorous", "--branch", "main",
                "--commit-dirty=true"],
               cwd=WEB, shell=True):
        print("\nThe deploy failed. NOTHING WAS COMMITTED — the repo still\n"
              "holds the change, so fixing the deploy and re-running is all\n"
              "that is needed. A commit here would have claimed a publish\n"
              "that did not happen.")
        return 1
    done.append(("deploy", "ok"))

    # ---- 5. push ---------------------------------------------------------
    # LAST, so a commit always means "this is live".
    print(f"\n{'=' * 70}\n5. PUSH — commit what was published\n{'=' * 70}")
    dirty = subprocess.run(["git", "status", "--porcelain"], cwd=str(ROOT),
                           capture_output=True, text=True).stdout.strip()
    if not dirty:
        print("   nothing changed — no commit needed")
        done.append(("push", "nothing to commit"))
        summary(started, done)
        return 0

    n = len(dirty.splitlines())
    leagues = ", ".join(lg.split("-")[-1] for lg in ready_leagues())
    msg = (f"Daily publish {started:%Y-%m-%d}: {leagues}\n\n"
           f"Updated, checked, built and deployed by scripts/publish.py.\n"
           f"{n} file(s) changed. The deploy succeeded before this commit was\n"
           f"made, so this records what is actually live.\n")
    subprocess.call(["git", "add", "-A"], cwd=str(ROOT))
    if subprocess.call(["git", "commit", "-q", "-m", msg], cwd=str(ROOT)) != 0:
        print("   commit failed — the deploy is live but the repo is behind")
        done.append(("push", "COMMIT FAILED"))
        summary(started, done)
        return 1
    if subprocess.call(["git", "push", "-q", "origin", "main"], cwd=str(ROOT)) != 0:
        print("   push failed — committed locally, not pushed")
        done.append(("push", "committed, PUSH FAILED"))
        summary(started, done)
        return 1
    print(f"   committed and pushed ({n} files)")
    done.append(("push", f"ok ({n} files)"))

    summary(started, done)
    return 0


def summary(started: datetime, done: list) -> None:
    mins = (datetime.now() - started).total_seconds() / 60
    print(f"\n{'=' * 70}\npublish finished in {mins:.1f} min")
    for stage, how in done:
        print(f"   {stage:<8} {how}")
    print("https://predictorous.com")


if __name__ == "__main__":
    raise SystemExit(main())

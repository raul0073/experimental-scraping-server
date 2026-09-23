"""Undo the over-coercion that build_whoscored_events.write_events once did.

WHAT HAPPENED. write_events has a retry path for a real Arrow failure: some
events have no `player`, pandas reads the gap as a float NaN in a column of
strings, and Arrow cannot type the mix. The first version of that retry
coerced EVERY object column to string, which is far more than the broken one.

Two kinds of column were destroyed by that:

  is_goal / is_shot   True/None became the STRING 'True' and pd.NA. pd.NA is
                      neither true nor false, so `if row.is_goal:` RAISES
                      rather than returning False — which is what stopped the
                      stamping step and kept two complete leagues off the site.

  qualifiers          an array of {'type': {'displayName': ...}} dicts became
                      a string repr of that array. Structured reads silently
                      return nothing, so OWN GOALS STOP BEING DETECTED and are
                      credited to the scoring team. Every future qualifier
                      metric — set pieces, pass length, card reason — would
                      have read empty too.

The repr is faithful, so this is recoverable in place with literal_eval and
no refetch. That matters: the alternative is re-reading several hundred
cached match JSONs per season.

Detection is by DTYPE, not by a hardcoded file list, because any season that
happened to hit the retry path is affected and the two we know about may not
be all of them.

    .venv/Scripts/python.exe scripts/repair_event_parquet.py           # report
    .venv/Scripts/python.exe scripts/repair_event_parquet.py --apply   # fix
"""
import argparse
import ast
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "whoscored"

FLAGS = ("is_goal", "is_shot", "is_touch")
STRUCT = ("qualifiers",)


def as_bool(s: pd.Series) -> pd.Series:
    """Text or object flags -> real booleans. A missing flag means False.

    Parsed as text rather than with astype(bool), which maps the STRING
    'False' to True — the kind of silent inversion that would be found much
    later, in a number nobody could explain.
    """
    return (s.astype("string").str.lower().eq("true")
            .fillna(False).to_numpy(dtype=bool))


def as_struct(s: pd.Series):
    """String reprs of a qualifier array -> the array again.

    literal_eval only builds literals, so a corrupted or truncated cell
    cannot execute anything; it raises and becomes None, which is what an
    event with no qualifiers already looks like.
    """
    def one(v):
        if v is None or not isinstance(v, str):
            return v                       # already structured, or genuinely null
        try:
            return ast.literal_eval(v)
        except (ValueError, SyntaxError):
            return None
    return s.map(one)


def looks_like_text(s: pd.Series) -> bool:
    """Are this column's values STRINGS where they should not be?

    The test is the value type, not the dtype. `is_goal` arrives from
    WhoScored as an OBJECT column holding True and None, and that is the
    native, correct shape — `if row.is_goal:` reads None as false and every
    consumer has always worked with it. Testing `dtype != bool` instead
    condemns all twenty files, which is how a repair turns into the thing it
    was meant to fix.

    What is actually damaged is a column whose values are the strings 'True'
    and 'False', or a string repr of an array.
    """
    nn = s.dropna()
    return not nn.empty and isinstance(nn.iloc[0], str)


def as_object(s: pd.Series) -> pd.Series:
    """Nullable-string column -> plain object holding str and None.

    The nullable dtype is not wrong in itself, but it spells missing as pd.NA
    while every other season on disk spells it None, and consumers test
    `is None`. services/mental/plots.py did exactly that, found pd.NA is not
    None, fell through to `a == b` and raised. One spelling of missing.
    """
    return s.map(lambda v: v if isinstance(v, str) else None).astype(object)


def inspect(path: Path) -> dict:
    """What is genuinely wrong with this file."""
    head = pd.read_parquet(path)
    bad_flags = [c for c in FLAGS
                 if c in head.columns and looks_like_text(head[c])]
    bad_struct = [c for c in STRUCT
                  if c in head.columns and looks_like_text(head[c])]
    # Text columns carrying pd.NA where the rest of the corpus carries None.
    bad_text = [c for c in head.columns
                if c not in FLAGS and c not in STRUCT
                and isinstance(head[c].dtype, pd.StringDtype)]
    return {"df": head, "flags": bad_flags, "struct": bad_struct,
            "text": bad_text}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true",
                    help="write the repaired files (default is report only)")
    args = ap.parse_args()

    files = sorted(p for p in RAW.glob("*/*.parquet")
                   if not p.stem.endswith("_stamped"))
    if not files:
        sys.exit(f"no event parquet under {RAW}")

    hurt = []
    print(f"scanning {len(files)} event files under {RAW.relative_to(ROOT)}\n")
    for p in files:
        try:
            r = inspect(p)
        except Exception as e:                               # noqa: BLE001
            print(f"  !! {p.parent.name}/{p.name}: unreadable ({e})")
            continue
        if not r["flags"] and not r["struct"] and not r["text"]:
            continue
        hurt.append((p, r))
        broke = ", ".join(r["flags"] + r["struct"]
                          + [c + "(NA)" for c in r["text"]])
        print(f"  DAMAGED  {p.parent.name}/{p.name:16} {broke}")

    if not hurt:
        print("  every file is clean — nothing to repair")
        return 0

    print(f"\n{len(hurt)} file(s) need repair")
    if not args.apply:
        print("dry run — pass --apply to write them")
        return 0

    for p, r in hurt:
        df = r["df"]
        for c in r["flags"]:
            df[c] = as_bool(df[c])
        for c in r["struct"]:
            df[c] = as_struct(df[c])
        for c in r["text"]:
            df[c] = as_object(df[c])
        # Write beside the original and swap only once the write has fully
        # succeeded: a half-written parquet here is a season lost, and the
        # source events cost hours to fetch.
        tmp = p.with_suffix(".parquet.repaired")
        df.to_parquet(tmp, index=False)
        tmp.replace(p)
        goals = int(df["is_goal"].sum()) if "is_goal" in df.columns else -1
        quals = int(df["qualifiers"].notna().sum()) if "qualifiers" in df.columns else -1
        print(f"  repaired {p.parent.name}/{p.name:16} "
              f"{len(df):,} events · {goals} goals · {quals:,} with qualifiers")

    print("\nNOTE: the stamped copies are now older than their source, so the "
          "next daily re-stamps them automatically (stale_seasons compares "
          "mtimes). No manual stamping needed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

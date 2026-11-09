# Tests

Two entry points, one set of cases. Neither touches the network or the real ledgers: every case runs in a temp directory on copies of `data/ledger`, `data/slips`, `data/history` and the fixture cache.

    .venv/Scripts/python.exe scripts/selfcheck.py              # PASS/FAIL per case, exit 1 on any FAIL (~7s)
    .venv/Scripts/python.exe scripts/selfcheck.py -k window    # one group: gate, grading, window, guards, payload, runner
    .venv/Scripts/python.exe -m pytest -q                      # the same cases + probability_service unit tests

`scripts/publish.py` runs `selfcheck.py` as STAGE 0, so a failing case blocks the publish before anything is updated.

Add a case in `scripts/selfcheck.py` with the `@case(group, name)` decorator; `tests/test_selfcheck.py` picks it up automatically. A case that documents a live bug gets `known_bug=...`: selfcheck reports it as FAIL, pytest treats it as strict xfail.

Install the test dependency with `.venv/Scripts/python.exe -m pip install -r requirements-dev.txt`.

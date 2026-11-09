"""The selfcheck cases, one pytest test each. The logic lives in
scripts/selfcheck.py (publish.py runs it as STAGE 0); this file only gives
each case a test id, a fresh sandbox and pytest's reporting.

A case that documents a LIVE pipeline bug (Case.known_bug) is strict-xfail:
the suite stays green while the bug is open, and the day the fix lands the
unexpected pass fails the suite until the marker is removed — so the known
bug cannot be forgotten in either direction."""
from __future__ import annotations

import hashlib

import pytest

import selfcheck


def _digest() -> dict:
    return {str(p): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in selfcheck.REAL_LEDGERS if p.exists()}


@pytest.fixture(scope="session", autouse=True)
def real_ledgers_untouched():
    # a test that can corrupt picks.jsonl is worse than no test
    before = _digest()
    yield
    assert _digest() == before, "the test session changed a REAL ledger"


def _param(c: selfcheck.Case):
    marks = [pytest.mark.xfail(strict=True, reason=c.known_bug)] if c.known_bug else []
    return pytest.param(c, id=c.id, marks=marks)


@pytest.mark.parametrize("case", [_param(c) for c in selfcheck.CASES])
def test_case(case: selfcheck.Case):
    with selfcheck.Sandbox() as sb:
        case.fn(sb)


def test_every_spec_group_is_covered():
    groups = {c.group for c in selfcheck.CASES}
    assert groups == {"gate", "grading", "window", "guards", "payload", "runner"}

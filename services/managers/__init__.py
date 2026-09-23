"""Manager ranking — what a side does under the man in charge.

The unit is the SPELL, stitched from WhoScored's per-match managerName by
services/mental/spells.py with absorb_short=False, so a manager sacked in
October keeps his own row instead of having his eight matches credited to
whoever came after him.

services.managers.metrics computes the raw per-spell numbers. Scoring,
percentiles and the web payload live elsewhere; this package publishes no
raw event stream, only derived metrics.
"""

# Production package deliberately removed (2026-08-07)

The files that were here were generated on 2026-08-05 22:42, which is BEFORE the
XIAO pad-map defect was found. They encoded the fatal wiring:

  module pin 12 (3V3_OUT) tied to GND   -> dead short across the module's LDO
  module pin 13 (GND)     left floating -> module ungrounded, cannot boot
  module pin 14 (VBUS)    fed 3.3V

Ordering from them would have produced a dead board that also destroys the
XIAO's regulator. They were deleted rather than left in place, because a stale
gerber zip sitting in a folder called "production" is an accident waiting to
happen.

The board itself is fixed (commit 289db9c). Regenerate this package with
    design/tools/export_production_2l.py
only AFTER routing closes -- as of this commit 5 connections are still open
(Net-(Q1-D) plus 4 ground edges), so the board is not yet fabricable.

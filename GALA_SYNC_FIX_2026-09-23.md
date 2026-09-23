# Gala sync fix — 2026-09-23

Changes after first real PWA + Streamlit rehearsal:
- Supersnajper TOP3 no longer reveals goal total. It shows matches in which the EA player scored, number of FIFA Night controllers who scored with him, and hat-tricks. Goal total remains winner-only.
- Drużyna Roku TOP3 no longer reveals titles. It shows match count and final appearances. Full W/D/L, W%, goals, GD and titles remain winner-only.
- Gala START freezes the public category payload (nominees + winner + readiness metadata) into the gala state.
- During a running/finale/finished gala, `/api/v1/gala/{year}` no longer recalculates `annual_awards()` on every TV/PWA poll.
- NEXT/REPLAY therefore switch category state quickly and the 6-second intro timer starts when the lightweight state is saved, instead of being consumed by repeated Awards calculations.
- Added `gala_sync_snapshot_smoke.py` to ensure running gala status never calls `annual_awards()`.

Tests PASS:
- py_compile core
- gala_backend_smoke
- gala_tv_payload_smoke
- gala_tv_fx_source_smoke
- gala_sync_snapshot_smoke
- gala_closeout_smoke
- audit_regression_smoke
- mobile_api_smoke 51/51
- group_tiebreak_smoke

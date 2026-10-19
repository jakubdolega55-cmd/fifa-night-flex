# FIFA NIGHT FLEX — R21 — FC27 partial wheel balance + idle wheel source
Date: 2026-10-19
Base: R20 / Android versionCode 15

## Scope
1. FC27 3/4/5-player wheel still uses 5 named teams + 1 Wild Card.
2. Wild Card is now strongly de-prioritized for real players in partial wheels:
   - real-player WC owner weight x0.10,
   - unused/ghost wheel slots remain x1.00,
   - previous-placement WC preference still works within real players.
3. Streamlit TV idle wheel now uses backend `remaining_wheel_pool` before the first spin and between spins, instead of reconstructing the wheel from hidden player assignments.
4. FC26 3/4 legacy draft unchanged.
5. No mobile source files changed in R21.

## Why
Old partial-wheel mechanics effectively made WC appear in roughly 50% / 67% / 83% of 3/4/5-player tournaments because real players and unused slots were treated similarly for the WC slot. This made WC much too common and reduced variety among the five named wheel clubs.

## Targeted tests
PASS:
- `python -m py_compile logic.py database.py ui.py`
- `tests/fc27_partial_wheel_wc_bias_smoke.py`
  - deterministic sample observed approx. 5.6% / 23.3% / 36.7% WC use for 3/4/5 players
  - every named fixed team appeared more often than WC
- `tests/tv_partial_wheel_idle_source_smoke.py`
- `tests/fc27_small_wheel_smoke.py`
  - full six-sector initial pool exposed to TV
  - remaining pool shrinks correctly after every real draw
  - final real player still spins when multiple unused sectors remain
  - FC26 3/4 draft unchanged
- `tests/fc27_draw_weight_tuning_smoke.py`
- `tests/team_repeat_penalty_smoke.py`

`mobile_api_smoke.py` was started and produced no failure through multiple full tournament flows, but the tool run hit the 30s execution limit before the suite completed, so it is NOT marked as a full PASS for this checkpoint.

## APK
R21 itself does not change mobile source, so no additional APK rebuild is required specifically for R21. R20 already moved Android to versionCode 15 and still requires a V15 build to receive the season UI changes.

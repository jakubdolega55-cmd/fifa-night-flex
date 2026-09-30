# FIFA NIGHT FLEX — MID-TOURNAMENT DRAW UI AUDIT

Stan: 2026-09-30

## Problem
Controller/Streamlit rendered `big_visible_draw_state()` as raw markdown lines (`A vs B`, BYE box), while TV already had a cinematic renderer. This made real DE9/DE10/Swiss/group draws look unfinished.

## Fix
- `app.py`: controller now uses `render_visible_pair_draw()` for every big visible draw.
- `ui.py`: generic draw renderer now reveals pairs sequentially, shows BYE candidate pool, and reveals the selected lucky BYE at the end.
- Specific headings added for DE9/DE10, other DE, groups9 and Swiss.

## Timing audit
- DE4: deterministic; no fake mid-draw.
- DE5/DE6: dynamic routing preserved; smoke PASS.
- DE7: LB cross is drawn early with symbolic sources before source matches finish.
- DE8: LB cross is drawn early with symbolic sources before source matches finish.
- DE9: first LB BYE intentionally waits until all 5 real candidates are known. Earlier selection would be unfair/incomplete.
- DE10: early LB routing exists; later BYE/cross is one coherent public reveal with symbolic sources.
- Swiss8/10: round pair reveal works and is persistent until acknowledged.
- Group 6/7/8/10 deterministic crosses are reveals, not fake random draws.
- Group9 barrage/top8 use genuine visible random draws where multiple equally valid layouts exist; final4 does not fake randomness if only one best layout exists.

## Regression tests
PASS:
- visible_draw_policy_smoke
- de456_draw_smoke
- de9_de10_smoke
- swiss_smoke
- mobile_api_smoke 51/51

No APK rebuild required. Streamlit/UI-only change.

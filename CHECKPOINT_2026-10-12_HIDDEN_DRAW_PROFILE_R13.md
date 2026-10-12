# CHECKPOINT 2026-10-12 — HIDDEN DRAW PROFILE R13

Base: R12.

## Changes
- Removed the artificial maximum of 3 player-specific FC27 draw-profile corrections.
- Streamlit controller can add any number of eligible players with **Dodaj korektę**.
- Every active correction can be edited or removed independently.
- The correction section renders only after Streamlit controller access has already been taken with the admin password.
- Removed the redundant second password/unlock form for this section.
- PWA/APK UI remains unchanged and contains no controls for this feature.
- Mobile/PWA setup API strips `fc27_real_player_handicap_snapshot`; the correction is applied only server-side.
- Core Real/PSG weighting rules from R11/R12 are unchanged.

## Tests
- `fc27_real_player_handicap_smoke.py` PASS (5 simultaneous corrections, remove, eligibility, tournament snapshot, mobile redaction)
- `fc27_real_profile_admin_visibility_smoke.py` PASS
- `fc27_small_wheel_smoke.py` PASS
- `fc27_real_ban_switch_smoke.py` PASS
- `fc27_draw_weight_tuning_smoke.py` PASS
- `national_mode_fc27_smoke.py` PASS
- `mobile_api_smoke.py` 52/52 PASS
- `python -m py_compile app.py database.py mobile_api.py` PASS

## APK
NO. No mobile source file changed.

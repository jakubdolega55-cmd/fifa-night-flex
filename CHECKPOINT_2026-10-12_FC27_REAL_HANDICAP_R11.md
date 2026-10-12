# CHECKPOINT 2026-10-12 — FC27 REAL HANDICAP R11

Base: R10 Streamlit wheel hotfix.

## Changes
- EA FC 27 club draw: Real Madrid is now handicapped more strongly for players coming from the immediately previous completed FIFA Night:
  - previous champion: Real weight x0.25,
  - previous runner-up: Real weight x0.45.
- PSG is unchanged:
  - previous champion x0.40,
  - previous runner-up x0.60.
- Added Streamlit-only, admin-password-protected settings for up to 3 historical official-tournament players.
- Each selected player can receive an additional Real reduction from 0% to 90% in 5 pp steps.
- Manual player reduction stacks multiplicatively with the normal Real placement handicap, Live Team Rating and exact previous-team repeat penalty.
- The custom player handicap applies only to Real Madrid in EA FC 27 club mode.
- It does not affect PSG, national-team mode, FC26 or 1 vs 1 manual team selection.
- Real-ban remains authoritative: if Real is banned, the custom handicap is irrelevant because Real is not in the pool.
- Settings are persistent by player ID and affect newly created FC27 club tournaments. Already-created tournaments keep their previously generated team assignments.
- A per-tournament snapshot of active custom Real reductions is stored in meta for auditability.

## Streamlit UI
Settings -> "Dodatkowy handicap Realu — wybrani gracze"
1. Enter ADMIN_PASSWORD to unlock the section.
2. Select up to 3 players who already have official tournament history.
3. Set an extra Real reduction (0-90%) for each.
4. Save. The section can be locked again.

Example: a previous champion with a manual 50% reduction has Real weight x0.25 x0.50 = x0.125 before Live Team Rating / repeat-team modifiers.

## Validation
- Python compile: PASS (existing ui.py invalid escape SyntaxWarning unchanged).
- fc27_draw_weight_tuning_smoke.py: PASS.
- fc27_real_player_handicap_smoke.py: PASS.
- fc27_small_wheel_smoke.py: PASS.
- fc27_real_ban_switch_smoke.py: PASS.
- fc27_real_ban_mobile_settings_smoke.py: PASS.
- national_mode_fc27_smoke.py: PASS.
- club_pool_and_test_reset_smoke.py: PASS.
- mobile_api_smoke.py: 52/52 PASS.

## APK
NO. No mobile source changed. Backend/Streamlit deployment only.

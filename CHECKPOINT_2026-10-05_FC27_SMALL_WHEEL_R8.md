# FIFA NIGHT FLEX — R8 FC27 SMALL WHEEL
Date: 2026-10-05
Base: R7 (FIRST CHAMPIONS)

## Change
EA FC 27 tournaments with 3, 4 and 5 players now use the same six-sector team wheel model as 6-player tournaments:
- 5 fixed teams + 1 Wild Card;
- spin only once per real player;
- after all players have a team, any remaining wheel sectors are simply unused;
- the final real player still spins when multiple sectors remain;
- FC26 3/4 legacy draft remains unchanged.

This applies to FC27 clubs and FC27 national-team mode. Existing Real-ban snapshot rules remain unchanged.

## Technical notes
- `allowed_teams()` returns the six-sector FC27 pool for 3–6 players.
- 3–5 player FC27 tournaments use a partial-wheel assignment with neutral ghost slots so the existing weighting/anti-repeat logic remains compatible with the six-slot wheel.
- Full wheel pool is retained in metadata while concrete player assignments use only N of the 6 slots.
- `remaining_wheel_pool()` removes only already-consumed technical slots and keeps unused sectors visible.
- deterministic final no-spin shortcut runs only when exactly one real player AND exactly one wheel sector remain.
- mobile setup exposes `remaining_wheel_pool` so the mobile auto-final shortcut follows the same rule.

## Tests
- `fc27_small_wheel_smoke.py`: PASS for FC27 3/4/5 and FC26 3/4 legacy draft.
- `national_mode_fc27_smoke.py`: PASS.
- `wheel_shrink_smoke.py`: PASS.
- `fc27_real_ban_switch_smoke.py`: PASS.
- `big_patch_smoke.py`: PASS (8 format regression set).
- `mobile_api_smoke.py`: 52/52 PASS.
- Python compile: PASS.

## APK
YES — mobile setup behavior changed for FC27 3/4/5.

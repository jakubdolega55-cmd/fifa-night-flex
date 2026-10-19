# FIFA NIGHT FLEX — R19 Awards season close
Date: 2026-10-19
Base: R18 Awards Season labels

## Scope
Small checkpoint: backend + Streamlit season boundary only. No mobile/PWA source files changed.

## Added
- Active Awards season stored in app_settings.
- Season 1 initializes lazily from Jan 1 of the current calendar year, preserving the pre-season behavior on upgrade.
- Existing current-year laureate selections and Gala state are copied into Season 1 on first access.
- Current Awards use the active season start timestamp instead of the whole calendar year.
- Streamlit Awards header shows `Sezon N` and its start date.
- Closed season list is visible in Streamlit.
- Admin-only `Zakończ sezon` control unlocks only after Gala status is `finished`.
- Closing is blocked while any official non-test event is active.
- Closing stores a frozen Awards + Gala snapshot and history metadata.
- A new season starts at the exact close timestamp with clean laureate/Gala state.
- General matches, H2H, all-time stats, badges, milestones and tournament history are untouched.

## Compatibility
The public method signatures still accept the current calendar year. Internally, current-year Award selections/Gala state are mapped to the active season, so existing clients are not forced to change in this checkpoint.

## Tests
- `tests/awards_season_close_smoke.py` PASS
- `tests/gala_counters_smoke.py` PASS
- `tests/gala_tv_payload_smoke.py` PASS
- `tests/awards_logic_patch_smoke.py` PASS
- `python -m py_compile database.py app.py` PASS

## Next small step
Adapt explicit mobile/PWA Awards/Gala labels and controls from calendar-year wording to `Sezon N`, without changing the season boundary logic.

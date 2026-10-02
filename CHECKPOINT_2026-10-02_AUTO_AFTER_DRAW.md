# CHECKPOINT 2026-10-02 — Streamlit AUTO after team draw

## Change
After the synchronized setup/team draw finishes on Streamlit TV, the display now automatically switches to `🔄 AUTO`.

- Setup/draw watcher remains LIVE at 1 s.
- The final reveal still gets the existing 4.2 s grace period.
- Only after that grace period does Streamlit set `tv_display_mode_<tid>` to `🔄 AUTO` and enter the normal tournament TV screen.
- AUTO starts a fresh 30 s slide cycle.
- No tournament logic, DB, API, scheduler, Swiss, DE, or mobile code changed.

## Tests
- Python compile: PASS (`app.py`, `ui.py`, `database.py`)
- Verified current base still contains: FC27 default, Swiss draw support 3-1-0, TEST FIXES R2 checkpoint, draw reveal/wide R3.

## APK
NO. Streamlit-only change.

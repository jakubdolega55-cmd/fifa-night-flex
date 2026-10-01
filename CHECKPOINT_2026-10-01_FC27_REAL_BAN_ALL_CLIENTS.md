# CHECKPOINT 2026-10-01 — FC27 REAL BAN ALL CLIENTS

- Streamlit: admin-password protected Real ban switch remains available.
- PWA/APK: Settings now show the same Real-ban toggle after controller login.
- Shared backend setting: `fc27_real_banned`.
- ON: wheel = Manchester City, PSG, Bayern Monachium, FC Barcelona, Arsenal.
- ON: Real Madryt is blocked from Wild Card/manual selection; City is removed from WC suggestions.
- ON: only PSG keeps the extra strong-team soft handicap. City is neutral.
- OFF: normal pool = Real Madryt, PSG, Bayern Monachium, FC Barcelona, Arsenal; City returns as first WC.
- Existing tournaments keep their pool snapshot.
- Android `versionCode` bumped 12 -> 13.
- New APK required because mobile UI changed.

Tests run:
- `fc27_real_ban_mobile_settings_smoke.py` PASS
- `fc27_real_ban_switch_smoke.py` PASS
- `mobile_api_smoke.py` 51/51 PASS
- `national_mode_fc27_smoke.py` PASS
- `club_pool_and_test_reset_smoke.py` PASS
- Python compile PASS

Not physically tested on installed APK/PWA in this environment.

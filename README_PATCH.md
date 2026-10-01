# FIFA Night — V14 Team Visuals / Forma Live POLISHED

Base: `FIFA-NIGHT-1.1.3-TEAM-VISUALS-LIVE-FORM-V14-2026-10-01.zip`

Replace on GitHub:
- `app.py`
- `team_visuals.py`
- `mobile/src/FifaScreen.tsx`
- `mobile/src/teamVisuals.tsx`
- `tests/team_visuals_live_form_smoke.py`

Add:
- `CHECKPOINT_2026-10-01_TEAM_VISUALS_LIVE_FORM_POLISH.md`

No database migration. No API contract change. Android `versionCode` stays **14** because the V14 APK has not been built yet.

Polish included:
- stronger W/R/P badges and fixed 5-slot layout,
- `FORMA LIVE` Polish label,
- England flag fix,
- extra club-name aliases,
- crest cache request + subtle shadow + initials fallback.

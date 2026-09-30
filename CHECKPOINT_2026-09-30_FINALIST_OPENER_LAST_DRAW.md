# Checkpoint 2026-09-30 — previous finalists opener + Streamlit final assignment

## Fix 1 — no useless final team wheel in Streamlit
- When exactly one unrevealed team slot remains, Streamlit consumes it automatically.
- Normal team: assignment is confirmed without a one-sector wheel and setup advances directly to structure draw.
- Final Wild Card: no wheel animation; controller goes directly to Wild Card team selection, then advances to structure draw after confirmation.
- Works for FC27 nationals as well as clubs.

## Fix 2 — neither previous finalist opens the next tournament when avoidable
- Cross-tournament context now stores both previous finalists explicitly.
- At tournament start, if at least one ready/legal match contains neither previous finalist, scheduler must choose among those matches first.
- New/returning player priority remains, but cannot override finalist opener protection.
- Pairings are never rewritten; only play order among already legal/ready matches changes.
- No forced A/B alternation was added.

## Tests
- finalist_opener_streamlit_last_smoke: PASS
- smart_scheduler_smoke: PASS
- next_match_projection_smoke: PASS
- summary_last_team_yellow_smoke: PASS
- national_mode_fc27_smoke: PASS
- mobile_api_smoke: 51/51 PASS
- group_tiebreak_smoke: PASS
- swiss_smoke: PASS
- forfeit_smoke: PASS

## Deployment
Backend/Streamlit only. No APK rebuild required.
Replace on GitHub:
- `database.py`
- `logic.py`
- `app.py`
Then redeploy Render/Streamlit as usual.

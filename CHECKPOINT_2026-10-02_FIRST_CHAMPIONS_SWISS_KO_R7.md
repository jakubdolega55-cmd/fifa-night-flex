# CHECKPOINT 2026-10-02 — FIRST CHAMPIONS SWISS / KO — R7

Correction of R6 milestone semantics.

- Removed the R6 match-level milestones `first_de_win`, `first_swiss_win`, `first_ko_win`.
- Existing Double Elimination milestone `first_de` remains unchanged; it already records the first DE event and its champion.
- Added `first_swiss_champion` — 🔀 Pierwszy mistrz Swiss.
- Added `first_ko_champion` — 🥊 Pierwszy mistrz KO.
- Swiss / KO milestone is created only for a completed official tournament with `champion_player_id`; abandoned/incomplete tournaments do not qualify.
- The milestone points to the tournament, not to a single match (`match_no=None`).

Tests:
- `tests/format_first_win_milestones_smoke.py` — champion semantics PASS.
- `tests/milestones_refresh_modes_smoke.py` — regression PASS.

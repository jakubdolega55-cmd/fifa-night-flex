# CHECKPOINT 2026-10-12 — GLOBAL TEAM REPEAT x0.10 — R15

## Change
- Exact repeat of the same team from a player's immediately previous official tournament now keeps only **10% of normal draw weight** (`x0.10`, previously `x0.35`).
- The penalty is global in the shared randomized team-assignment engine: FC26/FC27 and clubs/national-team modes where team assignment is randomized.
- It remains a soft penalty, never a hard ban: a repeat is still possible.
- Manual team choices (for example a concrete Wild Card choice) are not probabilistic and therefore are not altered by this multiplier.

## Preserved
- FC27 Real champion/finalist handicap and hidden Streamlit draw-profile correction unchanged.
- R14 removal of the 3-player profile-correction limit is included in this checkpoint.
- FC27 small-wheel behavior for 3/4/5 players unchanged.
- PWA/APK UI unchanged.

## Validation
- Python compile: PASS.
- Global repeat weighting smoke: PASS for FC26 clubs, FC27 clubs and FC27 national mode.
- FC27 draw-weight tuning smoke: PASS.
- FC27 3/4/5 small-wheel smoke: PASS.
- Mobile/API smoke: 52/52 PASS.

## APK
- No APK rebuild required; backend/logic only.

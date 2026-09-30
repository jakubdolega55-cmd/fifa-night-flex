# CHECKPOINT 2026-09-30 — GLOBAL REST + BYE FAIRNESS

## Changes
- Rest / anti-marathon scheduler is now enabled for every tournament format, not only DE and 8+ player formats.
- It only reorders matches that are already legal and ready; it never changes pairings or bracket dependencies.
- If a player has appeared in consecutive recent matches, a legal alternative is preferred.
- Rolling last-4 load is also considered so one intervening match does not fully reset fatigue pressure.
- In-tournament dynamic BYE logic uses a strong repeat penalty: 1st previous BYE x0.25, 2nd x0.10, 3rd+ x0.05; never zero.
- Existing DE9 repeated-BYE selection uses the penalty on every successive lower-bracket BYE.

## Expected behavior
- Applies to DE, Swiss, groups/league and any future format whenever multiple matches are simultaneously ready.
- If only one match is legal/ready, it is played normally; fairness never blocks progression.

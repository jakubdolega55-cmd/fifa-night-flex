# GitHub patch — Global Rest + BYE Fairness

Replace on GitHub:
- `database.py`

No APK rebuild required.

Behavior:
- anti-marathon match ordering applies to every format whenever 2+ legal matches are ready;
- repeated in-tournament BYEs are strongly down-weighted, never hard-blocked;
- pairings/bracket sources are never rewritten.

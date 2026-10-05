# CHECKPOINT 2026-10-05 — Awards Frequency Fairness R9

Base: R8 FC27 Small Wheel.

## Changed award scoring

1. Najlepszy spoza dominatorów
- Removed raw wins and total GD from scoring.
- Score now uses W%, GD per match, finals rate (finals / starts), and a small title bonus (max 1 title eligibility unchanged).

2. Rywalizacja Roku
- Pure H2H volume bonus is capped at 6 matches: `min(matches, 6) * 3`.
- Balance has more weight; important matches and drama remain meaningful.

3. Najbardziej Uniwersalny Gracz
- Score now uses percentage of used teams that were successful, capped diversity bonus, and a smaller W% component.
- Tournament starts themselves give no points.
- Swiss/KO success is correctly recognized as reaching SF/Final; DE keeps WB/LB Final logic; leagues require Final.

4. Comeback King
- Main component is comeback points per 10 official matches.
- Maximum recovered deficit gives a quality bonus.
- Raw total comeback points remain visible but no longer dominate by volume.

5. Król Końcówek
- Main component is goals 85+ per 10 matches with detailed Events.
- Total late goals give only a small capped bonus (max 8 goals counted for that bonus).

6. Clutch Player Roku
- Removed `clutch wins * 4` volume bonus.
- Uses Beta(3,3) adjusted clutch win rate: `(wins + 3) / (matches + 6)`.
- Minimum 5 clutch matches unchanged.

7. Beton Roku
- Removed `+min(matches,20)` and raw clean-sheet bonus.
- Score is based on GA/match, clean-sheet percentage, plus the existing controlled xGA/match component.

8. Ofensywny Gracz Roku
- Removed total goals and raw high-win count from scoring.
- Score uses goals/match, percentage of matches won by 3+ goals, capped max-margin bonus, xG/match and shots/match.
- SOT is not used in scoring.

9. Gracz Roku
- Removed `+1` per tournament start.
- Titles, finals, W%, clutch%, GD/match and controlled xGD remain.

## Gala presentation
- Nominee teasers still avoid revealing decisive ranking metrics.
- Winner reveal now explains normalized/per-match metrics where relevant.

## Tests
- `awards_frequency_fairness_smoke.py` PASS.
  - Same quality at 10 vs 20 matches does not increase Offensive / Outsider / Player of the Year score by volume alone.
  - Defense uses rate-only score.
  - Clutch smoothing makes strong larger samples competitive with perfect tiny samples.
  - Rivalry H2H volume bonus is capped after 6 matches.
- `awards_logic_patch_smoke.py` PASS.
- `gala_tv_payload_smoke.py` PASS.
- `mobile_api_smoke.py` 52/52 PASS.
- Python compile PASS.

Note: existing `gala_backend_smoke.py` test-mode fallback assertion already fails identically on clean R8; not introduced by R9.

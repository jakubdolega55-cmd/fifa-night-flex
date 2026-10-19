# CHECKPOINT 2026-10-19 — AWARDS SEASON LABELS R18

Base: R17 Gala counters fix, carrying R16 mobile SetupResponse typing fix and all R15 backend changes.

## Changes
- Awards/Gala public naming switched from `Roku` to `Sezonu` where applicable:
  - Gracz Sezonu
  - Drużyna Sezonu
  - Supersnajper Sezonu
  - Debiut Sezonu
  - Rywalizacja Sezonu
  - Mecz Sezonu
  - Clutch Player Sezonu
  - Beton Sezonu
  - Ofensywny Gracz Sezonu
  - Pechowiec Sezonu
- Gala/Streamlit/mobile highlight text updated to season wording.
- Clutch still uses sample-size correction internally for ranking fairness, but the UI no longer exposes the confusing adjusted percentage. It shows only raw clutch record and effectiveness.
- Comeback King display changed from points per 10 matches to points per match.
- Król Końcówek display changed from 85+ goals per 10 matches to 85+ goals per match.
- Ranking balance for Comeback/late goals is mathematically unchanged (`per_match * 10` internally where needed); this is a presentation/API-field cleanup, not a rebalance.
- R17 nomination and physical statuette counter fixes remain intact.

## Tests
- Python compile PASS
- gala_counters_smoke PASS
- awards_logic_patch_smoke PASS
- awards_frequency_fairness_smoke PASS
- gala_tv_payload_smoke PASS
- gala_closeout_smoke PASS

## Next separate task
Implement real Award seasons with admin `Zakończ sezon` closeout, archived Gala results, and new-season calculation boundary. Do not mix that database boundary migration into R18.

APK: NO. No mobile component/source UI was changed; only backend/API text and Streamlit-visible wording.

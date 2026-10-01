# CHECKPOINT 2026-10-01 — LOCAL FLAGS

## Zakres
- Reprezentacje nie używają już emoji flag w UI.
- Dodano lokalne PNG flag do Streamlit: `assets/teams/flags/`.
- Dodano lokalne PNG flag do PWA/APK: `mobile/assets/teams/flags/`.
- Streamlit osadza flagę jako lokalny `data:image/png;base64`, bez requestu sieciowego.
- Mobile/PWA używa statycznych `require(...)`, więc asset jest bundlowany z aplikacją.
- Aliasowanie nazw reprezentacji pozostaje bez zmian.
- Herby klubów pozostają na tym etapie zdalne i będą przenoszone lokalnie w kolejnym osobnym patchu.

## Testy
- `python -m py_compile team_visuals.py app.py ui.py` — PASS
- `python tests/team_visuals_live_form_smoke.py` — PASS
- test sprawdza istnienie wszystkich 14 lokalnych PNG po obu stronach projektu.

## APK
TAK — zmienione zostały assety i `mobile/src/teamVisuals.tsx`.
Jeżeli V14 nadal nie było zbudowane/zainstalowane, `versionCode` pozostaje 14.

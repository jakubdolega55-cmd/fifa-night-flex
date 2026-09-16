# FIFA Night 1.1.1 — DE technical 1:0 stats hotfix

## Zasada
W Grand Final Double Elimination techniczne +1 dla zwycięzcy Winners Bracket:
- **liczy się do oficjalnego W/L zawodnika i rozstrzygnięcia drabinki**;
- **nie jest prawdziwym golem**;
- nie wchodzi do GF/GA, GD, goli/mecz, rekordów bramkowych, Meczu Roku, widowiskowości itd.;
- dla **statystyk drużyny** wynik jest wynikiem boiskowym, np. zapisane 4:3 = statystycznie 3:3 i remis drużyn.

## Co poprawia hotfix
- all-time statystyki zawodników: W/L zostaje oficjalne, GF/GA bez technicznego gola;
- H2H: W/L zawodnika zostaje, bilans bramek bez +1;
- profile graczy: ogólny W/L zawodnika zostaje, statystyki jego drużyn traktują finał jako remis;
- statystyki drużyn: W/D/L + GF/GA/GD liczone z realnego wyniku;
- Live Team Rating: wynik drużyny i GD liczone z realnego wyniku;
- Awards / Drużyna Roku: techniczne +1 nie daje klubowi zwycięstwa i nie zmienia GF/GA;
- Mecz Roku i pozostałe kategorie bramkowe: realna liczba goli;
- rekordy (najwięcej goli / największa różnica / gole gracza): bez technicznego gola;
- podsumowanie turnieju i PNG: bilanse oraz liczba goli bez +1;
- comeback / blown lead: techniczny gol nie uczestniczy w przebiegu bramkowym.

## Pliki do podmiany w repo
W głównym katalogu repo podmień:
- `database.py`
- `export_utils.py`

Nie ma zmian w `mobile/`, więc nie trzeba budować nowego APK tylko z powodu tego hotfixa.
Po pushu zdeployuj / poczekaj na auto-deploy API i zrestartuj/zdeployuj Streamlit.

## Walidacja
- `python -m py_compile app.py database.py logic.py mobile_api.py export_utils.py scorer_seeds.py ui.py` — PASS
- `tests/mobile_api_smoke.py` — 51/51 PASS
- wszystkie BIG PATCH / Swiss / DE / scheduler / versioning / wheel testy — PASS
- `tests/de_technical_score_stats_smoke.py` — PASS

Dedykowany przypadek testowy: Grand Final DE zapisany jako 4:3 (techniczne 1:0 + realne 3:3):
- zawodnik: W/L zgodnie z 4:3;
- GF/GA zawodników: 3:3;
- drużyny: remis, 3:3;
- H2H: zwycięstwo zawodnika, gole 3:3;
- Live Team Rating: remis drużyn;
- Mecz Roku: 6 goli;
- rekordy / podsumowanie: 6 realnych goli.

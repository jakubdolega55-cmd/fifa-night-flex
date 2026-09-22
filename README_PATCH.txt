FIFA NIGHT 1.1.3 — GROUP TIEBREAK PATCH

Podmień te pliki w głównym repozytorium GitHub, zachowując strukturę katalogów.
Po pushu zrób/restartuj deploy backendu na Renderze.

NOWA ZASADA GRUP:
1) punkty -> różnica bramek -> gole strzelone -> H2H / mini-tabela
2) jeśli ostatni mecz w danej grupie jest dokładnie między dwoma graczami równymi
   na granicy awansu, remis po 90 min oznacza dogrywkę; jeśli nadal remis -> karne
3) przy remisie 3+ graczy albo remisie nierozstrzyganym w ostatnim bezpośrednim meczu:
   fair play (żółta = 1 pkt karny, czerwona = 3; mniej = lepiej)
4) jeśli fair play też równe -> trwałe losowanie kolejności; tie_order nie decyduje o awansie

WAŻNE:
- To jest zmiana mobilnego UI i wymaga nowego APK.
- Wersja mobile: 1.1.3, Android versionCode: 8.
- Pakiet APK BUILD-READY jest dostarczony osobno.
- Nie ma migracji schematu bazy danych.

TESTY ODPALONE:
- group_tiebreak_smoke.py PASS
- audit_regression_smoke.py PASS
- forfeit_smoke.py PASS
- Swiss8/10 PASS
- DE4–10 PASS
- smart scheduler PASS
- visible draw policy PASS
- FC26/FC27/versioning PASS
- wheel shrink PASS
- mobile_api_smoke 51/51 PASS
- big_patch_smoke 8/8 formatów PASS
- Python compile PASS
- TypeScript/TSX parse 12/12 PASS

Nie oznaczono jako PASS rzeczywistego EAS build na koncie Expo.

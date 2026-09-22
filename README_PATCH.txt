FIFA Night 1.1.2 — AUDIT PATCH / GITHUB
=======================================

Ta paczka ma strukturę zgodną z repozytorium.
Skopiuj jej zawartość do katalogu głównego repozytorium i zezwól na zastąpienie plików o tych samych nazwach.

PLIKI RUNTIME — najważniejsze:
- database.py
- mobile_api.py

Poprawki backendu:
1. Rzuty karne:
   - tylko w fazie pucharowej,
   - tylko przy remisie wyniku meczu,
   - wymagane obie wartości,
   - wynik karnych nie może być remisowy.
2. Atomowy zapis wyniku:
   - drugi telefon / drugi zapis nie nadpisze już zapisanego wyniku.
3. Strzelcy:
   - backend ignoruje nazwę drużyny przesłaną przez klienta i bierze właściwą drużynę z turnieju.

SYNCHRONIZACJA ŹRÓDEŁ MOBILE Z APK FIX2, KTÓRĄ JUŻ ZAINSTALOWANO:
- mobile/src/FifaScreen.tsx
- mobile/src/AwardsScreen.tsx
- mobile/src/StatsScreen.tsx

Te pliki NIE wymagają ponownego APK, ponieważ są dokładnie zsynchronizowane z użytym BUILD-READY-FIX2.
FifaScreen.tsx zawiera poprawiony przycisk PODDAJ MECZ z własnym async/await + refresh.

BEZPIECZEŃSTWO PRZYSZŁYCH BUILDÓW:
- mobile/.gitignore
- mobile/.easignore

TEST DODANY:
- tests/audit_regression_smoke.py

TESTY PO PATCHU:
- Python compile: PASS
- audit_regression_smoke: PASS
- forfeit_smoke: PASS
- swiss_smoke: PASS
- de456_draw_smoke: PASS
- de9_de10_smoke: PASS
- smart_scheduler_smoke: PASS
- versioning_alias_smoke: PASS
- visible_draw_policy_smoke: PASS
- wheel_shrink_smoke: PASS
- big_patch_smoke: PASS
- mobile_api_smoke: 51/51 PASS

WAŻNE:
- Patch nie zmienia schematu bazy danych i nie wymaga migracji Neon.
- Zainstalowanego APK FIX2 nie trzeba przebudowywać dla tych poprawek.
- Po podmianie database.py i mobile_api.py trzeba jedynie doprowadzić do redeployu backendu na Render (jeżeli auto-deploy z GitHub jest włączony, commit/push powinien go uruchomić).

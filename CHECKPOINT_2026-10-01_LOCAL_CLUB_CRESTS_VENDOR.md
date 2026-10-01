# FIFA NIGHT FLEX — LOCAL CLUB CRESTS / BUILD VENDOR — 2026-10-01

## Zakres tego małego etapu

Runtime Streamlit/PWA/APK został odcięty od zdalnych URL-i herbów klubowych.

- `team_visuals.py` ładuje klub wyłącznie z `assets/teams/clubs/<slug>.png` i osadza PNG jako data URI.
- `mobile/src/teamVisuals.tsx` używa statycznych `require('../assets/teams/clubs/<slug>.png')`.
- nieznany/ręczny Wild Card nadal ma fallback do inicjałów.
- flagi reprezentacji pozostają lokalne jak w poprzednim checkpointcie.
- miejsca wyświetlania bez zmian: wynik losowania, aktualny mecz, następny mecz.
- logika turnieju/API/DB bez zmian.

## 16 mapowanych herbów

Real Madrid, PSG, Bayern, Barcelona, Arsenal, Manchester City, Liverpool, Atletico Madrid, Inter, Manchester United, Borussia Dortmund, Napoli, Chelsea, Tottenham, AC Milan, Bayer Leverkusen.

Aliasy z poprzedniej wersji pozostają (np. Real Madryt, Lombardia FC, BVB 09, Man Utd, Atletico/Atlético).

## Ważne — vending assetów

Środowisko robocze tego checkpointu nie ma bezpośredniego zapisu binarnych obrazów z internetu do paczki. Zamiast wkładać atrapy, dodano deterministyczny vendor step:

- root / Streamlit: `python vendor_team_crests.py`
- mobile/PWA/APK: `npm run vendor:teams`

Vendor pobiera PNG tylko przed buildem/deployem i zapisuje je lokalnie. UI nigdy nie odwołuje się do tych URL-i.

Mobile ma vendor podpięty automatycznie przed:
- `npm start`
- `npm run android`
- `npm run web`
- `npm run build:web`
- `npm run build:apk`
- one-click `BUILD_APK_WINDOWS.cmd`

Po udanym vendingu wszystkie herby są lokalnymi plikami w projekcie/bundlu.

## Testy

PASS:
- Python compile: app/ui/mobile_api/database/team_visuals/vendor
- `tests/team_visuals_live_form_smoke.py`
- `tests/local_team_assets_vendor_smoke.py`
- `tests/milestones_refresh_modes_smoke.py`
- Node syntax check vendor script

Nie wykonano realnego pobrania PNG w tym środowisku, bo container nie ma wyjścia sieciowego do plików binarnych. Nie deklarować fizycznego testu na telefonie/TV.

## APK

TAK — zmienia się mobile i dochodzą lokalne assety. Jeśli użytkownik nadal nie zbudował pierwszego V14, `versionCode` pozostaje 14.

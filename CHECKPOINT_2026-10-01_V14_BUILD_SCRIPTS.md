# CHECKPOINT — V14 build scripts cleanup — 2026-10-01

Zmiany:
- `BUILD_APK.bat`: poprawiony nagłówek z versionCode 13 na V14 i dodany `vendor:teams` przed check/build.
- `BUILD_APK_WINDOWS.cmd`: jawny nagłówek V14.
- `mobile/build-preview.ps1`: wersja 1.1.3/V14 + przygotowanie lokalnych herbów.
- `mobile/build-pwa.ps1`: usunięte podwójne vendorowanie; `npm run build:web` robi je sam.
- `mobile/README.md`: zaktualizowane stare dane 1.0.1/versionCode 3 do 1.1.3/versionCode 14 i aktualny flow lokalnych assetów.

Logika turnieju/API/DB bez zmian.
APK: TAK tylko dlatego, że ten checkpoint jest źródłem do kolejnego V14; sam cleanup skryptów nie zmienia runtime aplikacji.

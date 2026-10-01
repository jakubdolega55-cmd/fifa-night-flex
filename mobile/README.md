# FIFA Night Mobile 1.1.3 / V14

Aplikacja Android/PWA (React Native + Expo) sterująca tym samym FIFA Night, którego wersja web/TV działa w Streamlit.

Architektura: `APK/PWA -> FastAPI/Render -> Neon <- Streamlit/TV`. APK nie zawiera `DATABASE_URL` i nie łączy się bezpośrednio z Neonem.

## Tożsamość aplikacji

- Expo/EAS: `@kubsi/fifa-night-mobile`
- Android package: `pl.fifanight.flex`
- EAS projectId: `cbb45c49-4757-4587-8a05-e4814cb5f60a`
- Mobile version: `1.1.3`
- Android versionCode: `14`

Nie zmieniaj package ID ani istniejącego keystore, jeśli APK ma aktualizować wcześniej zainstalowaną aplikację.

## Lokalne herby i flagi

- Flagi reprezentacji są spakowane lokalnie w `assets/teams/flags/`.
- Herby klubów są już fizycznie spakowane w `assets/teams/clubs/`; build i runtime nie wymagają pobierania ich z internetu.
- Runtime aplikacji nie pobiera herbów ani flag po URL.
- Nieznany/ręczny Wild Card ma fallback do inicjałów.

## API

Profile EAS `preview` i `production` używają publicznego:

`EXPO_PUBLIC_API_URL=https://fifa-night-api.onrender.com`

To nie jest sekret. Sekrety bazy pozostają wyłącznie na Renderze.

## Build APK

Najprościej uruchomić z katalogu głównego:

- `BUILD_APK_WINDOWS.cmd` albo
- `BUILD_APK.bat`

Oba skrypty sprawdzają obecność spakowanych lokalnych herbów, uruchamiają TypeScript check i Expo Doctor przed buildem EAS.

Ręcznie w katalogu `mobile/`:

```powershell
npm.cmd install
npm.cmd run check
npx.cmd expo-doctor
npx.cmd eas-cli@latest build --platform android --profile preview
```

Można też uruchomić `./build-preview.ps1`.

## Build PWA

W katalogu `mobile/`:

```powershell
npm.cmd install
npm.cmd run check
npx.cmd expo-doctor
npm.cmd run build:web
```

`build:web` najpierw sprawdza komplet lokalnych herbów, a następnie wykonuje eksport. Nie pobiera żadnych herbów z internetu.

## Kontrola przed instalacją

1. Lokalne herby muszą być obecne w `mobile/assets/teams/clubs/` przed buildem.
2. `npm run check` musi zakończyć się bez błędów.
3. `expo-doctor` nie może zgłaszać problemów blokujących build.
4. EAS build `preview` ma wygenerować APK dla `pl.fifanight.flex` z `versionCode 14`.
5. Po instalacji sprawdź połączenie z API, losowanie, ekran meczu, NEXT/terminarz oraz widoczność herbów/flag.

Pakiet regresyjny backend/logika znajduje się w `../tests/mobile_api_smoke.py`.

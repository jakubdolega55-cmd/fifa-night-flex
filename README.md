# FIFA Night Mobile 1.0

Natywna aplikacja Android (React Native + Expo) sterująca tym samym FIFA Night, którego wersja web/TV działa w Streamlit.

Architektura: `APK -> FastAPI/Render -> Neon <- Streamlit/TV`. APK nie zawiera `DATABASE_URL` i nie łączy się bezpośrednio z Neonem.

## Tożsamość aplikacji

- Expo/EAS: `@kubsi/fifa-night-mobile`
- Android package: `pl.fifanight.flex`
- EAS projectId: `cbb45c49-4757-4587-8a05-e4814cb5f60a`
- Mobile version: `1.0.0`
- Android versionCode: `2`

Nie zmieniaj package ID ani nie twórz nowego keystore, jeśli APK ma aktualizować wcześniej zainstalowaną wersję v0.1.

## API

Profile EAS `preview` i `production` mają ustawione publiczne:

`EXPO_PUBLIC_API_URL=https://fifa-night-api.onrender.com`

To nie jest sekret. Sekrety bazy, sterowania i odczytu zdjęć pozostają wyłącznie na Renderze.

## Build APK

W katalogu `mobile/`:

```powershell
npm.cmd install
npm.cmd run check
npx.cmd expo-doctor
npx.cmd eas-cli@latest build --platform android --profile preview
```

Można też uruchomić `./build-preview.ps1`. EAS powinien użyć istniejących credentials/keystore projektu.

## Kontrola przed instalacją

1. `npm run check` musi zakończyć się bez błędów.
2. `expo-doctor` nie może zgłaszać problemów blokujących build.
3. EAS build `preview` ma wygenerować APK dla `pl.fifanight.flex`.
4. Po instalacji sprawdź połączenie z API, sterowanie, utworzenie testowego turnieju i zapis jednego wyniku APK -> Neon -> Streamlit.
5. Na prawdziwym telefonie sprawdź aparat/galerię, kilka zdjęć jednego meczu, zapis i udostępnianie PNG oraz długie nazwy na małym ekranie.

Pakiet regresyjny backend/logika znajduje się w `../tests/mobile_api_smoke.py`.

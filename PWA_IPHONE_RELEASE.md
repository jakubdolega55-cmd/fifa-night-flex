# FIFA Night — iPhone PWA beta

Dodano trzeci klient FIFA Night:

`Android APK -> FastAPI/Render -> Neon <- Streamlit/TV`

`iPhone PWA  -> FastAPI/Render -> Neon <- Streamlit/TV`

## Założenia

- iPhone nie korzysta ze Streamlit do sterowania turniejem.
- PWA wykorzystuje ten sam React/Expo frontend co Android.
- Ta sama baza, historia, statystyki, Awards i synchronizacja TV.
- Hosting wymaga HTTPS; `render.yaml` zawiera gotową usługę statyczną `fifa-night-pwa`.

## Różnice platformowe

- token sterowania: SecureStore na Androidzie, localStorage w PWA;
- zdjęcia EA FC: Expo ImagePicker obsługuje Web, upload jest konwertowany do Blob/FormData;
- PNG: Android zapisuje do galerii; PWA korzysta z Web Share API, a jeśli nie jest dostępne — pobiera PNG;
- alerty/confirm: web ma własny adapter oparty o `window.alert/confirm`;
- keep-awake: działa tylko, jeśli dana wersja Safari/iOS udostępnia Wake Lock;
- brak agresywnego service workera — aplikacja jest online-first, żeby nowe wersje UI nie utknęły w cache.

## Build

W `mobile/`:

```powershell
npm.cmd install
npm.cmd run check
npx.cmd expo-doctor
npm.cmd run build:web
```

Wynik: `mobile/dist/`.

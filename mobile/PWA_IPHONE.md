# FIFA Night — iPhone PWA

To jest ten sam frontend React/Expo co Android, uruchamiany jako Expo Web/PWA. Nie używa Streamlit do sterowania — komunikuje się bezpośrednio z FastAPI/Render i Neonem.

## Lokalny test

W folderze `mobile`:

```powershell
npm.cmd install
npm.cmd run check
npx.cmd expo-doctor
npm.cmd run web
```

W przeglądarce otwórz adres pokazany przez Expo.

## Build produkcyjny

```powershell
npm.cmd run build:web
```

Gotowe pliki będą w `mobile/dist/`.

## Publikacja

Folder `dist/` można opublikować na dowolnym hostingu HTTPS (np. Netlify, Cloudflare Pages, Render Static Site, EAS Hosting). Aplikacja korzysta z API:

`https://fifa-night-api.onrender.com`

Backend ma już CORS dla klienta webowego.

## Instalacja na iPhone

1. Otwórz publiczny adres FIFA Night w Safari.
2. Udostępnij.
3. `Dodaj do ekranu początkowego`.
4. Uruchamiaj z ikony FIFA Night.

## Ważne różnice względem APK

- token sterowania jest przechowywany w `localStorage` przeglądarki zamiast SecureStore;
- aparat/galeria korzystają z webowego ImagePicker i wymagają bezpośredniego kliknięcia użytkownika;
- zapis PNG na webie pobiera plik, a `UDOSTĘPNIJ` korzysta z Web Share API, jeśli Safari je udostępnia;
- keep-awake zależy od obsługi Wake Lock przez daną wersję Safari/iOS;
- aplikacja wymaga internetu do działania z API; celowo nie dodano agresywnego service workera, żeby stare wersje UI nie zostawały w cache po aktualizacji.

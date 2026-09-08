# FIFA Night Mobile v0.1 (Android / Expo)

Pierwsza natywna wersja mobilna. Nie jest to WebView Streamlita.

## Co działa

- LIVE z automatycznym pollingiem co 5 s.
- Dynamiczny terminarz z kolejnością zgodną z backendem.
- Tabela grupy/liga i TOP strzelców bieżącego FIFA Night.
- Tryb podglądu na każdym urządzeniu.
- Odblokowanie sterowania hasłem administratora; token jest przechowywany przez `expo-secure-store`.
- Wpisanie wyniku aktualnego meczu, karne oraz opcjonalni strzelcy.
- Cofnięcie ostatniego wyniku na urządzeniu ze sterowaniem.
- Podstawowe Statystyki + profile/Gablota.
- AWARDS LIVE w trybie podglądu.

## Start developerski

1. Zainstaluj Node.js >= 22.13.
2. W katalogu `mobile` uruchom `npm install`.
3. Dla pewności dopasuj natywny pakiet do SDK: `npx expo install expo-secure-store`.
4. Skopiuj `.env.example` do `.env` i wpisz `EXPO_PUBLIC_API_URL`.
5. Uruchom `npx expo start`.

## APK dla znajomych

Projekt ma `eas.json` z profilem `preview`, który generuje instalowalny APK. Po skonfigurowaniu EAS użyj:

`eas build --platform android --profile preview`

Package ID to `pl.fifanight.flex`. Nie zmieniaj go między aktualizacjami, jeśli nowe APK mają aktualizować poprzednią instalację.

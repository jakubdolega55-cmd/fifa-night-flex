# CHECKPOINT 2026-10-20 — R23 — Android APK PNG save

## Zakres
Naprawa wspólnego helpera PNG używanego przez:
- `mobile/src/FifaScreen.tsx` — podsumowanie świeżo zakończonego turnieju,
- `mobile/src/StatsScreen.tsx` — historia turnieju i rozliczenia,
- `mobile/src/AwardsScreen.tsx` — grafiki Awards / sezonu.

## Przyczyna
Projekt działa na Expo SDK 57. W SDK 57 stary interfejs MediaLibrary został przeniesiony pod `expo-media-library/legacy`.
`saveToLibraryAsync()` wywołane z root importu `expo-media-library` jest metodą deprecated i może rzucić błąd w runtime.

R22 miał:
```ts
import * as MediaLibrary from 'expo-media-library';
```

a następnie:
```ts
await MediaLibrary.saveToLibraryAsync(result.uri);
```

## Poprawka R23
W `mobile/src/export.ts` zmieniono wyłącznie import MediaLibrary:
```ts
import * as MediaLibrary from 'expo-media-library/legacy';
```

Pozostała logika jest bez zmian:
1. PNG pobierane do cache przez `expo-file-system/legacy`,
2. `UDOSTĘPNIJ` korzysta z `expo-sharing`,
3. `ZAPISZ PNG` prosi o write-only permission i zapisuje plik do galerii przez legacy MediaLibrary.

Dzięki temu jeden fix obejmuje wszystkie ekrany używające `getPng()`.

## Wersjonowanie
- app version: `1.1.3`
- Android `versionCode`: `15` — bez zmiany zgodnie z handoffem, o ile V15 nie został jeszcze zainstalowany/dystrybuowany jako build wymagający upgrade'u.

## Testy
PASS:
- `tests/mobile_png_export_sdk57_smoke.py`
  - potwierdza Expo SDK 57,
  - wymusza import `expo-media-library/legacy`,
  - blokuje powrót root importu,
  - sprawdza zachowanie ścieżek SAVE / SHARE / download.

NOT RUN / NOT PASS:
- pełny `npm install && npm run check` — instalacja zależności przekroczyła limit czasu środowiska i nie została oznaczona jako PASS.

## Fizyczny retest APK
Po zbudowaniu APK sprawdzić osobno:
1. zakończony turniej → `ZAPISZ PNG`,
2. zakończony turniej → `UDOSTĘPNIJ`,
3. rozliczenie → `ZAPISZ PNG`,
4. rozliczenie → `UDOSTĘPNIJ`,
5. Awards / podsumowanie sezonu → zapis i share,
6. potwierdzić, że pliki faktycznie pojawiają się w galerii Androida.

## Następny task po fizycznym potwierdzeniu R23
R24 — AI screenshot parser / Events / trudne karne.

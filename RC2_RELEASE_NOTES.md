# FIFA Night Mobile 1.0.1 RC2

## Cel tej wersji

RC2 skupia się na tym, aby **telefon był pilotem**, a laptop/TV był ekranem dla wszystkich uczestników — szczególnie podczas losowań.

## Telefon -> Streamlit/TV

Streamlit może przełączyć setup na `📺 TV` już przed rozpoczęciem pierwszego meczu. Losowania uruchamiane w APK są publikowane przez backend jako krótka kolejka zdarzeń. TV pobiera ją bezpośrednio z API co ok. 650 ms i odtwarza zdarzenia w kolejności.

Obsługiwane efekty:
- kolejność draftu,
- koło fortuny drużyn,
- Wild Card,
- wybory draftu,
- losowanie grup/drabinki/ustawienia ligi,
- specjalne losowania w trakcie DE i faz grupowych,
- przejście do startu turnieju.

## Mobilny UX

- prawdziwy wizualny spinner koła drużyn;
- sekwencyjne reveal losowań;
- mocniejsze spotlighty QF/SF/WB Final/LB Final/Final/Reset Final;
- celebracja mistrza po zakończeniu turnieju;
- niedostępni piłkarze tylko przy właściwym aktualnym/następnym meczu.

## Odznaki

W profilu gracza zarówno w Streamlit, jak i w APK dostępny jest katalog `❔ Jak zdobywać`, który pokazuje wszystkie odznaki, warunek zdobycia, status oraz postęp tam, gdzie można go policzyć.

## Start aplikacji

APK renderuje aktywny turniej po `/live` i nie blokuje pierwszego ekranu oczekiwaniem na `/config`. Darmowy Render nadal może mieć cold start po okresie bezczynności — wtedy pierwsze połączenie może trwać kilkadziesiąt sekund.

## Wersje

- Mobile: `1.0.1`
- Android `versionCode`: `3`
- API: `1.0.1`
- Android package pozostaje: `pl.fifanight.flex`

## Walidacja w środowisku przygotowującym

- Python `py_compile`: PASS
- backend/API smoke: **50/50 PASS**
- TypeScript/JSX syntax check: PASS
- JSON config validation: PASS

Przed EAS należy na prywatnym komputerze ponownie wykonać `npm.cmd install`, `npm.cmd run check` oraz `npx.cmd expo-doctor`.

# FIFA NIGHT FLEX — LOCAL CRESTS PACKED — 2026-10-01

- 14 klubowych herbów zostało znormalizowanych do lokalnych PNG 256x256.
- Pliki są fizycznie spakowane w `assets/teams/clubs/` i `mobile/assets/teams/clubs/`.
- Normalny start/build APK/PWA oraz runtime NIE pobierają herbów z internetu.
- `npm run verify:teams` sprawdza komplet 14 plików przed startem/buildem mobilnym.
- Streamlit używa lokalnych PNG jako data URI.
- Chelsea: celowo pominięta zgodnie z decyzją użytkownika; jeśli kiedyś pojawi się ręcznie, fallback = inicjały.
- Napoli: bez lokalnego pliku; fallback = inicjały, logika puli/turnieju bez zmian.
- AC Milan: zastąpiono wcześniejszy ucięty materiał pełnym, nieuciętym lokalnym assetem.
- Usunięto niepotrzebny vendor/download step i manifest z URL-ami; asset bundle jest samowystarczalny.
- APK: TAK (zmiana asset bundle/mobile visuals). `versionCode` pozostaje 14, jeśli V14 nie był jeszcze fizycznie zbudowany/zainstalowany.

# HANDOFF — FIFA Night Mobile v0.1

## Źródło prawdy

Bazą jest FIFA Night Flex v1.8.0 TV Mode Hotfix 18. Streamlit i FastAPI korzystają z tych samych `database.py` i `logic.py` oraz z tego samego `DATABASE_URL`.

## Gotowe

- FastAPI (`mobile_api.py`) z publicznym LIVE, terminarzem, statystykami, profilem i AWARDS.
- HMAC controller tokens po haśle `ADMIN_PASSWORD`.
- Natywny Android frontend React Native / Expo w `mobile/`.
- Polling LIVE co 5 s.
- Zapis bieżącego wyniku, karnych i opcjonalnych strzelców.
- Cofnięcie ostatniego wyniku.
- SecureStore dla tokenu urządzenia.
- `render.yaml` do bezpłatnego testowego hostingu API.
- `eas.json` z profilem `preview` generującym APK do instalacji bez Google Play.

## Następny etap v0.2

1. Start FIFA Night z Androida.
2. Wybór liczby graczy i składu.
3. Flagi „gra za kasę”, stawka i jackpot preview.
4. Wybór formatu.
5. Natywny draft / wheel / structure draw.
6. Specjalne losowania DE5/DE7/DE8 i playoff reveal.
7. Po v0.2 pełny test jednego całego turnieju bez używania Streamlita do sterowania.

## Ważne

Nie wkładać `DATABASE_URL` ani `ADMIN_PASSWORD` do `mobile/.env`. APK zna tylko publiczny `EXPO_PUBLIC_API_URL`. Sekrety pozostają na serwerze FastAPI.

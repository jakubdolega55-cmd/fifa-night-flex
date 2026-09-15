# FIFA Night Flex 1.1.0 — instrukcja wdrożenia

## 0. Przed wdrożeniem
1. Zrób backup / snapshot bazy Neon.
2. Nie uruchamiaj nowego turnieju w trakcie podmiany wersji.
3. Zachowaj poprzedni działający ZIP/revision jako rollback.

## 1. Render — API
W repozytorium/serwisie API podmień kod na zawartość tego wydania.

Wymagane pliki backendu to m.in.:
- `mobile_api.py`
- `database.py`
- `logic.py`
- `export_utils.py`
- `scorer_seeds.py`
- `requirements-api.txt`
- `render.yaml` (jeżeli Blueprint jest używany)

Render API:
- build: `pip install -r requirements-api.txt`
- start: `uvicorn mobile_api:app --host 0.0.0.0 --port $PORT`
- health check: `/api/v1/health`

Zmienne środowiskowe pozostają:
- `DATABASE_URL`
- `ADMIN_PASSWORD`
- `MOBILE_TOKEN_SECRET`
- `OPENAI_API_KEY` (jeżeli używany Vision/AI)
- `GOOGLE_VISION_API_KEY` (jeżeli używany)

Po starcie API `db.init_schema()` wykona bezpieczną, idempotentną migrację Neon. Nie uruchamiaj osobnego ręcznego ALTER TABLE.

### Kontrola po deployu API
- otwórz `/api/v1/health` i sprawdź HTTP 200;
- sprawdź `/api/v1/config`, czy zwracane są FC26/FC27 oraz formaty do 10 graczy;
- otwórz istniejącą historię i potwierdź, że stare turnieje działają jako FC26.

## 2. Streamlit laptop/TV
Podmień pełny zestaw plików aplikacji, szczególnie:
- `app.py`
- `database.py`
- `logic.py`
- `ui.py`
- `export_utils.py`
- `scorer_seeds.py`
- `requirements.txt`

Uruchom/redeploy Streamlit dopiero po udanym starcie API. Streamlit również wywołuje `init_schema()`, więc operacja jest bezpieczna po migracji wykonanej już przez API.

### Kontrola Streamlit
- ekran główny: `1 VS 1`, `3`, `4`, `5`, `6`, `7`, `Więcej zawodników` -> `8`, `9`, `10`;
- przed startem można wybrać FC26/FC27;
- stary turniej/history działa;
- nowy testowy turniej 9 lub 10 osób przechodzi setup bez błędu;
- deterministic cross (np. A1-B2/B1-A2) pokazuje reveal, nie fałszywe losowanie.

## 3. PWA na Render
Katalog: `mobile/`

Build:
```bash
npm install
npm run check
npx expo-doctor
npm run build:web
```

Konfiguracja Render Static Site:
- Root Directory: `mobile`
- Build Command: `npm install && npm run build:web`
- Publish Directory: `dist`
- `EXPO_PUBLIC_API_URL=https://fifa-night-api.onrender.com`
- Node: 22.16.0 (zgodnie z `render.yaml`)

Po deployu na iPhone sprawdź odświeżenie PWA / usunięcie starego cache, jeżeli przeglądarka nadal pokazuje stary bundle.

## 4. Android APK
W katalogu `mobile/`:
```powershell
npm install
npm run check
npx expo-doctor
npx eas build --platform android --profile preview
```

Wersja aplikacji: `1.1.0`, Android `versionCode: 5`.

## 5. Minimalny smoke produkcyjny po wdrożeniu
1. Zaloguj sterowanie mobilne.
2. Utwórz TESTOWY turniej FC27, 9 osób.
3. Sprawdź przypisanie drużyn oraz ekran LIVE na telefonie i TV.
4. Sprawdź jeden visible draw/reveal.
5. Zapisz jeden wynik i sprawdź, czy oba ekrany widzą tę samą zmianę.
6. Cofnij wynik i potwierdź, że już publicznie wylosowana source-level ścieżka DE nie losuje się ponownie.
7. Usuń/porzuć testowy turniej zgodnie z normalną procedurą.

## 6. Rollback
Jeżeli API po wdrożeniu nie przechodzi health checku:
1. przywróć poprzednią revision/kod;
2. nie cofaj automatycznie schematu Neon — nowe kolumny/tabele są addytywne i stary kod może je ignorować;
3. dopiero po przywróceniu backendu sprawdź historię i aktywny turniej.

Nie usuwaj ręcznie `game_version`, `footballer_rosters` ani `footballer_aliases` w ramach rollbacku.

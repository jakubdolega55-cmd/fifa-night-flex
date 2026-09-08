# FIFA Night Mobile v0.1 — pierwszy działający etap

Ta paczka zawiera dotychczasową aplikację Streamlit oraz pierwszy natywny frontend Android + FastAPI. Oba klienty pracują na tej samej bazie Neon.

## Synchronizacja ze Streamlit

- Wynik zapisany w Androidzie trafia przez FastAPI do tego samego Neona, którego używa Streamlit.
- Streamlit TV Mode pobiera stan co 5 sekund, więc podczas aktywnego turnieju automatycznie zobaczy wynik i nową kolejność LIVE.
- Zwykłe ekrany Streamlita pobierają świeże dane przy rerunie/interakcji. Nie powstaje osobna kopia turnieju ani osobna baza dla telefonu.
- Android również odświeża LIVE co 5 sekund, więc telefony w trybie podglądu widzą zmiany bez ręcznego odświeżania.

## Mobile v0.1

Działa już:

- natywny interfejs React Native / Expo, nie WebView;
- ekran LIVE z aktualnym i następnym meczem;
- dynamiczny terminarz;
- tabela grupowa/liga i strzelcy turnieju;
- podstawowe Statystyki + profile i Gablota;
- AWARDS LIVE;
- podgląd jako tryb domyślny;
- odblokowanie sterowania hasłem administratora;
- token sterowania w Android SecureStore;
- wpisanie bieżącego wyniku, karnych i opcjonalnych strzelców;
- cofnięcie ostatniego wyniku z urządzenia sterującego.

## Architektura

Android APK → FastAPI → Neon PostgreSQL ← Streamlit

APK nigdy nie dostaje `DATABASE_URL`. W aplikacji zapisany jest wyłącznie publiczny adres API. Hasło administratora jest sprawdzane na serwerze, a telefon przechowuje podpisany token sterowania.

## Uruchomienie API lokalnie

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\\Scripts\\activate
pip install -r requirements-api.txt
export ADMIN_PASSWORD='twoje-haslo'
export MOBILE_TOKEN_SECRET='dlugi-losowy-sekret'
# DATABASE_URL pomiń dla lokalnego SQLite albo ustaw ten sam Neon co Streamlit
uvicorn mobile_api:app --reload --port 8000
```

Health check: `http://127.0.0.1:8000/api/v1/health`

## Publiczne API bez kosztu na start

`render.yaml` jest przygotowany pod darmowy Web Service w Render. Ustaw w Render trzy sekrety: `DATABASE_URL`, `ADMIN_PASSWORD`, `MOBILE_TOKEN_SECRET`. `DATABASE_URL` ma być identyczny z używanym przez Streamlit Cloud.

Darmowy Render usypia usługę po okresie bezczynności, więc pierwsze otwarcie po dłuższej przerwie może mieć cold start. Gdy telefony używają LIVE i odpyytują API co 5 sekund, usługa pozostaje aktywna podczas turnieju.

## Android

Wejdź do `mobile/`, skopiuj `.env.example` jako `.env` i ustaw publiczny URL FastAPI:

```env
EXPO_PUBLIC_API_URL=https://twoje-api.onrender.com
```

Następnie:

```bash
npm install
npx expo install expo-secure-store
npx expo start
```

Do prywatnego APK przygotowany jest profil `preview` w `eas.json`:

```bash
eas build --platform android --profile preview
```

Profil `preview` generuje instalowalny `.apk`, a package ID pozostaje `pl.fifanight.flex`, żeby kolejne pliki mogły aktualizować tę samą aplikację.

## Co dalej

v0.2: tworzenie turnieju z telefonu, wybór uczestników, „gra za kasę”, wybór formatu i cały proces losowania/draftu w natywnym UI.

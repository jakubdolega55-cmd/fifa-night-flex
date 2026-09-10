# FIFA Night — Mobile 1.0 release source

Data przygotowania: 2026-09-10.

## Status

Ten stan repozytorium jest przygotowany jako finalny **kod źródłowy Mobile 1.0** do zbudowania APK. Nie zmieniono Android package (`pl.fifanight.flex`) ani EAS projectId, dzięki czemu build ma korzystać z istniejącej tożsamości aplikacji i istniejącego keystore.

W środowisku przygotowującym release wykonano:

- `python -m py_compile app.py database.py logic.py mobile_api.py export_utils.py scorer_seeds.py ui.py` — PASS;
- `python tests/mobile_api_smoke.py` — **49 PASS / 0 FAIL**;
- niezależny offline strict-check własnego kodu TypeScript/JSX — PASS;
- walidację plików JSON (`package.json`, `app.json`, `eas.json`, `tsconfig.json`) — PASS;
- audyt usunięcia mechanizmu blokowania Historii z aktywnego kodu — PASS;
- audyt normalnego UI APK pod kątem eksponowania technicznego `AI/OpenAI` — 0 wystąpień.

Pełnego `npm install` / `npm run check` na realnych zależnościach Expo oraz `expo-doctor` nie dało się wykonać w środowisku przygotowującym release, ponieważ nie było dostępu do npm i nie istniał lokalny `node_modules`. Dlatego finalny binarny APK wymaga jeszcze przejścia poniższego gate'u w środowisku z dostępem do npm/EAS.

## Zakres pokryty testami

Smoke test obejmuje 1 VS 1 i wszystkie formaty 3–8, setup/draft/koło/Wild Card/losowanie struktury, wyniki i karne, strzelców, `+ DO LISTY`, skan-preview i korekty zdarzeń, deduplikację nakładających się zdjęć, samobóje/karne/kartki/kontuzje, konflikt dwóch urządzeń, undo, dokładne przesunięcie o jeden grywalny mecz, matematycznie bezpieczne `Pomiń`, zmianę test -> oficjalny, zakończenie jako NIEDOKOŃCZONY, Historię/delete, finanse/settlement, PNG, profile/statystyki/Awards/kamienie milowe oraz 1 VS 1 bez kasy.

## Finalny gate APK

W `mobile/` uruchom kolejno:

```powershell
npm.cmd install
npm.cmd run check
npx.cmd expo-doctor
npx.cmd eas-cli@latest build --platform android --profile preview
```

Alternatywnie: `./build-preview.ps1`.

Po buildzie zainstaluj APK jako aktualizację istniejącej aplikacji i wykonaj krótki smoke na fizycznym Androidzie:

- Ustawienia -> połączenie API i sterowanie;
- test 3–8 bez sterowania oraz oficjalny 3–8 ze sterowaniem;
- jeden zapis wyniku i potwierdzenie APK -> Neon -> Streamlit;
- konflikt zapisu z drugim urządzeniem;
- aparat/galeria i prawdziwe screeny EA FC (także 2+ zdjęcia);
- PNG: ZAPISZ i UDOSTĘPNIJ;
- mały ekran: długie nicki, długa nazwa drużyny, klawiatura, modale i drzewko DE.

## Render

`render.yaml` wymaga: `DATABASE_URL`, `ADMIN_PASSWORD`, `MOBILE_TOKEN_SECRET`, `OPENAI_API_KEY`; `GOOGLE_VISION_API_KEY` może pozostać opcjonalnie do diagnostyki. Po deployu endpoint `/api/v1/health` ma zwracać `api_version: 1.0.0`.

## EAS API URL

`mobile/eas.json` ustawia dla `preview` i `production`:

`EXPO_PUBLIC_API_URL=https://fifa-night-api.onrender.com`

Jest to publiczny adres usługi, nie sekret.

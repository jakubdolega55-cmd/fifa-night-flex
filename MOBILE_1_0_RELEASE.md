# FIFA Night — Mobile 1.0.1 RC2 release source

Data przygotowania: 2026-09-11.

## Status

Ten stan repozytorium jest przygotowany jako release candidate **Mobile 1.0.1 RC2** do zbudowania APK. Nie zmieniono Android package (`pl.fifanight.flex`) ani EAS projectId, dzięki czemu build ma korzystać z istniejącej tożsamości aplikacji i istniejącego keystore.

W środowisku przygotowującym release wykonano:

- `python -m py_compile app.py database.py logic.py mobile_api.py export_utils.py scorer_seeds.py ui.py` — PASS;
- `python tests/mobile_api_smoke.py` — **50 PASS / 0 FAIL**;
- offline kontrolę składni TypeScript/JSX (`tsc --noCheck`) — PASS;
- walidację plików JSON (`package.json`, `app.json`, `eas.json`, `tsconfig.json`) — PASS;
- audyt usunięcia mechanizmu blokowania Historii z aktywnego kodu — PASS;
- audyt normalnego UI APK pod kątem eksponowania technicznego `AI/OpenAI` — 0 wystąpień.

Pełnego `npm install` / `npm run check` na realnych zależnościach Expo oraz `expo-doctor` nie dało się wykonać w środowisku przygotowującym RC2, ponieważ nie ma tu `node_modules` ani dostępu do npm. Poprzednia paczka przeszła na prywatnym komputerze użytkownika **21/21 Expo Doctor**, ale po zmianach RC2 należy ponowić poniższy gate przed EAS buildem.


## RC2 — najważniejsze zmiany

- telefon jest pilotem losowań, a Streamlit może wejść w **📺 TV już podczas setupu**;
- TV pobiera lekką kolejkę zdarzeń losowania bezpośrednio z API co ok. **650 ms**, więc szybkie akcje z telefonu są odtwarzane po kolei zamiast zlewać się do końcowego stanu;
- zsynchronizowane są: kolejność draftu, wybór drużyny, **koło fortuny**, Wild Card, losowanie struktury i losowania specjalne podczas turnieju;
- dodano TV gate także do etapu **koła drużyn**;
- mobilka ma mocniejsze wejścia dla ćwierćfinału/półfinału/finałów oraz celebrację mistrza;
- niedostępni piłkarze są pokazywani tylko przy meczu graczy, których dotyczą — osobno dla **TERAZ** i **NASTĘPNY**;
- katalog odznak ma `? / Jak zdobywać` zarówno w Streamlit, jak i w APK; pokazuje warunek, status i dostępny postęp;
- start APK nie czeka już na cięższe `/config`; aktywny turniej renderuje się po odpowiedzi `/live`. Cold start darmowego Rendera nadal może potrwać kilkadziesiąt sekund.

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

`render.yaml` wymaga: `DATABASE_URL`, `ADMIN_PASSWORD`, `MOBILE_TOKEN_SECRET`, `OPENAI_API_KEY`; `GOOGLE_VISION_API_KEY` może pozostać opcjonalnie do diagnostyki. Po deployu endpoint `/api/v1/health` ma zwracać `api_version: 1.0.1`.

## EAS API URL

`mobile/eas.json` ustawia dla `preview` i `production`:

`EXPO_PUBLIC_API_URL=https://fifa-night-api.onrender.com`

Jest to publiczny adres usługi, nie sekret.

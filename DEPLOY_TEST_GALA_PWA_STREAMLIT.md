# Test Gali — PWA + Streamlit

## 1. GitHub

Rozpakuj ZIP i skopiuj **zawartość paczki do głównego katalogu repozytorium**.
Nie wrzucaj zewnętrznego folderu jako dodatkowego poziomu.

W root repo mają być m.in.:
- `app.py`
- `database.py`
- `logic.py`
- `mobile_api.py`
- `ui.py`
- `render.yaml`
- `requirements-api.txt`
- folder `mobile/`

Zrób commit/push na branch używany przez Render i Streamlit.

## 2. Render — API

Usługa `fifa-night-api`:
- Build: `pip install -r requirements-api.txt`
- Start: `uvicorn mobile_api:app --host 0.0.0.0 --port $PORT`
- Health: `/api/v1/health`

Zachowaj istniejące sekrety/zmienne:
- `DATABASE_URL`
- `ADMIN_PASSWORD`
- `MOBILE_TOKEN_SECRET`
- `OPENAI_API_KEY`
- `GOOGLE_VISION_API_KEY` jeśli używasz

Na czas testów:
- `FIFA_GALA_TEST_MODE=0`

W `render.yaml` tej paczki tryb testowy jest wpisany jawnie jako `1`.

## 3. Render — PWA

Usługa `fifa-night-pwa`:
- rootDir: `mobile`
- Build: `npm install && npm run build:web`
- Publish: `./dist`
- `EXPO_PUBLIC_API_URL=https://fifa-night-api.onrender.com`

Do pierwszego testu Gali nie potrzebujesz APK.

## 4. Streamlit

Streamlit korzysta z tego samego kodu i bazy.
Main file: `app.py`.

Na czas testu Gala ma działać w test mode. Kod domyślnie używa `1`; jeśli na hostingu ustawiasz własne env/secrets, ustaw także:

`FIFA_GALA_TEST_MODE = "0"`

## 5. Pierwszy test bez wybierania laureatów

Nie musisz najpierw wybierać wszystkich laureatów.
W test mode:
- ręcznie wybrany laureat ma pierwszeństwo;
- przy braku wyboru aplikacja może użyć lidera statystycznego jako laureata testowego;
- kategoria bez kandydatów może zostać pominięta.

Na komputerze:
1. Otwórz Streamlit.
2. Wejdź w `GALA`.
3. Ustaw przeglądarkę na pełny ekran/F11.

Na telefonie:
1. Otwórz PWA.
2. Zaloguj/przejmij sterowanie.
3. Wejdź w `GALA`.
4. Uruchom galę.
5. Po każdym revealu używaj `NASTĘPNA KATEGORIA`.

Sprawdź:
- intro;
- TOP3 pojawiające się co ok. 2.5 s;
- suspense;
- reveal;
- HOLD laureata bez automatycznego przejścia;
- `POWTÓRZ KATEGORIĘ`;
- synchronizację PWA -> TV;
- specjalne ekrany Rywalizacji i Meczu Roku;
- efekty Supersnajpera, Progresu i Króla Końcówek;
- finał Gracza Roku.

## 6. Drugi test z ręcznymi laureatami

Wybierz kilka kategorii ręcznie, najlepiej tak, aby wybrany laureat nie był liderem rankingu. Uruchom galę ponownie i sprawdź, czy używa wyboru organizatora.

## 7. Czyszczenie po teście

W test mode w panelu Awards jest przycisk resetujący wszystkich laureatów danego roku.
Reset:
- usuwa wybory laureatów;
- resetuje stan Gali;
- NIE usuwa meczów, rankingów ani statystyk.

Po teście możesz więc wrócić do czystego stanu wyboru Awards.

## 8. Po zakończeniu fazy testowej

Ustaw `FIFA_GALA_TEST_MODE=0` na API i środowisku Streamlit.
Po tej zmianie:
- testowy reset wszystkich laureatów znika;
- Gala jest dostępna dopiero po kompletnym, poprawnym wyborze wymaganych laureatów.

## 9. Czego jeszcze nie uznajemy za potwierdzone

- realny Render deploy tej konkretnej paczki;
- realna synchronizacja telefon/TV przy słabym internecie;
- pełny build PWA po `npm install` w tym środowisku;
- EAS/APK;
- parser Summary na finalnych screenach użytkownika.

# FIFA Night Flex 1.1.3 — TEST CANDIDATE

Aktualna paczka testowa: Streamlit laptop/TV + FastAPI/Render + Neon PostgreSQL + PWA/Android.

## Najważniejszy cel tej paczki

Test end-to-end **Gali Awards** na realnym układzie:

`telefon/PWA -> FastAPI/Render -> Neon -> Streamlit/TV`

Nie trzeba budować APK do pierwszego testu. Telefon może działać przez PWA, a komputer/TV przez Streamlit.

## Gala Awards

- 18 kategorii w ustalonej kolejności od najmniej ważnej do Gracza Roku.
- Telefon uruchamia kolejną kategorię jednym przyciskiem.
- TV automatycznie przechodzi: intro -> TOP3 -> suspense -> laureat.
- Laureat pozostaje na ekranie bez limitu czasu do kliknięcia `NASTĘPNA KATEGORIA`.
- TOP3 jest zapisywane w losowej kolejności, bez pokazywania miejsc 1/2/3.
- Tryb testowy pozwala wystartować Galę bez pełnego zestawu laureatów.
- W test mode dostępny jest reset wszystkich laureatów danego roku.
- Finalnie należy ustawić `FIFA_GALA_TEST_MODE=0`.

## Summary z ekranów EA FC

Backend ma przygotowaną obsługę mieszanych zdjęć Events + Summary i magazynowanie danych Summary bez archiwizowania zdjęć. Warstwa Summary może wpływać na wybrane Awards. Parser wymaga jeszcze praktycznej kalibracji na realnych screenach FC26/FC27.

## FC26 / FC27 — tryb drużyn

Domyślnie aplikacja działa na **klubach**.

### FC26
- tylko kluby;
- dotychczasowa logika Real Madrid helper/banned pozostaje.

### FC27 — kluby
Koło:
- Real Madrid
- PSG
- Bayern Monachium
- FC Barcelona
- Arsenal

Wild Cardy w rankingu podpowiedzi:
- Manchester City
- Atletico
- Liverpool
- Man United
- Inter
- BVB
- Napoli
- Chelsea
- Tottenham
- AC Milan

Real i PSG mają obniżoną szansę trafienia dla zwycięzcy/finalisty poprzedniego turnieju.

### FC27 — reprezentacje
Tryb włączany w ustawieniach organizatora. Francja jest banned.

Koło:
- Hiszpania
- Anglia
- Brazylia
- Niemcy
- Portugalia

Wild Cardy:
- Włochy
- Argentyna
- Holandia
- Belgia
- Chorwacja
- Dania
- Maroko
- Turcja
- Szwajcaria

Hiszpania i Brazylia mają obniżoną szansę trafienia dla zwycięzcy/finalisty poprzedniego turnieju.

## Wersje

- Mobile/PWA: `1.1.3`
- Android versionCode: `8`
- API: `1.1.3`

## Testy backendu

W tym kandydacie przeszły m.in.:
- Python compile
- Awards/Gala backend + TV + controller + closeout
- mobile API 51/51
- FC27 clubs/nationals
- FC26/FC27 versioning/aliases
- Swiss8/10
- Double Elimination
- smart scheduler
- draw policy
- forfeit
- group tiebreak
- wheel shrink 10 -> 0

Nie wykonano w tym środowisku fizycznego testu PWA na Renderze ani Streamlit TV po deployu. Nie wykonano też EAS build APK.

## Start

Najpierw przeczytaj `DEPLOY_TEST_GALA_PWA_STREAMLIT.md`.

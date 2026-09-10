# FIFA Night Flex v1.8.0 — Hotfix 22: nowe odznaki z eventów

Pliki do podmiany:
- `app.py`
- `database.py`
- `mobile_api.py`

## Zmiana Perfect Night
`Perfect Night` wymaga teraz mistrzostwa po samych zwycięstwach w regulaminowych 90 minutach. Znana seria karnych lub potwierdzony gol w dogrywce wyklucza odznakę. Dla starych meczów bez szczegółowej osi czasu aplikacja nie zgaduje niewidocznej dogrywki.

## Nowe odznaki
- 🔥 Nie do zabicia — zwycięstwo po przegrywaniu co najmniej 3 golami.
- 🟥 W dziesiątkę raźniej — zwycięstwo mimo czerwonej kartki dla własnej drużyny.
- 🎯 Egzekutor z wapna — 10 goli z karnych w trakcie meczu.
- ➕ Po godzinach — gol na wagę zwycięstwa w dogrywce.
- 🎩 Hat-trick Express — hat-trick jednego piłkarza w maksymalnie 15 minut.
- 🪓 Rzeźnik — 25 pkt dyscyplinarnych (żółta=1, czerwona=3).
- 🃏 Joker — zmiennik zdobywa gola na wagę zwycięstwa.

Odznaki wymagające dokładnej kolejności bramek są liczone wyłącznie z meczów mających kompletny szczegółowy przebieg. Techniczny gol +1 w finale Double Elimination nie tworzy odznak.

## Zmiany przy zmianach zawodników
Prompt AI zapisuje zmianę jednoznacznie:
- `footballer_name` / `player` = zawodnik WCHODZĄCY,
- `related_footballer_name` / `related_player` = zawodnik SCHODZĄCY.

W korekcie wydarzeń Streamlit pojawia się osobne pole dla zawodnika schodzącego, a historia pokazuje strzałki wejście/zejście. To jest potrzebne do poprawnego wykrywania odznaki Joker.

# FIFA Night Flex v1.8.0 — Hotfix 10

## Historia nowych meczów
- Mecze zapisane z odczytu zdjęć pokazują w Historii dokładny przebieg z minutami.
- Obsługiwane wpisy: zwykły gol, gol z karnego, samobój, techniczny samobój DE, niewykorzystany karny, żółta/czerwona kartka i zmiana.
- Starsze mecze bez `match_events` nadal pokazują dotychczasową zagregowaną listę strzelców.

## Administracja
- Usunięto panel `Historia i baza` z ekranu tworzenia turnieju.
- Zmiana nazwy gracza została przeniesiona do `⚙️ Ustawienia`.
- Blokowanie/odblokowywanie usuwania Historii zostało przeniesione do `⚙️ Ustawienia`.
- W samej zakładce `🗂️ Historia` pojawia się zabezpieczone hasłem usuwanie wybranej pozycji, jeśli Historia jest odblokowana.
  - dla 1 VS 1: usuwa cały wybrany mecz 1 VS 1 wraz z eventami;
  - dla turnieju wielomeczowego: usuwa cały wybrany turniej.
- Pojedynczego meczu ze środka zamkniętego turnieju wielomeczowego nie usuwamy, ponieważ zerwanie jednego wyniku mogłoby unieważnić drabinkę, awanse i mistrza.

## Pliki do podmiany
- `app.py`
- `database.py`

# Hotfix 25 — TV AUTO

## Co dodano

W widoku `📺 TV` pełnego FIFA Night dostępne są dwa tryby:

- `📺 LIVE` — dotychczasowy, stały ekran aktualnego meczu;
- `🔄 AUTO` — automatyczny pokaz informacji turniejowych.

AUTO zmienia ekran mniej więcej co 10 sekund:

1. `🎮 TERAZ / NASTĘPNY` — bieżący mecz oraz kolejny mecz wybrany przez istniejący algorytm kolejności;
2. `🗺️ SYTUACJA TURNIEJU` — tabela/grupy albo drzewko Double Elimination;
3. `⚽ WYNIKI I STRZELCY` — ostatnie rozegrane mecze i TOP 5 strzelców bieżącego FIFA Night.

## Ważne

Hotfix nie modyfikuje logiki harmonogramu. `database.py`, `logic.py`, `ui.py` i `export_utils.py` pozostają bez zmian względem Hotfix 24.

Algorytm nadal sam ustala kolejność tak, aby zachować dotychczasowe zasady i ograniczać zbędne oczekiwanie graczy. Funkcja `Przesuń mecz na później` pozostaje awaryjną ręczną opcją na sytuacje typu spóźnienie, telefon, wyjście gracza itp.

Tryb AUTO nie jest pokazywany dla pojedynczego meczu `1 vs 1`, gdzie nie ma sensu przełączać tabeli/drabinki.

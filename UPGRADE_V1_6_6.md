# FIFA Night Flex v1.6.6

- dodano losowanie par kolejnej rundy Winners Bracket po pierwszej rundzie Double Elimination dla 7 i 8 graczy,
- w 5-osobowym Double Elimination pozostaje istniejące losowanie przeciwnika dla wolnego losu,
- losowanie uwzględnia odpoczynek: zwycięzca ostatniego meczu pierwszej rundy trafia do drugiego meczu kolejnej rundy,
- poprawiono czytelność eksportu PNG; naprawiono także awaryjny font, który na Streamlit Cloud mógł renderować tekst bardzo mały,
- grafika ma większe napisy i prostszy układ,
- do grafiki dodano drużynę mistrza i finalisty, bilans mistrza oraz statystyki całego turnieju.

Aktualizacja z v1.6.5: podmień `app.py`, `database.py`, `logic.py`, `ui.py`, `export_utils.py`.

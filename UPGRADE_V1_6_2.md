# FIFA Night Flex v1.6.2

Hotfix losowania Wild Card:
- naprawiono `ValueError` po zatwierdzeniu konkretnej drużyny Wild Card,
- koło zapamiętuje osobno wylosowany slot Wild Card i wybraną nazwę drużyny,
- po wyborze np. Inter animacja kończy się na właściwym slocie Wild Card, a wynik pokazuje `Inter`,
- `render_wheel()` ma dodatkowe zabezpieczenie dla starych stanów sesji z v1.6.1.

Aktualizacja z v1.6.1: podmień `app.py` i `ui.py`.

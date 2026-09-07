# FIFA Night Flex v1.7.6

## Co nowego

### 1. Nowy gracz gra wcześniej
Jeżeli w obecnym składzie jest osoba, która nie grała w bezpośrednio poprzednim turnieju tej samej klasy (oficjalny/testowy), aplikacja traktuje ją jako świeżego gracza. Pary i grupy pozostają losowe, ale kolejność niezależnych meczów otwierających jest ustawiana tak, aby świeży gracz zagrał możliwie wcześnie.

W DE 5/7 świeży gracz ma wagę 0.15 przy losowaniu Szczęśliwego losu. Szansa nie spada do zera, ale jest wyraźnie niższa niż u graczy, którzy właśnie grali poprzedni turniej.

### 2. Stawki i rozliczenia
Przy tworzeniu turnieju pojawiło się pole `Stawka na osobę (zł)`. Każdy uczestnik wpłaca stawkę, zwycięzca bierze pulę.

W `Statystyki → Rozliczenia` można:
- wybrać kilka ostatnich oficjalnych turniejów,
- poprawić stawkę zakończonego turnieju,
- zobaczyć skompensowany bilans,
- dostać listę końcowych przelewów,
- skopiować tekst lub pobrać rozliczenie jako TXT.

## Pliki do podmiany po v1.7.5.1
- `app.py`
- `database.py`
- `logic.py`

Nie ma migracji schematu bazy. Stawka jest zapisywana w istniejącym `extra_json`, więc stare turnieje pozostają kompatybilne.

# UPGRADE V1.7.4.1

Hotfix połączeń PostgreSQL/Neon.

## Co naprawia

Po uśpieniu Streamlit Cloud lub Neon połączenie trzymane w puli mogło zostać zamknięte po stronie serwera. Przy kolejnym uruchomieniu aplikacja dostawała martwy socket, a ręczny `rollback()` maskował pierwotny błąd jako `psycopg.OperationalError`.

## Zmiany

- `ConnectionPool.check_connection` sprawdza połączenie przy każdym checkout,
- martwe połączenie jest odrzucane i zastępowane nowym,
- `pool.connection()` sam obsługuje commit/rollback i zwrot połączenia,
- brak zmian w logice turniejów i bazie danych.

Z v1.7.4 wystarczy podmienić `database.py` i wykonać Commit + Reboot app.

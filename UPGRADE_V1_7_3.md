# FIFA Night Flex v1.7.3 — Performance

Ta wersja nie zmienia czasu ani wyglądu animacji. Optymalizuje wyłącznie martwy czas pomiędzy kliknięciem a startem animacji.

## Najważniejsze zmiany
- warm connection pool dla Neon (`psycopg[pool,binary]`),
- lżejszy `setup_bundle()` na ekranach losowań, bez pobierania tabeli meczów,
- koło fortuny po zapisie renderuje nowy wynik w tym samym przebiegu fragmentu, zamiast robić kolejny rerun i ponowny odczyt z bazy,
- usunięty drugi `bundle()` z kolejnych spinów koła,
- ujawnienie grup/drabinki wykonuje teraz tylko szybkie oznaczenie `draw_revealed`; zapisy grup/tie-order są odroczone do kliknięcia „Zaczynamy turniej”,
- reroll grup/drabinki renderuje nowy układ bez dodatkowego fragment rerun,
- losowania DE 5/7/8 renderują wynik bez ponownego odczytu z Neon po kliknięciu przycisku.

## Instalacja
Podmień `app.py`, `database.py`, `requirements.txt`, następnie Commit i Reboot app. Zmiana `requirements.txt` doinstaluje obsługę puli połączeń.

Nie ma migracji bazy i nie zmieniono logiki turniejów, harmonogramów ani długości animacji.

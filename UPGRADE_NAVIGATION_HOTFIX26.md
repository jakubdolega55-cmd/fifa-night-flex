# Hotfix 26 — uproszczona nawigacja i testowe FIFA Night bez sterowania

## Start rozgrywki
- Bez sterowania można utworzyć i prowadzić dowolny **testowy** turniej FIFA Night.
- Zasada 1 vs 1 została doprecyzowana w Hotfix 28: każde 1 vs 1 jest oficjalne i nie wymaga sterowania.
- Sterowanie jest wymagane do rozpoczęcia oficjalnego turnieju FIFA Night dla 3–8 graczy.
- Zmiana istniejącej rozgrywki z testowej na oficjalną wymaga `ADMIN_PASSWORD`; po poprawnym haśle urządzenie automatycznie przejmuje sterowanie.

## Nawigacja główna
Pozostają cztery główne panele:
- `🎮 FIFA NIGHT`
- `📊 STATYSTYKI`
- `🏆 AWARDS`
- `⚙️ USTAWIENIA`

1 vs 1 jest teraz trybem w panelu FIFA Night, a nie osobnym kafelkiem.

## Statystyki
Zakładki są uporządkowane jako:
- Ranking
- Rekordy
- Gracze
- Ciekawostki
- Rozliczenia
- Historia

Historia nie jest już osobnym głównym panelem. Drużyny i strzelcy są połączone w `Ciekawostki`.

## Profile graczy
Odznaki gracza zostały przeniesione bezpośrednio do jego profilu. Każda zdobyta odznaka jest domyślnie zwinięta; po rozwinięciu pokazuje opis, datę i miejsce zdobycia. Lista niezdobytych odznak również jest zwinięta.

## AWARDS
W panelu AWARDS jest wewnętrzny przełącznik:
- `🏆 Awards`
- `🏛️ Kamienie milowe`

Globalne jubileusze FIFA Night nie zajmują już osobnej zakładki w Statystykach.

## Baza i logika
Hotfix nie zmienia schematu bazy danych ani algorytmów turniejowych. Nie wymaga migracji Neona.

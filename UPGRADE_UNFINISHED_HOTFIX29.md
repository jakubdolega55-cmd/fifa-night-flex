# Hotfix 29 — niedokończony oficjalny FIFA Night

## Co dodano

- Aktywny **oficjalny turniej 3–8 graczy** można zamknąć przed rozegraniem wszystkich spotkań przez `⏹️ Zakończ FIFA Night jako niedokończony`.
- Zamknięcie jest dostępne tylko po rozegraniu co najmniej jednego meczu. Gdy nie rozegrano nic, właściwą operacją pozostaje reset.
- Zamknięty wcześniej turniej otrzymuje status `abandoned`, znika z aktywnej rozgrywki i **nie jest przeznaczony do późniejszego wznawiania**.
- Rozegrane mecze i zapisani strzelcy zostają w bazie oraz liczą się jako oficjalne do statystyk meczowych, H2H, rekordów, statystyk drużyn/strzelców, Awards, odznak zależnych od rozegranych meczów i globalnych kamieni milowych.
- Niedokończony turniej **nie przyznaje** mistrza, podium, tytułu, finału ani rozliczenia finansowego/jackpotu.
- Historia pokazuje taki wpis jako `NIEDOKOŃCZONY`, zachowuje jego numer FIFA Night, liczbę rozegranych spotkań i pełną listę dotychczasowych wyników. Nierozgrane mecze są opisane jako `NIE ROZEGRANO`.
- Numeracja kolejnych oficjalnych FIFA Night uwzględnia zamknięty niedokończony event, dzięki czemu historyczny numer nie zmienia się po fakcie.

## Oś historii kamieni milowych

Zgodnie z ustalonym kierunkiem usunięto przewijaną tabelę. Kamienie są teraz grupowane po dacie w rozwijanych sekcjach `DD-MM-RRRR`; wewnątrz widoczna jest zwykła lista wszystkich wydarzeń z danego dnia, bez limitu liczby pozycji.

## Baza danych

Nie jest wymagana migracja schematu. Kolumna `tournaments.status` jest tekstowa; Hotfix 29 wykorzystuje dodatkową wartość `abandoned`.

## Ważne rozróżnienie

- `Reset` = usuwa bieżący turniej i jego rozegrane dane.
- `Zakończ jako niedokończony` = zamyka oficjalny turniej i zachowuje rozegrane dane jako część oficjalnej historii.

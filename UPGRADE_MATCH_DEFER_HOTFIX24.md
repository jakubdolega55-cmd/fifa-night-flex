# Hotfix 24 — Przesuń mecz na później

- Dodano przycisk **🕒 PRZESUŃ MECZ NA PÓŹNIEJ** przy aktywnym meczu.
- Przycisk pojawia się wyłącznie wtedy, gdy istnieje co najmniej jeden inny mecz, który jest już gotowy do rozegrania.
- Przesunięcie nie pomija meczu i nie zapisuje żadnego wyniku — zmienia tylko kolejność LIVE/Terminarza.
- Od Hotfix 28 przycisk przesuwa mecz tylko o **jeden grywalny slot**: następny legalny mecz wskakuje teraz, a odroczone spotkanie wraca bezpośrednio po nim. Jeśli zawodnik nadal jest niedostępny, można użyć przycisku ponownie.
- Dotychczasowe **Pomiń mecz** pozostaje bez zmian i nadal pojawia się tylko wtedy, gdy algorytm potwierdzi matematycznie, że wynik nie może zmienić pary finalistów.
- Brak migracji bazy: kolejność jest zapisywana w istniejącym `extra_json`.

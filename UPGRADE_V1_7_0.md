# FIFA Night Flex v1.7.0

## Podsumowanie i PNG
- uproszczona klasyfikacja: mistrz ma bilans i bramki, miejsca 2–4 pokazują tylko nick i drużynę,
- usunięto informacje o losowaniu Winners z podsumowania,
- strzelcy nadal są opcjonalni,
- jeśli w turnieju nie wpisano żadnego strzelca, aplikacja i PNG pokazują „Nie uzupełniono strzelców” i działają normalnie,
- polskie znaki pozostają obsługiwane przez Unicode-capable font fallback.

## Kolejność między turniejami
- dopasowanie tylko po identycznym nicku z bezpośrednio poprzedniego zakończonego turnieju,
- liczba graczy i format mogą się zmieniać,
- pary/grupy są losowane normalnie; poprzedni turniej nie zmienia przeciwników,
- poprzednie oczekiwanie może jedynie zmienić kolejność rozegrania już wylosowanych niezależnych meczów otwierających,
- BYE jest nadal losowy, ale z miękkimi wagami: najdłużej czekający = 25% zwykłej wagi, drugi = 50%, pozostali = 100%; nikt nie jest wykluczony,
- przy remisach w oczekiwaniu maksymalnie dwie osoby są losowo wybierane do obniżonej wagi,
- priorytety nie są pokazywane w interfejsie,
- cofanie wyniku używa faktycznej kolejności rozegrania (`played_at`), a nie numeru meczu.

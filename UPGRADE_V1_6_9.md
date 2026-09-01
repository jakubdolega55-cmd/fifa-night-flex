# FIFA Night Flex v1.6.9

## Priorytet między turniejami
- używany jest wyłącznie bezpośrednio poprzedni zakończony turniej tego samego typu: testowy dla testowego, produkcyjny dla produkcyjnego,
- nick musi być identyczny znak w znak,
- zmiana liczby graczy i formatu jest obsługiwana (np. 7→5, 5→7, 6→8),
- priorytet = liczba meczów rozegranych po ostatnim meczu danego gracza w poprzednim turnieju,
- większy priorytet przyspiesza pierwszy mecz w kolejnym turnieju,
- nowi / niedopasowani gracze są neutralni,
- algorytm ma bezpiecznik: nie może pogorszyć liczby meczów back-to-back ani maksymalnej przerwy w fazie otwierającej względem bazowego terminarza,
- w DE 5/7 gracz z największym oczekiwaniem nie dostaje opóźnionego slotu/BYE, jeśli można go przyznać komuś z niższym priorytetem.

## PNG
- zachowane miejsca 3–4 i pozostałe poprawki z v1.6.8,
- polskie znaki korzystają z darmowego fallbacku DejaVu Sans dostarczanego przez matplotlib na Streamlit Cloud.

# FIFA Night Flex v1.6.5

## Nowość

Dodano eksport podsumowania zakończonego turnieju do obrazka PNG 1080×1080.

## Jak działa

- Na ekranie końcowego podsumowania pojawia się przycisk `Pobierz podsumowanie PNG`.
- Grafika nie używa nazwy `FIFA Night Flex` — pokazuje tylko numer turnieju (albo oznaczenie testowe).
- Obraz zawiera: datę, liczbę graczy, format, mistrza, finalistę, wynik finału, strzelca turnieju, mecz turnieju oraz podstawowe statystyki.

## Technicznie

- Eksport jest generowany bezpośrednio z danych turnieju, więc nie robi screenshota strony.
- Dodano moduł `export_utils.py` oparty o Pillow.

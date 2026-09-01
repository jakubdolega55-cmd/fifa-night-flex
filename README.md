# FIFA Night Flex v1.6.6

Responsywna aplikacja Streamlit do turniejów FIFA dla 4–8 graczy, z trwałym zapisem w Neon/PostgreSQL.

## Formaty

- 4 graczy — liga każdy z każdym + finał (7 meczów)
- 5 graczy — Double Elimination (8–9) albo liga + finał (11)
- 6 graczy — klasyczne 2×3 + SF + finał (9) albo rozszerzone 2×3 + QF + SF + finał (11)
- 7 graczy — Double Elimination (12–13), grupy 4+3 + QF + SF + finał (14) albo grupy 4+3 + SF + finał (12)
- 8 graczy — grupy 4+4 + SF + finał (15), Double Elimination (14–15) albo grupy 4+4 + baraże + SF + finał (17)

## Formaty dla 8 graczy

### Grupy 4+4 + półfinały + finał — 15 meczów

12 meczów grupowych, następnie 1A–2B i 1B–2A, a na końcu finał. Kolejność półfinałów jest dobierana po zakończeniu grup, aby ograniczyć granie bez odpoczynku.

### Double Elimination — 14–15 meczów

Pełna, symetryczna drabinka dla ośmiu osób, bez BYE. Zawodnik odpada dopiero po drugiej porażce. Mecz 15 jest resetem finału i pojawia się tylko wtedy, gdy mistrz Losers Bracket wygra pierwszy finał.

### Grupy 4+4 + baraże + półfinały + finał — 17 meczów

12 meczów grupowych. Zwycięzcy obu grup przechodzą bezpośrednio do półfinałów. Miejsca 2–3 grają dwa baraże, a 4. miejsca odpadają. Każdy zwycięzca barażu dostaje jeden pełny mecz odpoczynku przed swoim półfinałem.

## Drużyny

- 4 i 5 graczy — losowanie kolejności draftu, następnie wybór drużyn z pozostałej puli.
- 6 graczy — koło fortuny: Bayern, Barcelona, PSG, Liverpool, Man City, Wild Card.
- 7 graczy — koło fortuny: 5 klubów + 2 Wild Cards.
- 8 graczy — koło fortuny: 5 klubów + 3 Wild Cards.
- Real Madryt pozostaje zablokowany przy Wild Card.

## Telefon

Losowania i ceremonie używają responsywnego układu. Na małym ekranie karty składają się pionowo, długie nicki są zawijane, a animowane elementy dopasowują wysokość do zawartości.

## Wpisywanie graczy

Pola graczy są wyszukiwalne i podpowiadają nicki z zakończonych turniejów nietestowych zapisanych we wspólnej bazie statystyk. Można też wpisać nowy nick. Pola znajdują się w formularzu, więc wpisywanie i filtrowanie podpowiedzi nie uruchamia pełnego reruna aplikacji; dane trafiają do backendu dopiero po zatwierdzeniu formularza.

## Statystyki i klimat meczu

Przed każdym meczem aplikacja pokazuje kompaktowo H2H, formę z ostatnich 5 oficjalnych spotkań oraz oznaczenia Rivalry/Derby, jeśli para spełnia kryteria historyczne.

Zakładka `Statystyki` zawiera ranking, explorer H2H, aktualną formę, rekordy, Hall of Fame oraz klasyfikację dokładnych strzelców. Po zakończeniu turnieju pojawia się osobny ekran podsumowania z mistrzem, finalistą, najlepszym atakiem/obroną, największym zwycięstwem, najbardziej bramkowym meczem, strzelcem turnieju i wykrytymi nowymi rekordami.

## Wild Card

Jeśli koło wylosuje Wild Card, losowanie zatrzymuje się do czasu wpisania konkretnej drużyny. Pole podpowiada wcześniejsze wybory oraz startową listę: Inter, Atletico, BVB, Man United, Arsenal, Chelsea, Bayer Leverkusen, Tottenham, AC Milan i Napoli. Wpisywanie/wybieranie odbywa się w formularzu, więc nie przeładowuje strony przy każdym znaku.

## Dokładni strzelcy

Pod wynikiem meczu można opcjonalnie rozpisać dokładnych strzelców. Dla każdej drużyny na wierzchu pojawia się 5 najpopularniejszych nazwisk z licznikami +/–. Pozostali są dostępni niżej, a nowego zawodnika można dopisać w polu `Inny zawodnik`. Po zapisaniu trafia do puli danej drużyny.

Liczniki są wewnątrz formularza meczu, więc ich zmiana nie uruchamia rerunu; wynik i strzelcy są zapisywani razem dopiero po `ZATWIERDŹ WYNIK`. Jeśli zaczynasz rozpisywać strzelców, suma ich goli musi zgadzać się z wynikiem. Można też zostawić strzelców całkowicie pustych.

Początkowe listy zawodników uzupełnia się w pliku `scorer_seeds.py`.


## Losowanie Winners Bracket w Double Elimination

W formatach 7- i 8-osobowego Double Elimination po zakończeniu pierwszej rundy aplikacja wykonuje osobne losowanie par kolejnej rundy Winners Bracket. Dla 5 graczy pozostaje istniejące losowanie przeciwnika dla zawodnika z wolnym losem.

## Eksport do obrazka

Po zakończeniu turnieju na ekranie podsumowania pojawia się przycisk `Pobierz podsumowanie PNG`.

Eksport generuje czytelną grafikę **1080×1080** do wrzucenia na grupę. W v1.6.6 powiększono typografię i uproszczono układ. Na obrazku znajdują się m.in.:

- numer turnieju (bez nazwy aplikacji),
- data, liczba graczy i format,
- mistrz i finalista,
- wynik finału,
- strzelec turnieju,
- mecz turnieju,
- ofensywa i defensywa turnieju.

Turnieje testowe też można eksportować, ale na grafice są oznaczone jako testowe i nie dostają numeru oficjalnego.

## Historia i zabezpieczenie bazy

Panel `Historia i baza` obsługuje usunięcie ostatniego zakończonego turnieju nietestowego, wyczyszczenie całej historii oraz blokowanie/odblokowanie historii. Operacje administracyjne wymagają `ADMIN_PASSWORD` ze Streamlit Secrets.

Pełne czyszczenie usuwa turnieje, mecze i statystyki. Tabela graczy i zapamiętane składy pozostają w bazie, ale autocomplete pokazuje wyłącznie nicki występujące w aktualnych oficjalnych statystykach.

## Streamlit Secrets

W Streamlit Community Cloud ustaw:

```toml
DATABASE_URL = "TWÓJ_CONNECTION_STRING_Z_NEON"
ADMIN_PASSWORD = "TWOJE_HASLO"
```

Plik `.streamlit/secrets.toml` nie może trafić do GitHuba.

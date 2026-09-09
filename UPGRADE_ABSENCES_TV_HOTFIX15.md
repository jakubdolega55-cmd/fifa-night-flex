# Hotfix 15 — absencje po czerwonej kartce/kontuzji + TV

## Co dodano

- OpenAI Vision rozpoznaje nowy typ zdarzenia `injury` (kontuzja). Do czasu potwierdzenia dokładnej ikonografii EA FC prompt ma zachować ostrożność i zwracać `unknown`, gdy symbol jest niejednoznaczny.
- `red_card` i `injury` tworzą automatyczną absencję piłkarza na dokładnie **następny faktycznie rozegrany mecz** jego gracza FIFA Night w tym samym turnieju.
- Przesunięcie meczu nie zużywa absencji. Pominięty mecz również jej nie zużywa.
- Cofnięcie ostatniego wyniku cofa także stan absencji: usuwa absencje utworzone przez cofany mecz i reaktywuje absencje, które zostały w nim odbyte.
- Nowa tabela `tournament_absences` przechowuje źródło absencji i mecz, w którym została odbyta.
- Kontuzje są widoczne w podglądzie AI, edytorze wydarzeń i Historii.
- W sterowaniu meczu wyświetla się ostrzeżenie o absencjach na aktualny mecz oraz na następny mecz.
- Panel TV (LIVE/AUTO, slajd TERAZ / NASTĘPNY) pokazuje absencje zarówno dla aktualnego meczu, jak i dla kolejnego oraz — jeśli jest już ustalony — następnego po nim.

## Zasada

- czerwona kartka = 1 następny rozegrany mecz pauzy,
- kontuzja = 1 następny rozegrany mecz pauzy,
- kara przypisana jest do konkretnego piłkarza w drużynie gracza FIFA Night,
- match_no nie decyduje o odbyciu kary — liczy się rzeczywista kolejność rozegrania.

## Pliki

Podmień:
- `app.py`
- `database.py`
- `mobile_api.py`

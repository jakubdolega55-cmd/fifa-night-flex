# FIFA Night Flex

Druga aplikacja do turniejów FIFA dla 4–7 graczy. Może działać pod osobnym linkiem Streamlit, ale używa **tego samego DATABASE_URL / Neon** co klasyczna aplikacja 6-osobowa.

## Formaty

- 4 graczy: liga każdy z każdym + finał (7 meczów)
- 5 graczy: double elimination (8 lub 9 meczów)
- 6 graczy: 2×3 + półfinały + finał (9 meczów)
- 7 graczy: double elimination (12 lub 13 meczów) **albo** grupy 4+3 + playoff (14 meczów)

## Wspólna baza ze starą aplikacją

W Streamlit Cloud w `Secrets` wklej **dokładnie ten sam `DATABASE_URL`**, którego używa stara aplikacja.

Nie trzeba zmieniać starej aplikacji, żeby statystyki działały wspólnie. Flex zapisuje zakończone turnieje do tych samych tabel `players`, `tournaments`, `tournament_players`, `matches`, więc stary ekran statystyk również je zobaczy.

Bieżący turniej Flex jest przechowywany przez osobny klucz `flex_current_tournament` i ma `is_current=0`, więc klasyczna aplikacja nie pomyli go ze swoim aktywnym turniejem.

**Uwaga:** przycisk `Wyczyść całą historię` w starej aplikacji usuwa wszystkie wspólne tabele, więc po podłączeniu obu aplikacji wyczyści historię obu. W Flex przycisk czyszczenia usuwa tylko historię Flex.

## Deployment

1. Utwórz nowe repo GitHub, np. `fifa-night-flex`.
2. Wrzuć zawartość tego folderu do repo (tak, żeby `app.py` był w katalogu głównym).
3. Streamlit Community Cloud → `Create app` → wybierz nowe repo → `app.py`.
4. W `Advanced settings → Secrets` wklej ten sam:

```toml
DATABASE_URL = "TWÓJ_CONNECTION_STRING_Z_NEON"
```

5. Deploy. Dostaniesz drugi niezależny link.


## v1.1 — draft drużyn dla 4 i 5 graczy

Dla turniejów 4- i 5-osobowych drużyny nie są losowane kołem. Aplikacja najpierw losuje kolejność wyboru, a następnie gracze po kolei wybierają z puli: Bayern, Barcelona, PSG, Liverpool, Manchester City i Wild Card. Wybrana pozycja znika z puli. Wild Card pozwala wpisać inną drużynę; Real Madryt pozostaje zablokowany. Dla 6 i 7 graczy pozostaje koło fortuny.

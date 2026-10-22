# FIFA NIGHT FLEX — handoff R33 — 2026-10-22

Baza: R32. Android versionCode pozostaje 15.

R33 dodaje historię ostatnich meczów bezpośrednio do profilu gracza:
1. backend zwraca do 15 ostatnich oficjalnych meczów wraz z kontekstem FIFA Night / 1v1;
2. wynik jest pokazany z perspektywy gracza;
3. mobile/PWA i Streamlit mają wybór 5 / 10 / 15;
4. po rozwinięciu meczu pokazują Summary i Events, jeśli te dane rzeczywiście zostały zapisane;
5. stare mecze bez nowych danych pozostają w historii bez zgadywania brakujących statystyk.

Nie zmieniono Awards, Gali, odznak, klasyfikacji, rekordów, formatów ani finansów.

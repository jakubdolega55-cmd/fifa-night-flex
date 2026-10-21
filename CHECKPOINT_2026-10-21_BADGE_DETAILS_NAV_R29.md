# FIFA NIGHT FLEX — R29 — szczegóły odznak + nawigacja kategorii

## Zakres
Mały checkpoint po R28. Bez zmian zasad zdobywania 53 odznak, Awards, klasyfikacji, rekordów i turniejów.

## Zmiany
- Zdobyte odznaki meczowe pokazują teraz **konkretny mecz z perspektywy gracza**: rywal + wynik, np. `vs Bartek • 7:1` (z wynikiem karnych, jeśli wystąpiły).
- Informacja jest rekonstruowana historycznie z istniejących meczów, więc działa również dla wcześniej zdobytych odznak.
- `Mistrz wielu barw` pokazuje nazwy drużyn, którymi zdobyto mistrzowskie tytuły; także postęp przed zdobyciem odznaki pokazuje już zgromadzone drużyny.
- Poprawiono mylący postęp `One Man Army`: licznik nie pokazuje już rekordu dowolnego pojedynczego strzelca. Liczy wyłącznie wygrane mecze, w których **wszystkie gole zwycięzcy** zdobył jeden piłkarz. Przykład: 6 goli jednego piłkarza + 1 gol kolegi nie daje postępu 6/3.
- Mobile/PWA `ZOBACZ WSZYSTKIE ODZNAKI`: na górze są kafelki kategorii z ikonami. Wyświetlana jest tylko wybrana kategoria, z dużą nazwą kategorii i licznikiem zdobytych odznak. Nie ma już jednej długiej listy wszystkich 53 odznak z nagłówkami pomiędzy.
- Streamlit wykorzystuje również nowy `match_context` w szczegółach zdobytej odznaki.

## Testy
- `achievement_badge_details_r29_smoke.py` — PASS
- `achievement_badges_r27_smoke.py` — PASS
- `records_summary_turnaround_r28_smoke.py` — PASS
- `mobile_api_smoke.py` — 52/52 PASS
- Python compile (`database.py`, `mobile_api.py`, `app.py`) — PASS
- TSX: parser TypeScript nie zgłosił błędów składni; pełny npm check nadal nieoznaczony jako PASS z powodu braku `node_modules` w paczce roboczej.

Android `versionCode` bez zmiany: 15.

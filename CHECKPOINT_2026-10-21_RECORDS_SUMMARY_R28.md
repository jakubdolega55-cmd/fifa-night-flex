# FIFA NIGHT FLEX — R28 — rekordy Summary + zwrot akcji

## Zakres
Mały checkpoint po R27. Bez zmian Awards, klasyfikacji, losowań i zasad odznak.

## Zmiany
- Rekordy: dodano **Najwyższe posiadanie w meczu** z zapisanych, użytecznych Summary.
- Rekordy: dodano **Najwyższe xG w meczu** z zapisanych, użytecznych Summary.
- `Największy comeback` + `Największy wypuszczony wynik` połączono w publicznym UI w jeden rekord: **Największy zwrot akcji**.
- Backend zachowuje legacy `biggest_comeback` i `biggest_blown_lead` dla kompatybilności, a dodatkowo zwraca `biggest_turnaround`.
- Stare mecze bez Summary nie są traktowane jako 0 i nie biorą udziału w rekordach xG/posiadania.
- Stare mecze bez szczegółowej osi Events nie mogą zostać użyte do rekordu zwrotu akcji.

## Wsteczność odznak R27
`achievement_center()` rekonstruuje odznaki z pełnej zapisanej historii przy odczycie i zapisuje jako moment zdobycia pierwszy historyczny moment spełnienia warunku. Dlatego nowe odznaki mogą pojawić się wstecznie, jeśli odpowiednie dane już istnieją.

Ograniczenia:
- Summary-badges wymagają historycznie zapisanego usable Summary.
- Events/scorer badges wymagają historycznie zapisanych Events/scorerów.
- turniejowe, H2H, wyniki, drużyny i finanse działają wstecz tam, gdzie historia tych danych jest zapisana.

## Testy
- `records_summary_turnaround_r28_smoke.py` — PASS
- `achievement_badges_r27_smoke.py` — PASS
- `summary_classifications_r26_smoke.py` — PASS
- Python compile głównych plików — PASS
- `mobile_api_smoke.py` — 52/52 PASS

Android `versionCode` bez zmiany: 15.

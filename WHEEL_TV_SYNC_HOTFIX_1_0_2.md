# FIFA Night 1.0.2 — Wheel / TV Sync hotfix

Zmiany po testach na telefonie i TV:

- koło drużyn na Androidzie: kolorowe segmenty, nazwy przyklejone do segmentów, obrót ok. 10 s;
- TV Sync: nazwy drużyn obracają się razem z kołem;
- podczas etapu `team_draw` TV cały czas pokazuje koło — po losowaniu wraca do statycznego koła dla następnego gracza zamiast kafelków uczestników;
- polling TV podczas losowań co 500 ms, wydarzenia nadal są kolejkowane;
- losowanie kolejności draftu i struktury/par/grup odkrywa kolejne pozycje co ok. **4,5 s**;
- telefon blokuje `ZATWIERDŹ/START/PONÓW` do czasu zakończenia revealu;
- specjalne losowania w trakcie turnieju także mają ok. **4,5 s** między kolejnymi odkryciami;
- Streamlitowe koło używane przy sterowaniu z laptopa też kręci się ok. 10 s;
- TV AUTO zmienia ekran co ok. 30 s zamiast 10 s;
- Mobile/API version: 1.0.2, Android versionCode: 4.

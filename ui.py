from __future__ import annotations

import hashlib
import html
import math
import random

import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

TEAM_SHORT = {
    "Bayern Monachium":"BAYERN", "FC Barcelona":"BARCA", "PSG":"PSG", "Liverpool":"LIVERPOOL", "Manchester City":"MAN CITY",
    "Dowolna drużyna (Real Madryt banned)":"DZIKA KARTA",
    "Dowolna drużyna #1 (Real Madryt banned)":"WILD CARD 1",
    "Dowolna drużyna #2 (Real Madryt banned)":"WILD CARD 2",
}
COLORS=["#2563EB","#DB2777","#0891B2","#EA580C","#16A34A","#7C3AED","#CA8A04"]
JOKES={
    "Bayern Monachium":["Bundesliga tax activated.","Harry Kane pyta, czy za to też jest trofeum."],
    "FC Barcelona":["Dźwignia finansowa odpalona.","Laporta sprzedał przyszły grill, żeby to sfinansować."],
    "PSG":["Projekt Champions League, kolejny sezon.","Budżet bez limitu. Wymówki też."],
    "Liverpool":["You'll Never Walk Alone. Chyba że odpadniesz.","Anfield mode: ON."],
    "Manchester City":["Pep już rysuje 14 nowych pozycji.","Posiadanie piłki: przewidywane 97%."],
}


def inject_css():
    st.markdown("""<style>
    .block-container{max-width:1180px;padding-top:1rem;padding-bottom:4rem}.hero{padding:22px 24px;border-radius:22px;background:linear-gradient(135deg,#121d35,#16344a 56%,#145a4a);border:1px solid rgba(255,255,255,.12);margin-bottom:18px;color:#f8fafc!important;box-shadow:0 14px 34px rgba(2,8,23,.14)}.hero h1{margin:0;font-size:clamp(2rem,6vw,3.4rem);color:white!important}.hero p{margin:4px 0 0;color:#dbeafe!important}.match-card,.mini-card{border:1px solid rgba(148,163,184,.22);border-radius:18px;padding:18px;background:linear-gradient(145deg,#111827,#162338);margin:8px 0 14px;color:#f8fafc!important;box-shadow:0 8px 24px rgba(2,8,23,.12)}.match-no{color:#94a3b8!important;text-transform:uppercase;font-size:.82rem;letter-spacing:.08em}.player-big{color:#fff!important;font-weight:850;font-size:clamp(1.2rem,4vw,1.75rem)}.team-small{color:#cbd5e1!important;font-size:.92rem}.scoreline{color:#fff!important;font-size:1.35rem;font-weight:850}.winner{text-align:center;padding:26px;border-radius:24px;color:#fff!important;background:linear-gradient(145deg,#2b2108,#4b3507);border:1px solid rgba(250,204,21,.45)}div.stButton>button,div[data-testid='stFormSubmitButton']>button{min-height:48px;border-radius:14px;font-weight:800}div[data-testid='stNumberInput'] input{font-size:1.25rem;text-align:center;font-weight:800}.score-separator{text-align:center;font-size:1.9rem;font-weight:900;padding-top:34px}.status-chip{display:inline-block;border:1px solid rgba(128,128,128,.35);border-radius:999px;padding:4px 10px;font-size:.78rem}.format-card{border:1px solid rgba(148,163,184,.22);border-radius:16px;padding:12px 14px;margin:6px 0;background:rgba(15,23,42,.04)}
    @media(max-width:640px){.block-container{padding-left:.75rem;padding-right:.75rem;padding-top:.55rem}.hero{padding:17px 15px;border-radius:18px}.match-card,.mini-card{padding:14px;border-radius:16px}div.stButton>button,div[data-testid='stFormSubmitButton']>button{width:100%;min-height:52px}.score-separator{padding-top:30px}}
    </style>""",unsafe_allow_html=True)


def hero(subtitle="4–7 graczy • jeden link • różne formaty"):
    st.markdown(f'<div class="hero"><h1>⚽ FIFA NIGHT FLEX</h1><p>{html.escape(subtitle)}</p></div>',unsafe_allow_html=True)


def joke_for(player,team,tid):
    if "Dowolna drużyna" in team:
        choices=["Wildcard. Real Madryt nadal banned 🚫","Florentino złożył protest. Odrzucony."]
    else: choices=JOKES.get(team,["Los zdecydował. Pretensje do komisji."])
    d=hashlib.sha256(f"{player}|{team}|{tid}".encode()).digest(); return choices[int.from_bytes(d[:2],"big")%len(choices)]


def _sector_path(i,n,r=182,c=210):
    span=360/n; start=i*span-span/2; end=i*span+span/2
    def pt(deg):
        rad=math.radians(deg); return c+r*math.sin(rad),c-r*math.cos(rad)
    x1,y1=pt(start);x2,y2=pt(end);large=1 if span>180 else 0
    return f"M {c} {c} L {x1:.2f} {y1:.2f} A {r} {r} 0 {large} 1 {x2:.2f} {y2:.2f} Z"


def render_wheel(result,player,tid,pool):
    n=len(pool); idx=pool.index(result); seed=int.from_bytes(hashlib.sha256(f"{tid}-{player}-{result}".encode()).digest()[:4],"big"); rng=random.Random(seed)
    span=360/n; offset=rng.uniform(-span*.24,span*.24); rotation=5*360+(360-(idx*span+offset))%360
    sectors=[];labels=[]
    for i,team in enumerate(pool):
        sectors.append(f'<path d="{_sector_path(i,n)}" fill="{COLORS[i%len(COLORS)]}" stroke="rgba(255,255,255,.18)" stroke-width="2"/>')
        deg=i*span;rad=math.radians(deg);x=210+119*math.sin(rad);y=210-119*math.cos(rad);label=html.escape(TEAM_SHORT.get(team,team[:12].upper()))
        labels.append(f'<text x="{x:.1f}" y="{y:.1f}" class="wl" text-anchor="middle" dominant-baseline="middle">{label}</text>')
    components.html(f"""<div class='card'><div class='eye'>LOSOWANIE DRUŻYNY</div><div class='who'>Teraz losujemy dla <b>{html.escape(player)}</b></div><div class='shell'><div class='pointer'><span></span></div><svg viewBox='0 0 420 420'><g class='spin'>{''.join(sectors)}{''.join(labels)}<circle cx='210' cy='210' r='45' fill='#0b1220' stroke='#f8fafc' stroke-width='7'/><text x='210' y='210' text-anchor='middle' dominant-baseline='middle' class='hub'>FC</text></g></svg></div><div class='land'><div class='small'>{html.escape(player)} dostaje</div><div class='team'>{html.escape(result)}</div><div class='joke'>{html.escape(joke_for(player,result,tid))}</div></div></div>
    <style>html,body{{margin:0;background:transparent;font-family:Inter,system-ui}}*{{box-sizing:border-box}}.card{{max-width:680px;margin:2px auto;padding:18px 14px 16px;border-radius:24px;background:radial-gradient(circle at 50% 28%,#1e3a5f,#111c30 46%,#0b1220);border:1px solid rgba(148,163,184,.22);color:#f8fafc;text-align:center;overflow:hidden}}.eye{{font-size:11px;font-weight:900;letter-spacing:.18em;color:#7dd3fc}}.who{{font-size:18px;color:#dbeafe;margin:5px 0}}.shell{{position:relative;width:min(88vw,420px);margin:auto}}svg{{display:block;width:100%;filter:drop-shadow(0 18px 20px rgba(0,0,0,.33))}}.spin{{transform-box:view-box;transform-origin:210px 210px;animation:spin 2.85s cubic-bezier(.10,.72,.12,1) forwards}}@keyframes spin{{to{{transform:rotate({rotation:.2f}deg)}}}}.wl{{fill:white;font-size:{'13' if n>=7 else '15'}px;font-weight:900;paint-order:stroke;stroke:rgba(0,0,0,.44);stroke-width:3px}}.hub{{fill:#fff;font-size:20px;font-weight:1000}}.pointer{{position:absolute;z-index:5;top:2px;left:50%;transform:translateX(-50%);width:44px;height:52px}}.pointer:before{{content:'';position:absolute;left:7px;top:0;width:30px;height:30px;border-radius:50%;background:#f8fafc;border:5px solid #0b1220}}.pointer span{{position:absolute;left:10px;top:25px;border-left:12px solid transparent;border-right:12px solid transparent;border-top:22px solid #f8fafc}}.land{{opacity:0;transform:translateY(8px);animation:land .32s ease 2.72s forwards;min-height:74px}}@keyframes land{{to{{opacity:1;transform:none}}}}.small{{font-size:12px;color:#94a3b8;text-transform:uppercase;font-weight:850}}.team{{font-size:clamp(22px,5vw,31px);font-weight:1000;color:#fff;margin:4px 0}}.joke{{font-size:14px;color:#cbd5e1}}@media(max-width:480px){{.card{{padding:14px 8px 13px}}.wl{{font-size:{'11' if n>=7 else '13'}px}}}}</style>""",height=585,scrolling=False)


def render_draft_order(players,redraws=0):
    ordered=sorted(players,key=lambda p:int(p.get("team_reveal_order") or 999))
    rows=[]
    for i,p in enumerate(ordered,1):
        delay=1.0+(i-1)*1.35
        rows.append(f"<li style='--d:{delay:.2f}s'><span class='num'>{i}</span><span class='wait'>losujemy...</span><b>{html.escape(str(p.get('name') or ''))}</b></li>")
    duration=1.0+(len(ordered)-1)*1.35+.7
    paid=f"<div class='paid'>💸 Podgrzane kulki: <b>{redraws}</b></div>" if redraws else ""
    components.html(f"""<div class='draw'><div class='eye'>KOLEJNOŚĆ DRAFTU</div><div class='title'>Kto wybiera pierwszy?</div>{paid}<div class='box order'><ul>{''.join(rows)}</ul></div><div class='foot'>✅ Kolejność ustalona.</div></div><style>html,body{{margin:0;background:transparent;font-family:Inter,system-ui}}*{{box-sizing:border-box}}.draw{{max-width:680px;margin:4px auto;padding:22px;border-radius:24px;background:radial-gradient(circle at 50% 0,#19395a,#101d32 38%,#0b1220);border:1px solid rgba(148,163,184,.24);color:#f8fafc;text-align:center}}.eye{{font-size:11px;font-weight:900;letter-spacing:.18em;color:#7dd3fc}}.title{{font-size:21px;font-weight:950;margin:5px 0 14px}}.paid{{display:inline-block;margin-bottom:8px;padding:5px 10px;border-radius:999px;background:#422006;color:#fde68a;font-size:12px}}.box{{max-width:520px;margin:auto;border-radius:18px;padding:8px 16px;text-align:left;background:#101c31;border:1px solid rgba(148,163,184,.22)}}ul{{list-style:none;padding:0;margin:0}}li{{position:relative;display:flex;align-items:center;gap:12px;min-height:54px;border-top:1px solid rgba(148,163,184,.14)}}li:first-child{{border-top:0}}.num{{width:34px;height:30px;border-radius:999px;display:grid;place-items:center;background:#1e293b;color:#7dd3fc;font-size:13px;font-weight:950}}li .wait{{position:absolute;left:46px;color:#64748b;font-size:13px;animation:hide .2s ease var(--d) forwards}}li b{{opacity:0;transform:translateX(-10px);font-size:18px;color:white;animation:show .42s ease var(--d) forwards}}@keyframes hide{{to{{opacity:0}}}}@keyframes show{{to{{opacity:1;transform:none}}}}.foot{{margin-top:14px;color:#86efac;font-size:13px;font-weight:800;opacity:0;animation:show .35s ease {duration:.2f}s forwards}}@media(max-width:620px){{.draw{{padding:16px 10px}}.title{{font-size:18px}}}}</style>""",height=max(350,170+len(ordered)*55),scrolling=False)


def _draw_layout(format_key,draw):
    s=draw["slots"]
    if format_key=="groups6": return [("GRUPA A",[("A1",s["A1"]),("A2",s["A2"]),("A3",s["A3"])]),("GRUPA B",[("B1",s["B1"]),("B2",s["B2"]),("B3",s["B3"])])], ["A1","B1","A2","B2","A3","B3"]
    if format_key=="groups7": return [("GRUPA A",[(f"A{i}",s[f"A{i}"]) for i in range(1,5)]),("GRUPA B",[(f"B{i}",s[f"B{i}"]) for i in range(1,4)])], ["A1","B1","A2","B2","A3","B3","A4"]
    if format_key=="league4_final": return [("MECZ OTWARCIA 1",[("1",s["A"]),("2",s["B"])]),("MECZ OTWARCIA 2",[("3",s["C"]),("4",s["D"])])], ["A","B","C","D"]
    if format_key=="double5": return [("MECZ 1",[("A",s["A"]),("B",s["B"])]),("MECZ 2",[("C",s["C"]),("D",s["D"])]),("WOLNY LOS",[("E",s["E"])])], ["A","B","C","D","E"]
    if format_key=="double7": return [("MECZ 1",[("A",s["A"]),("B",s["B"])]),("MECZ 2",[("C",s["C"]),("D",s["D"])]),("MECZ 3",[("E",s["E"]),("F",s["F"])]),("WOLNY LOS",[("G",s["G"])])], ["A","B","C","D","E","F","G"]
    return [],[]


def render_structure_draw(format_key,draw,redraws=0,name_map=None):
    groups,seq=_draw_layout(format_key,draw); pos={slot:i for i,slot in enumerate(seq)}; delay=lambda slot:1.25+pos[slot]*1.4
    cards=[]
    for title,rows in groups:
        rr=[]
        for slot,name in rows:
            if name_map: name=name_map.get(name,name)
            # slot keys A/B etc must map to actual draw keys for delay.
            dkey=slot
            if format_key=="league4_final": dkey={"1":"A","2":"B","3":"C","4":"D"}[slot]
            rr.append(f"<li style='--d:{delay(dkey):.2f}s'><span class='num'>{html.escape(slot)}</span><span class='wait'>oczekuje...</span><b>{html.escape(name)}</b></li>")
        cards.append(f"<div class='box'><div class='bt'>{html.escape(title)}</div><ul>{''.join(rr)}</ul></div>")
    duration=1.25+(len(seq)-1)*1.4+.7
    paid=f"<div class='paid'>💸 Podgrzane kulki: <b>{redraws}</b></div>" if redraws else ""
    components.html(f"""<div class='draw'><div class='eye'>OFICJALNE LOSOWANIE FIFA NIGHT</div><div class='title'>Losujemy po kolei. Komisja prosi o ciszę.</div>{paid}<div class='grid'>{''.join(cards)}</div><div class='foot'>✅ Losowanie zakończone. Reklamacji brak.</div></div><style>html,body{{margin:0;background:transparent;font-family:Inter,system-ui}}*{{box-sizing:border-box}}.draw{{max-width:900px;margin:4px auto;padding:22px;border-radius:24px;background:radial-gradient(circle at 50% 0,#19395a,#101d32 38%,#0b1220);border:1px solid rgba(148,163,184,.24);color:#f8fafc;text-align:center}}.eye{{font-size:11px;font-weight:900;letter-spacing:.18em;color:#7dd3fc}}.title{{font-size:19px;font-weight:950;margin:4px 0 12px}}.paid{{display:inline-block;margin-bottom:8px;padding:5px 10px;border-radius:999px;background:#422006;color:#fde68a;font-size:12px}}.grid{{display:grid;grid-template-columns:repeat({min(len(groups),3)},1fr);gap:12px;align-items:start}}.box{{border-radius:18px;padding:14px;text-align:left;background:#101c31;border:1px solid rgba(148,163,184,.22)}}.bt{{font-size:16px;font-weight:1000;margin-bottom:5px;color:#fff}}ul{{list-style:none;padding:0;margin:0}}li{{position:relative;display:flex;align-items:center;gap:10px;min-height:52px;border-top:1px solid rgba(148,163,184,.14)}}li:first-child{{border-top:0}}.num{{width:34px;height:28px;border-radius:999px;display:grid;place-items:center;background:#1e293b;color:#94a3b8;font-size:11px;font-weight:950}}li .wait{{position:absolute;left:44px;color:#64748b;font-size:13px;animation:hide .2s ease var(--d) forwards}}li b{{opacity:0;transform:translateX(-10px);font-size:16px;color:white;animation:show .42s ease var(--d) forwards}}@keyframes hide{{to{{opacity:0}}}}@keyframes show{{to{{opacity:1;transform:none}}}}.foot{{margin-top:14px;color:#86efac;font-size:13px;font-weight:800;opacity:0;animation:show .35s ease {duration:.2f}s forwards}}@media(max-width:620px){{.draw{{padding:16px 10px}}.grid{{grid-template-columns:1fr}}.title{{font-size:16px}}}}</style>""",height=max(420,180+max(len(rows) for _,rows in groups)*55+(len(groups)-1)*20),scrolling=False)


def standings_df(rows):
    return pd.DataFrame([{"#":r["position"],"Gracz":r["name"],"Drużyna":r["team"],"M":r["m"],"W":r["w"],"R":r["d"],"P":r["l"],"Bramki":f'{r["gf"]}:{r["ga"]}',"+/-":r["gd"],"Pkt":r["pts"]} for r in rows])


def result_text(m):
    if m.get("home_score") is None:return "—"
    s=f'{m["home_score"]}:{m["away_score"]}'
    if m.get("home_penalties") is not None:s+=f' (k. {m["home_penalties"]}:{m["away_penalties"]})'
    return s

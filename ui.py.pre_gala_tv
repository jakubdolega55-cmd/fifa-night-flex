from __future__ import annotations

import hashlib
import html
import math
import random

import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

from logic import structure_match_preview

TEAM_SHORT = {
    "Bayern Monachium":"BAYERN", "FC Barcelona":"BARCA", "PSG":"PSG", "Liverpool":"LIVERPOOL", "Manchester City":"MAN CITY",
    "Dowolna drużyna (Real Madryt banned)":"DZIKA KARTA",
    "Dowolna drużyna #1 (Real Madryt banned)":"WC 1",
    "Dowolna drużyna #2 (Real Madryt banned)":"WC 2",
    "Dowolna drużyna #3 (Real Madryt banned)":"WC 3",
    "Dowolna drużyna #4 (Real Madryt banned)":"WC 4",
    "Dowolna drużyna #5 (Real Madryt banned)":"WC 5",
}
COLORS=["#2563EB","#DB2777","#0891B2","#EA580C","#16A34A","#7C3AED","#CA8A04"]
FIT_SCRIPT = """
<script>
(function(){
  function fit(){
    const body=document.body, doc=document.documentElement;
    const h=Math.max(body?body.scrollHeight:0, doc?doc.scrollHeight:0)+8;
    window.parent.postMessage({isStreamlitMessage:true,type:"streamlit:setFrameHeight",height:h},"*");
  }
  window.addEventListener("load",fit);
  window.addEventListener("resize",fit);
  if(window.ResizeObserver) new ResizeObserver(fit).observe(document.body);
  [50,250,800,1800,3500,7000,11000].forEach(ms=>setTimeout(fit,ms));
})();
</script>
"""

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


def hero(subtitle="4–8 graczy • jeden link • różne formaty"):
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


def render_wheel(result,player,tid,pool,display_result=None):
    display_result = display_result or result
    wheel_result = result
    if wheel_result not in pool:
        # Po zatwierdzeniu WC `result` może być już konkretnym klubem,
        # podczas gdy koło nadal zawiera techniczny slot Wild Card.
        wildcards=[x for x in pool if "Dowolna drużyna" in str(x)]
        if wildcards:
            wheel_result=wildcards[0]
        elif pool:
            wheel_result=pool[0]
        else:
            st.error("Brak drużyn w puli losowania.")
            return
    n=len(pool); idx=pool.index(wheel_result); seed=int.from_bytes(hashlib.sha256(f"{tid}-{player}-{display_result}".encode()).digest()[:4],"big"); rng=random.Random(seed)
    span=360/n; offset=rng.uniform(-span*.24,span*.24); rotation=8*360+(360-(idx*span+offset))%360

    # TV wheel: larger canvas + deliberately short labels. 8–10 player wheels
    # otherwise become unreadable, especially with five Wild Card slots in FC27.
    c=280; r=238; label_r=170
    def sector_path_tv(i:int)->str:
        start_deg=i*span-span/2; end_deg=i*span+span/2
        def pt(deg):
            rad=math.radians(deg); return c+r*math.sin(rad),c-r*math.cos(rad)
        x1,y1=pt(start_deg); x2,y2=pt(end_deg); large=1 if span>180 else 0
        return f"M {c} {c} L {x1:.2f} {y1:.2f} A {r} {r} 0 {large} 1 {x2:.2f} {y2:.2f} Z"

    sectors=[];labels=[]
    for i,team in enumerate(pool):
        sectors.append(f'<path d="{sector_path_tv(i)}" fill="{COLORS[i%len(COLORS)]}" stroke="rgba(255,255,255,.25)" stroke-width="2"/>')
        deg=i*span;rad=math.radians(deg);x=c+label_r*math.sin(rad);y=c-label_r*math.cos(rad)
        if "Dowolna drużyna" in str(team):
            # Supports WC1–WC5 even if a future pool name is not explicitly in TEAM_SHORT.
            import re
            m=re.search(r"#(\d+)",str(team)); label=f"WC {m.group(1)}" if m else "WILD CARD"
        else:
            label=TEAM_SHORT.get(team,team[:12].upper())
        labels.append(f'<text x="{x:.1f}" y="{y:.1f}" class="wl" text-anchor="middle" dominant-baseline="middle">{html.escape(label)}</text>')
    wc_note = "<div class='legend'><b>WC</b> = Wild Card &nbsp;•&nbsp; Real Madryt jest poza kołem</div>" if any("Dowolna drużyna" in str(x) for x in pool) else ""
    components.html(f"""<div class='card'><div class='eye'>LOSOWANIE DRUŻYNY</div><div class='who'>Teraz losujemy dla <b>{html.escape(player)}</b></div><div class='shell'><div class='pointer'><span></span></div><svg viewBox='0 0 560 560'><g class='spin'>{''.join(sectors)}{''.join(labels)}<circle cx='280' cy='280' r='56' fill='#07111f' stroke='#f8fafc' stroke-width='8'/><text x='280' y='280' text-anchor='middle' dominant-baseline='middle' class='hub'>FC</text></g></svg></div>{wc_note}<div class='land'><div class='small'>{html.escape(player)} dostaje</div><div class='team'>{html.escape(display_result)}</div><div class='joke'>{html.escape(joke_for(player,display_result,tid))}</div></div></div>
    <style>html,body{{margin:0;background:transparent;font-family:Inter,system-ui}}*{{box-sizing:border-box}}.card{{max-width:900px;margin:2px auto;padding:18px 18px 16px;border-radius:26px;background:radial-gradient(circle at 50% 28%,#1e3a5f,#111c30 48%,#0b1220);border:1px solid rgba(148,163,184,.22);color:#f8fafc;text-align:center;overflow:hidden}}.eye{{font-size:12px;font-weight:950;letter-spacing:.19em;color:#7dd3fc}}.who{{font-size:20px;color:#dbeafe;margin:5px 0 2px}}.shell{{position:relative;width:min(74vw,560px);margin:0 auto}}svg{{display:block;width:100%;filter:drop-shadow(0 18px 22px rgba(0,0,0,.38))}}.spin{{transform-box:view-box;transform-origin:280px 280px;animation:spin 10s cubic-bezier(.08,.72,.10,1) forwards}}@keyframes spin{{to{{transform:rotate({rotation:.2f}deg)}}}}.wl{{fill:white;font-size:{'17' if n>=9 else '18'}px;font-weight:1000;letter-spacing:.02em;paint-order:stroke;stroke:rgba(0,0,0,.58);stroke-width:4px;stroke-linejoin:round}}.hub{{fill:#fff;font-size:27px;font-weight:1000}}.pointer{{position:absolute;z-index:5;top:3px;left:50%;transform:translateX(-50%);width:52px;height:62px}}.pointer:before{{content:'';position:absolute;left:8px;top:0;width:36px;height:36px;border-radius:50%;background:#f8fafc;border:6px solid #0b1220;box-shadow:0 5px 12px rgba(0,0,0,.3)}}.pointer span{{position:absolute;left:12px;top:30px;border-left:14px solid transparent;border-right:14px solid transparent;border-top:27px solid #f8fafc}}.legend{{display:inline-block;margin:-1px auto 7px;padding:5px 11px;border-radius:999px;background:rgba(15,23,42,.75);border:1px solid rgba(148,163,184,.2);font-size:12px;color:#94a3b8}}.legend b{{color:#f8fafc}}.land{{opacity:0;transform:translateY(8px);animation:land .38s ease 9.72s forwards;min-height:78px}}@keyframes land{{to{{opacity:1;transform:none}}}}.small{{font-size:12px;color:#94a3b8;text-transform:uppercase;font-weight:850}}.team{{font-size:clamp(24px,4vw,34px);font-weight:1000;color:#fff;margin:4px 0}}.joke{{font-size:14px;color:#cbd5e1}}@media(max-width:720px){{.card{{padding:14px 8px 13px}}.shell{{width:min(92vw,500px)}}.wl{{font-size:{'15' if n>=9 else '16'}px}}.who{{font-size:17px}}}}</style>{FIT_SCRIPT}""",height=760,scrolling=False)

def render_draft_order(players,redraws=0):
    ordered=sorted(players,key=lambda p:int(p.get("team_reveal_order") or 999))
    rows=[]
    for i,p in enumerate(ordered,1):
        delay=1.2+(i-1)*4.5
        rows.append(f"<li style='--d:{delay:.2f}s'><span class='num'>{i}</span><span class='wait'>losujemy...</span><b>{html.escape(str(p.get('name') or ''))}</b></li>")
    duration=1.2+(len(ordered)-1)*4.5+1.0
    paid=f"<div class='paid'>💸 Podgrzane kulki: <b>{redraws}</b></div>" if redraws else ""
    components.html(f"""<div class='draw'><div class='eye'>KOLEJNOŚĆ DRAFTU</div><div class='title'>Kto wybiera pierwszy?</div>{paid}<div class='box order'><ul>{''.join(rows)}</ul></div><div class='foot'>✅ Kolejność ustalona.</div></div><style>html,body{{margin:0;background:transparent;font-family:Inter,system-ui}}*{{box-sizing:border-box}}.draw{{max-width:680px;margin:4px auto;padding:22px;border-radius:24px;background:radial-gradient(circle at 50% 0,#19395a,#101d32 38%,#0b1220);border:1px solid rgba(148,163,184,.24);color:#f8fafc;text-align:center}}.eye{{font-size:11px;font-weight:900;letter-spacing:.18em;color:#7dd3fc}}.title{{font-size:21px;font-weight:950;margin:5px 0 14px}}.paid{{display:inline-block;margin-bottom:8px;padding:5px 10px;border-radius:999px;background:#422006;color:#fde68a;font-size:12px}}.box{{max-width:520px;margin:auto;border-radius:18px;padding:8px 16px;text-align:left;background:#101c31;border:1px solid rgba(148,163,184,.22)}}ul{{list-style:none;padding:0;margin:0}}li{{position:relative;display:flex;align-items:center;gap:12px;min-height:54px;border-top:1px solid rgba(148,163,184,.14)}}li:first-child{{border-top:0}}.num{{width:34px;height:30px;border-radius:999px;display:grid;place-items:center;background:#1e293b;color:#7dd3fc;font-size:13px;font-weight:950}}li .wait{{position:absolute;left:46px;color:#64748b;font-size:13px;animation:hide .2s ease var(--d) forwards}}li b{{opacity:0;transform:translateX(-10px);font-size:18px;color:white;animation:show .42s ease var(--d) forwards}}@keyframes hide{{to{{opacity:0}}}}@keyframes show{{to{{opacity:1;transform:none}}}}.foot{{margin-top:14px;color:#86efac;font-size:13px;font-weight:800;opacity:0;animation:show .35s ease {duration:.2f}s forwards}}@media(max-width:620px){{.draw{{padding:16px 10px}}.title{{font-size:18px}}}}</style>{FIT_SCRIPT}""",height=max(350,170+len(ordered)*55),scrolling=False)


def _draw_layout(format_key,draw):
    s=draw["slots"]
    if format_key in ("groups6", "groups6_full"): return [("GRUPA A",[("A1",s["A1"]),("A2",s["A2"]),("A3",s["A3"])]),("GRUPA B",[("B1",s["B1"]),("B2",s["B2"]),("B3",s["B3"])])], ["A1","B1","A2","B2","A3","B3"]
    if format_key in ("groups7","groups7_sf"): return [("GRUPA A",[(f"A{i}",s[f"A{i}"]) for i in range(1,5)]),("GRUPA B",[(f"B{i}",s[f"B{i}"]) for i in range(1,4)])], ["A1","B1","A2","B2","A3","B3","A4"]
    if format_key=="league3_final": return [("KOLEJNOŚĆ LIGI",[("A",s["A"]),("B",s["B"]),("C",s["C"])])], ["A","B","C"]
    if format_key=="league4_final": return [("MECZ OTWARCIA 1",[("1",s["A"]),("2",s["B"])]),("MECZ OTWARCIA 2",[("3",s["C"]),("4",s["D"])])], ["A","B","C","D"]
    if format_key=="double5": return [("MECZ 1",[("A",s["A"]),("B",s["B"])]),("MECZ 2",[("C",s["C"]),("D",s["D"])]),("WOLNY LOS",[("E",s["E"])])], ["A","B","C","D","E"]
    if format_key=="league5_final": return [("KOLEJNOŚĆ LIGI",[("A",s["A"]),("B",s["B"]),("C",s["C"]),("D",s["D"]),("E",s["E"])])], ["A","B","C","D","E"]
    if format_key=="double7": return [("MECZ 1",[("A",s["A"]),("B",s["B"])]),("MECZ 2",[("C",s["C"]),("D",s["D"])]),("MECZ 3",[("E",s["E"]),("F",s["F"])]),("WOLNY LOS",[("G",s["G"])])], ["A","B","C","D","E","F","G"]
    if format_key in ("groups8_sf","groups8_barrage"): return [("GRUPA A",[(f"A{i}",s[f"A{i}"]) for i in range(1,5)]),("GRUPA B",[(f"B{i}",s[f"B{i}"]) for i in range(1,5)])], ["A1","B1","A2","B2","A3","B3","A4","B4"]
    if format_key=="double8": return [("MECZ 1",[("A",s["A"]),("B",s["B"])]),("MECZ 2",[("C",s["C"]),("D",s["D"])]),("MECZ 3",[("E",s["E"]),("F",s["F"])]),("MECZ 4",[("G",s["G"]),("H",s["H"])])], ["A","B","C","D","E","F","G","H"]
    return [],[]


def _render_match_structure_draw(format_key, draw, redraws=0, name_map=None):
    preview=structure_match_preview(format_key,draw)
    if not preview:
        return False
    names=name_map or {}
    cards=[]; max_order=-1
    def side_html(src,side):
        nonlocal max_order
        if not src:
            return ""
        if src.get("kind")=="player":
            order=int(src.get("reveal_order") if src.get("reveal_order") is not None else 99)
            max_order=max(max_order,order); delay=1.0+order*4.5
            nm=names.get(str(src.get("player_id") or ""),"?")
            return f"<div class='side player {side}' style='--d:{delay:.2f}s'><span>{'1. LOS' if side=='home' else '2. LOS'}</span><b>{html.escape(str(nm))}</b></div>"
        nm=str(src.get("label") or src.get("name") or "?")
        return f"<div class='side ref {side}'><span>ZALEŻNOŚĆ</span><b>{html.escape(nm)}</b></div>"
    for row in preview:
        no=row.get("match_no"); label=str(row.get("stage_label") or row.get("stage") or "MECZ")
        badge=f"M{int(no)} • {html.escape(label)}" if no else html.escape(label)
        playin=' playin' if str(row.get('stage'))=='PLAY_IN' else ''
        if row.get('away'):
            body=f"<div class='duel'>{side_html(row.get('home'),'home')}<div class='vs'>VS</div>{side_html(row.get('away'),'away')}</div>"
        else:
            body=f"<div class='duel bye'>{side_html(row.get('home'),'home')}<div class='byeMark'>🍀 WOLNY LOS</div></div>"
        cards.append(f"<div class='match{playin}'><div class='badge'>{badge}</div>{body}</div>")
    finish_delay=1.0+max(max_order,0)*4.5+1.0
    paid=f"<div class='paid'>💸 Podgrzane kulki: <b>{redraws}</b></div>" if redraws else ""
    title='Losujemy pary pierwszej fazy' if format_key.startswith('double') else 'Losujemy pary 1. rundy Swiss'
    sub='Najpierw pierwszy zawodnik pary, potem jego rywal. PLAY-IN jest oznaczony osobno.' if format_key.startswith('double') else 'Każda pokazana para jest dokładnie parą 1. rundy — po starcie nie ma ukrytego przetasowania.'
    components.html(f"""<div class='drawPairs'><div class='eye'>OFICJALNE LOSOWANIE FIFA NIGHT</div><div class='title'>{title}</div><div class='sub'>{sub}</div>{paid}<div class='matches'>{''.join(cards)}</div><div class='foot'>✅ Układ gotowy. To są pary, które trafią do terminarza.</div></div>
    <style>html,body{{margin:0;background:transparent;font-family:Inter,system-ui}}*{{box-sizing:border-box}}.drawPairs{{max-width:1040px;margin:4px auto;padding:24px;border-radius:26px;background:radial-gradient(circle at 50% 0,#183b58,#101d32 42%,#0b1220);border:1px solid rgba(148,163,184,.24);color:#f8fafc;text-align:center}}.eye{{font-size:11px;font-weight:950;letter-spacing:.19em;color:#7dd3fc}}.title{{font-size:27px;font-weight:1000;margin:5px 0 2px}}.sub{{font-size:13px;color:#94a3b8;margin-bottom:15px}}.paid{{display:inline-block;margin:0 0 10px;padding:5px 10px;border-radius:999px;background:#422006;color:#fde68a;font-size:12px}}.matches{{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:13px}}.match{{padding:15px;border-radius:19px;background:#101c31;border:1px solid #334155;text-align:left;box-shadow:0 9px 22px rgba(0,0,0,.14)}}.match.playin{{border-color:#b7791f;background:linear-gradient(145deg,#31230d,#151b29)}}.badge{{display:inline-block;margin-bottom:10px;padding:5px 9px;border-radius:999px;background:#17283c;color:#9fdcf6;font-size:11px;font-weight:1000;letter-spacing:.08em}}.playin .badge{{background:#4a3008;color:#fde68a}}.duel{{display:grid;grid-template-columns:minmax(0,1fr) 42px minmax(0,1fr);align-items:stretch;gap:8px}}.side{{min-height:76px;border-radius:15px;padding:12px 10px;display:flex;flex-direction:column;justify-content:center;text-align:center;background:#14243a;border:1px solid rgba(148,163,184,.2)}}.side span{{font-size:9px;font-weight:950;letter-spacing:.12em;color:#64748b}}.side b{{font-size:20px;line-height:1.13;overflow-wrap:anywhere}}.player{{opacity:0;transform:translateY(9px) scale(.98);animation:reveal .42s ease var(--d) forwards}}.ref{{background:#0d1726;border-style:dashed}}.ref b{{font-size:16px;color:#cbd5e1}}.vs{{display:grid;place-items:center;color:#64748b;font-size:12px;font-weight:1000}}.bye{{grid-template-columns:minmax(0,1fr) 1fr}}.byeMark{{display:grid;place-items:center;border-radius:15px;background:#26330f;border:1px solid #64791d;color:#d9f99d;font-weight:1000;font-size:16px}}.foot{{margin-top:15px;color:#86efac;font-size:13px;font-weight:850;opacity:0;animation:reveal .35s ease {finish_delay:.2f}s forwards}}@keyframes reveal{{to{{opacity:1;transform:none}}}}@media(max-width:760px){{.drawPairs{{padding:16px 9px;border-radius:18px}}.matches{{grid-template-columns:1fr;gap:9px}}.title{{font-size:22px}}.side b{{font-size:18px}}}}</style>{FIT_SCRIPT}""",height=max(470,250+((len(cards)+1)//2)*120),scrolling=True)
    return True


def render_structure_draw(format_key,draw,redraws=0,name_map=None):
    if _render_match_structure_draw(format_key,draw,redraws,name_map):
        return
    groups,seq=_draw_layout(format_key,draw)
    if not groups or not seq:
        st.error(f"Nie udało się przygotować wizualizacji losowania dla formatu: {format_key}")
        return
    pos={slot:i for i,slot in enumerate(seq)}; delay=lambda slot:1.4+pos[slot]*4.5
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
    duration=1.4+(len(seq)-1)*4.5+1.0
    paid=f"<div class='paid'>💸 Podgrzane kulki: <b>{redraws}</b></div>" if redraws else ""
    grid_cols=2 if len(groups)==4 else min(len(groups),3)
    components.html(f"""<div class='draw'><div class='eye'>OFICJALNE LOSOWANIE FIFA NIGHT</div><div class='title'>Losujemy po kolei. Komisja prosi o ciszę.</div>{paid}<div class='grid'>{''.join(cards)}</div><div class='foot'>✅ Losowanie zakończone. Reklamacji brak.</div></div><style>html,body{{margin:0;background:transparent;font-family:Inter,system-ui}}*{{box-sizing:border-box}}.draw{{max-width:900px;margin:4px auto;padding:22px;border-radius:24px;background:radial-gradient(circle at 50% 0,#19395a,#101d32 38%,#0b1220);border:1px solid rgba(148,163,184,.24);color:#f8fafc;text-align:center}}.eye{{font-size:11px;font-weight:900;letter-spacing:.18em;color:#7dd3fc}}.title{{font-size:19px;font-weight:950;margin:4px 0 12px}}.paid{{display:inline-block;margin-bottom:8px;padding:5px 10px;border-radius:999px;background:#422006;color:#fde68a;font-size:12px}}.grid{{display:grid;grid-template-columns:repeat({grid_cols},1fr);gap:12px;align-items:start}}.box{{border-radius:18px;padding:14px;text-align:left;background:#101c31;border:1px solid rgba(148,163,184,.22)}}.bt{{font-size:16px;font-weight:1000;margin-bottom:5px;color:#fff}}ul{{list-style:none;padding:0;margin:0}}li{{position:relative;display:flex;align-items:center;gap:10px;min-height:52px;border-top:1px solid rgba(148,163,184,.14)}}li:first-child{{border-top:0}}.num{{width:34px;height:28px;border-radius:999px;display:grid;place-items:center;background:#1e293b;color:#94a3b8;font-size:11px;font-weight:950}}li .wait{{position:absolute;left:44px;color:#64748b;font-size:13px;animation:hide .2s ease var(--d) forwards}}li b{{opacity:0;transform:translateX(-10px);font-size:16px;color:white;animation:show .42s ease var(--d) forwards}}@keyframes hide{{to{{opacity:0}}}}@keyframes show{{to{{opacity:1;transform:none}}}}.foot{{margin-top:14px;color:#86efac;font-size:13px;font-weight:800;opacity:0;animation:show .35s ease {duration:.2f}s forwards}}@media(max-width:620px){{.draw{{padding:14px 8px;border-radius:18px}}.grid{{grid-template-columns:1fr;gap:9px}}.box{{padding:10px 12px}}.title{{font-size:16px}}li b{{overflow-wrap:anywhere;word-break:break-word}}}}</style>{FIT_SCRIPT}""",height=max(420,180+max(len(rows) for _,rows in groups)*55+(len(groups)-1)*20),scrolling=True)


def standings_df(rows):
    return pd.DataFrame([{"#":r["position"],"Gracz":r["name"],"Drużyna":r["team"],"M":r["m"],"W":r["w"],"R":r["d"],"P":r["l"],"Bramki":f'{r["gf"]}:{r["ga"]}',"+/-":r["gd"],"Pkt":r["pts"]} for r in rows])


def result_text(m):
    if m.get("home_score") is None:return "—"
    s=f'{m["home_score"]}:{m["away_score"]}'
    if m.get("home_penalties") is not None:s+=f' (k. {m["home_penalties"]}:{m["away_penalties"]})'
    return s


def render_double5_mid_draw(player_name: str, candidates: list[dict], selected: dict):
    names=[html.escape(str(c.get("name") or "?")) for c in candidates]
    sel=html.escape(str((selected or {}).get("name") or "?"))
    cand_html="".join(f"<div class='cand' style='--d:{0.8+i*4.5:.2f}s'>{n}</div>" for i,n in enumerate(names))
    finish_delay=0.8+max(len(names)-1,0)*4.5+1.2
    components.html(f"""<div class='mid'><div class='eye'>NADZWYCZAJNE LOSOWANIE</div><div class='title'>Koniec wakacji dla <b>{html.escape(player_name)}</b></div><div class='sub'>Losujemy zwycięzcę, z którym zagra gracz ze Szczęśliwym losem.</div><div class='cands'>{cand_html}</div><div class='arrow'>↓</div><div class='selected'><span>PRZECIWNIK</span><b>{sel}</b></div><div class='j'>Szczęśliwy los dobiegł końca. Prosimy zejść z leżaka.</div></div>
    <style>html,body{{margin:0;background:transparent;font-family:Inter,system-ui}}*{{box-sizing:border-box}}.mid{{max-width:720px;margin:auto;padding:24px;border-radius:24px;background:radial-gradient(circle at 50% 0,#233b63,#111c30 44%,#0b1220);border:1px solid rgba(148,163,184,.22);color:#f8fafc;text-align:center}}.eye{{font-size:11px;font-weight:950;letter-spacing:.18em;color:#7dd3fc}}.title{{font-size:23px;font-weight:950;margin:5px 0}}.sub{{color:#94a3b8;font-size:14px}}.cands{{display:grid;grid-template-columns:repeat({max(1,len(names))},1fr);gap:10px;margin:18px auto 8px;max-width:560px}}.cand{{padding:15px 8px;border-radius:15px;background:#17233a;border:1px solid #334155;font-weight:900;opacity:.45;animation:pulse .65s ease var(--d) 2 alternate}}@keyframes pulse{{to{{opacity:1;transform:scale(1.05);border-color:#7dd3fc}}}}.arrow{{font-size:25px;color:#64748b}}.selected{{display:inline-flex;flex-direction:column;gap:2px;min-width:260px;padding:14px 24px;border-radius:18px;background:#052e2b;border:1px solid #34d399;opacity:0;animation:show .35s ease {finish_delay:.2f}s forwards}}.selected span{{font-size:10px;letter-spacing:.15em;color:#6ee7b7;font-weight:950}}.selected b{{font-size:25px}}.j{{margin-top:14px;color:#cbd5e1;opacity:0;animation:show .35s ease {finish_delay+0.4:.2f}s forwards}}@keyframes show{{to{{opacity:1}}}}@media(max-width:560px){{.mid{{padding:16px 8px;border-radius:18px}}.cands{{grid-template-columns:1fr;gap:8px}}.selected{{min-width:0;width:100%}}.selected b{{overflow-wrap:anywhere}}}}</style>{FIT_SCRIPT}""",height=410,scrolling=True)



def render_double_wb_pairing_draw(format_key: str, pairs: list[dict]):
    cards=[]
    for i,p in enumerate(pairs):
        cards.append(f"<div class='pair' style='--d:{0.9+i*4.5:.2f}s'><span>WINNERS BRACKET • M{int(p.get('match_no') or 0)}</span><b>{html.escape(str(p.get('home_name') or '?'))}</b><i>VS</i><b>{html.escape(str(p.get('away_name') or '?'))}</b></div>")
    subtitle='Po pierwszej rundzie losujemy pary następnej rundy Winners Bracket.'
    finish_delay=0.9+max(len(pairs)-1,0)*4.5+1.0
    components.html(f"""<div class='wb'><div class='eye'>LOSOWANIE WINNERS BRACKET</div><div class='title'>Kto gra z kim?</div><div class='sub'>{subtitle}</div><div class='pairs'>{''.join(cards)}</div><div class='foot'>Pary wylosowane. Drabinka jedzie dalej.</div></div><style>html,body{{margin:0;background:transparent;font-family:Inter,system-ui}}*{{box-sizing:border-box}}.wb{{max-width:820px;margin:auto;padding:24px;border-radius:24px;background:radial-gradient(circle at 50% 0,#19395a,#101d32 44%,#0b1220);border:1px solid rgba(148,163,184,.22);color:#f8fafc;text-align:center}}.eye{{font-size:11px;font-weight:950;letter-spacing:.18em;color:#7dd3fc}}.title{{font-size:26px;font-weight:1000;margin:5px 0}}.sub{{color:#94a3b8;font-size:14px}}.pairs{{display:grid;grid-template-columns:repeat(2,1fr);gap:12px;margin-top:18px}}.pair{{padding:18px 12px;border-radius:18px;background:#111c31;border:1px solid #334155;display:grid;gap:5px;opacity:0;transform:translateY(10px);animation:reveal .45s ease var(--d) forwards}}.pair span{{font-size:10px;letter-spacing:.1em;color:#94a3b8;font-weight:900}}.pair b{{font-size:20px}}.pair i{{font-style:normal;color:#64748b;font-size:12px;font-weight:900}}.foot{{margin-top:14px;color:#86efac;opacity:0;animation:reveal .35s ease {finish_delay:.2f}s forwards}}@keyframes reveal{{to{{opacity:1;transform:none}}}}@media(max-width:620px){{.wb{{padding:16px 8px;border-radius:18px}}.pairs{{grid-template-columns:1fr;gap:8px}}.pair b{{font-size:18px;overflow-wrap:anywhere;word-break:break-word}}.title{{font-size:22px}}}}</style>{FIT_SCRIPT}""",height=340,scrolling=True)

def render_double7_combined_draw(pairs: list[dict], candidates: list[dict], selected_lucky: dict):
    sel_id=(selected_lucky or {}).get("player_id")
    pair_cards=[]
    for i,p in enumerate(pairs):
        pair_cards.append(f"<div class='pair' style='--d:{0.9+i*4.5:.2f}s'><span>WINNERS • M{int(p.get('match_no') or 0)}</span><b>{html.escape(str(p.get('home_name') or '?'))}</b><i>VS</i><b>{html.escape(str(p.get('away_name') or '?'))}</b></div>")
    lucky_cards=[]
    for i,c in enumerate(candidates):
        chosen=str(c.get("player_id"))==str(sel_id)
        lucky_cards.append(f"<div class='loser {'win' if chosen else ''}' style='--d:{0.9+(len(pairs)+i)*4.5:.2f}s'><span>PRZEGRANY M{int(c.get('match_no') or 0)}</span><b>{html.escape(str(c.get('name') or '?'))}</b><em>{'🍀 SZCZĘŚLIWY LOS' if chosen else 'GRA DALEJ'}</em></div>")
    total_steps=len(pairs)+len(candidates)
    finish_delay=0.9+max(total_steps-1,0)*4.5+1.0
    components.html(f"""<div class='combo'><div class='eye'>LOSOWANIE DOUBLE ELIMINATION</div><div class='title'>Winners + Losers</div><div class='sub'>Jedno losowanie ustala pary Winners Bracket i Szczęśliwy los w Losers Bracket.</div><div class='label'>WINNERS BRACKET</div><div class='pairs'>{''.join(pair_cards)}</div><div class='label lucky'>LOSERS BRACKET • SZCZĘŚLIWY LOS</div><div class='losers'>{''.join(lucky_cards)}</div><div class='foot'>Losowanie zakończone. Drabinka gotowa.</div></div><style>html,body{{margin:0;background:transparent;font-family:Inter,system-ui}}*{{box-sizing:border-box}}.combo{{max-width:850px;margin:auto;padding:22px;border-radius:24px;background:radial-gradient(circle at 50% 0,#203d5c,#111a2d 45%,#0b1220);border:1px solid rgba(148,163,184,.22);color:#f8fafc;text-align:center}}.eye{{font-size:11px;font-weight:950;letter-spacing:.18em;color:#7dd3fc}}.title{{font-size:27px;font-weight:1000;margin:5px 0}}.sub{{color:#94a3b8;font-size:14px;margin-bottom:16px}}.label{{font-size:11px;font-weight:950;letter-spacing:.14em;color:#7dd3fc;margin:8px 0}}.label.lucky{{color:#fde68a;margin-top:17px}}.pairs{{display:grid;grid-template-columns:repeat(2,1fr);gap:10px}}.pair{{padding:15px 10px;border-radius:17px;background:#111c31;border:1px solid #334155;display:grid;gap:3px;opacity:0;transform:translateY(8px);animation:reveal .38s ease var(--d) forwards}}.pair span,.loser span{{font-size:10px;letter-spacing:.1em;color:#94a3b8;font-weight:900}}.pair b,.loser b{{font-size:18px}}.pair i{{font-style:normal;color:#64748b;font-size:11px;font-weight:900}}.losers{{display:grid;grid-template-columns:repeat(3,1fr);gap:9px}}.loser{{padding:13px 8px;border-radius:16px;background:#171827;border:1px solid #334155;display:flex;flex-direction:column;gap:4px;opacity:0;transform:translateY(8px);animation:reveal .35s ease var(--d) forwards}}.loser em{{font-style:normal;font-size:10px;color:#cbd5e1;font-weight:950}}.loser.win{{border-color:#fbbf24;background:#422006;box-shadow:0 0 0 1px rgba(251,191,36,.2)}}.loser.win em{{color:#fde68a}}.foot{{margin-top:14px;color:#86efac;opacity:0;animation:reveal .35s ease {finish_delay:.2f}s forwards}}@keyframes reveal{{to{{opacity:1;transform:none}}}}@media(max-width:620px){{.combo{{padding:15px 8px;border-radius:18px}}.pairs{{grid-template-columns:1fr}}.losers{{grid-template-columns:1fr;gap:7px}}.pair,.loser{{padding:11px 7px}}.pair b,.loser b{{font-size:17px;overflow-wrap:anywhere;word-break:break-word}}.title{{font-size:22px}}}}</style>{FIT_SCRIPT}""",height=575,scrolling=True)


def render_double7_lb_bye(candidates: list[dict], selected: dict):
    sel_id=(selected or {}).get("player_id")
    cards=[]
    for i,c in enumerate(candidates):
        chosen=str(c.get("player_id"))==str(sel_id)
        cards.append(f"<div class='loser {'win' if chosen else ''}' style='--d:{0.9+i*4.5:.2f}s'><span>PRZEGRANY M{int(c.get('match_no') or 0)}</span><b>{html.escape(str(c.get('name') or '?'))}</b><em>{'🍀 SZCZĘŚLIWY LOS' if chosen else '💀 GRA DALEJ'}</em></div>")
    finish_delay=0.9+max(len(candidates)-1,0)*4.5+1.0
    components.html(f"""<div class='mid'><div class='eye'>LOSERS BRACKET LOTTERY</div><div class='title'>Trzy porażki. Tylko jedna nagroda.</div><div class='sub'>Losujemy szczęście w nieszczęściu.</div><div class='grid'>{''.join(cards)}</div><div class='j'>Przegrał mecz, wygrał losowanie. Bilans się zgadza.</div></div><style>html,body{{margin:0;background:transparent;font-family:Inter,system-ui}}*{{box-sizing:border-box}}.mid{{max-width:820px;margin:auto;padding:24px;border-radius:24px;background:radial-gradient(circle at 50% 0,#3b1d48,#151326 44%,#0b1220);border:1px solid rgba(148,163,184,.22);color:#f8fafc;text-align:center}}.eye{{font-size:11px;font-weight:950;letter-spacing:.18em;color:#f0abfc}}.title{{font-size:23px;font-weight:950;margin:5px 0}}.sub{{color:#94a3b8}}.grid{{display:grid;grid-template-columns:repeat(3,1fr);gap:10px;margin-top:20px}}.loser{{display:flex;flex-direction:column;gap:5px;padding:18px 10px;border-radius:18px;background:#171827;border:1px solid #334155;opacity:0;transform:translateY(8px);animation:reveal .4s ease var(--d) forwards}}.loser span{{font-size:10px;letter-spacing:.11em;color:#94a3b8;font-weight:900}}.loser b{{font-size:20px}}.loser em{{font-style:normal;font-size:12px;color:#fda4af;font-weight:900;opacity:0;animation:show .25s ease {finish_delay:.2f}s forwards}}.loser.win{{border-color:#fbbf24;box-shadow:0 0 0 1px rgba(251,191,36,.25);animation:reveal .4s ease var(--d) forwards, winner .45s ease {finish_delay:.2f}s forwards}}.loser.win em{{color:#fde68a}}@keyframes reveal{{to{{opacity:1;transform:none}}}}@keyframes winner{{to{{background:#422006;transform:scale(1.04)}}}}@keyframes show{{to{{opacity:1}}}}.j{{margin-top:15px;color:#cbd5e1;opacity:0;animation:show .3s ease {finish_delay+0.4:.2f}s forwards}}@media(max-width:620px){{.mid{{padding:16px 8px;border-radius:18px}}.grid{{grid-template-columns:1fr;gap:8px}}.loser{{padding:13px 8px}}.loser b{{font-size:18px;overflow-wrap:anywhere}}}}</style>{FIT_SCRIPT}""",height=410,scrolling=True)


def render_playoff_reveal(format_key: str, pairs: list[dict], direct: list[dict] | None = None):
    direct=direct or []
    direct_html=""
    if direct:
        d="".join(f"<div class='bye'><span>GRUPA {html.escape(str(x.get('group')))}</span><b>{html.escape(str(x.get('name') or '?'))}</b><em>🎟️ PROSTO DO PÓŁFINAŁU</em></div>" for x in direct)
        direct_html=f"<div class='direct'>{d}</div>"
    cards=[]
    for i,p in enumerate(pairs):
        stage={"SF":"PÓŁFINAŁ","BARRAGE":"BARAŻ"}.get(p.get("stage"),"ĆWIERĆFINAŁ")
        cards.append(f"<div class='pair' style='--d:{1.0+i*4.5:.2f}s'><span>{stage} • M{int(p.get('match_no') or 0)}</span><b>{html.escape(str(p.get('home_name') or '?'))}</b><i>VS</i><b>{html.escape(str(p.get('away_name') or '?'))}</b></div>")
    finish_delay=1.0+max(len(pairs)-1,0)*4.5+1.0
    headline="FAZA PUCHAROWA" if format_key!="groups6" else "PÓŁFINAŁY"
    components.html(f"""<div class='po'><div class='eye'>FAZA GRUPOWA ZAKOŃCZONA</div><div class='title'>{headline}</div>{direct_html}<div class='pairs'>{''.join(cards)}</div><div class='foot'>VAR przeliczył tabelę. Reklamacji brak.</div></div><style>html,body{{margin:0;background:transparent;font-family:Inter,system-ui}}*{{box-sizing:border-box}}.po{{max-width:850px;margin:auto;padding:24px;border-radius:24px;background:radial-gradient(circle at 50% 0,#163b46,#101d32 45%,#0b1220);border:1px solid rgba(148,163,184,.22);color:#f8fafc;text-align:center}}.eye{{font-size:11px;font-weight:950;letter-spacing:.18em;color:#67e8f9}}.title{{font-size:27px;font-weight:1000;margin:5px 0 16px}}.direct{{display:grid;grid-template-columns:repeat(2,1fr);gap:10px;margin-bottom:12px}}.bye{{padding:14px;border-radius:16px;background:#052e2b;border:1px solid #10b981;display:flex;flex-direction:column}}.bye span{{font-size:10px;color:#6ee7b7;font-weight:900}}.bye b{{font-size:18px}}.bye em{{font-style:normal;font-size:10px;color:#a7f3d0;font-weight:900}}.pairs{{display:grid;grid-template-columns:repeat(2,1fr);gap:12px}}.pair{{padding:17px 12px;border-radius:18px;background:#111c31;border:1px solid #334155;display:grid;gap:4px;opacity:0;transform:translateY(8px);animation:reveal .42s ease var(--d) forwards}}.pair span{{font-size:10px;letter-spacing:.1em;color:#94a3b8;font-weight:900}}.pair b{{font-size:18px}}.pair i{{font-style:normal;color:#64748b;font-size:11px;font-weight:900}}.foot{{margin-top:14px;color:#86efac;opacity:0;animation:reveal .35s ease {finish_delay:.2f}s forwards}}@keyframes reveal{{to{{opacity:1;transform:none}}}}@media(max-width:620px){{.po{{padding:16px 8px;border-radius:18px}}.direct,.pairs{{grid-template-columns:1fr;gap:8px}}.pair b,.bye b{{overflow-wrap:anywhere;word-break:break-word}}.title{{font-size:22px}}}}</style>{FIT_SCRIPT}""",height=430 if direct else 330,scrolling=True)


def render_synced_setup_tv(tid: str, api_url: str):
    """Browser-side TV view for pre-tournament draws controlled from the phone.

    JavaScript polls the lightweight API feed directly.  This avoids Streamlit's
    multi-second rerun cadence and keeps a queue of draw events, so rapid phone actions
    are animated one by one instead of collapsing into the final state.
    """
    import json as _json
    feed_url=f"{str(api_url).rstrip('/')}/api/v1/tv/feed/{tid}"
    url_js=_json.dumps(feed_url)
    components.html(f"""
    <div id="tvroot" class="tvroot">
      <div class="top"><div><div class="eyebrow">FIFA NIGHT • TV SYNC</div><div id="headline" class="headline">Łączę ekran z losowaniem…</div></div><div class="live"><i></i> TELEFON STERUJE</div></div>
      <div id="stage" class="stage"><div class="loader"></div><div class="muted">Czekam na stan turnieju.</div></div>
      <div class="foot">Losowania są kolejkowane — ekran nie pomija szybkich akcji z telefonu.</div>
    </div>
    <style>
    html,body{{margin:0;background:transparent;font-family:Inter,Segoe UI,system-ui;color:#f8fafc}}*{{box-sizing:border-box}}
    .tvroot{{max-width:1050px;margin:0 auto;padding:22px 24px 18px;border-radius:26px;background:radial-gradient(circle at 50% 0,#173853 0,#0f1d31 43%,#091321 100%);border:1px solid rgba(148,163,184,.22);min-height:590px;box-shadow:0 18px 55px rgba(2,8,23,.25)}}
    .top{{display:flex;justify-content:space-between;gap:18px;align-items:center;margin-bottom:18px}}.eyebrow{{font-size:11px;letter-spacing:.18em;font-weight:950;color:#7dd3fc}}.headline{{font-size:clamp(25px,4vw,38px);font-weight:1000;margin-top:3px}}
    .live{{font-size:11px;font-weight:950;letter-spacing:.08em;color:#86efac;background:#062c25;border:1px solid #145c48;border-radius:999px;padding:8px 12px;white-space:nowrap}}.live i{{display:inline-block;width:8px;height:8px;border-radius:50%;background:#34d399;margin-right:6px;box-shadow:0 0 0 4px rgba(52,211,153,.12)}}
    .stage{{min-height:450px;display:grid;place-items:center}}.muted{{color:#94a3b8}}.foot{{text-align:center;color:#64748b;font-size:12px;margin-top:8px}}
    .grid{{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px;width:100%}}.card{{padding:17px;border-radius:18px;background:#101c31;border:1px solid #2a4059}}.card b{{font-size:20px}}.card small{{display:block;color:#94a3b8;font-weight:850;letter-spacing:.08em;margin-bottom:4px}}
    .order{{width:min(720px,100%);display:grid;gap:8px}}.row{{padding:13px 16px;border-radius:15px;background:#101c31;border:1px solid #2a4059;display:flex;align-items:center;gap:14px;opacity:0;transform:translateY(9px);animation:reveal .42s ease var(--d) forwards}}.num{{width:34px;height:34px;border-radius:999px;background:#18324b;color:#7dd3fc;display:grid;place-items:center;font-weight:950}}.row b{{font-size:21px}}
    .wheelWrap{{width:100%;display:grid;grid-template-columns:minmax(380px,520px) 1fr;gap:34px;align-items:center;justify-content:center}}.wheelBox{{position:relative;width:min(76vw,500px);aspect-ratio:1;margin:auto}}.wheel{{position:absolute;inset:12px;border-radius:50%;border:8px solid #e8f1fa;box-shadow:0 20px 30px rgba(0,0,0,.35);transform:rotate(0deg)}}.wheel.spin{{animation:spin 10s cubic-bezier(.08,.72,.10,1) forwards}}.pointer{{position:absolute;z-index:5;top:-2px;left:50%;transform:translateX(-50%);width:0;height:0;border-left:18px solid transparent;border-right:18px solid transparent;border-top:36px solid #f8fafc;filter:drop-shadow(0 3px 3px rgba(0,0,0,.4))}}.hub{{position:absolute;z-index:4;left:50%;top:50%;transform:translate(-50%,-50%);width:84px;height:84px;border-radius:50%;background:#081421;border:7px solid #f8fafc;display:grid;place-items:center;font-weight:1000;font-size:22px}}.wlabel{{position:absolute;left:50%;top:50%;width:116px;margin-left:-58px;text-align:center;font-size:12px;font-weight:1000;color:white;text-shadow:0 2px 3px #000;transform-origin:50% 50%}}
    .result{{text-align:left}}.result .who{{color:#94a3b8;font-size:15px}}.result .name{{font-size:30px;font-weight:1000;margin:4px 0 8px}}.result .team{{font-size:clamp(26px,4vw,42px);font-weight:1000;color:#86efac;opacity:0;transform:translateY(8px);animation:reveal .4s ease 9.7s forwards}}.result .idleTeam{{font-size:16px;color:#94a3b8;opacity:1;transform:none;animation:none}}.chips{{display:flex;flex-wrap:wrap;gap:7px;margin-top:15px}}.chip{{padding:5px 8px;border-radius:999px;background:#14283e;color:#a8bed3;font-size:10px;font-weight:850}}
    .drawGrid{{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:10px;width:100%}}.drawItem{{padding:15px;border-radius:17px;background:#101c31;border:1px solid #334155;opacity:0;transform:translateY(8px);animation:reveal .4s ease var(--d) forwards}}.drawItem span{{display:block;color:#7dd3fc;font-size:11px;font-weight:950;letter-spacing:.1em}}.drawItem b{{font-size:20px}}
    .matchDrawGrid{{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:13px;width:100%}}.matchDraw{{padding:15px;border-radius:19px;background:#101c31;border:1px solid #334155;text-align:left}}.matchDraw.playin{{border-color:#b7791f;background:linear-gradient(145deg,#31230d,#151b29)}}.matchBadge{{display:inline-block;margin-bottom:10px;padding:5px 9px;border-radius:999px;background:#17283c;color:#9fdcf6;font-size:11px;font-weight:1000;letter-spacing:.08em}}.playin .matchBadge{{background:#4a3008;color:#fde68a}}.matchDuel{{display:grid;grid-template-columns:minmax(0,1fr) 42px minmax(0,1fr);gap:8px;align-items:stretch}}.drawSide{{min-height:76px;padding:12px 10px;border-radius:15px;background:#14243a;border:1px solid rgba(148,163,184,.2);display:flex;flex-direction:column;justify-content:center;text-align:center}}.drawSide.player{{opacity:0;transform:translateY(8px);animation:reveal .42s ease var(--d) forwards}}.drawSide.ref{{background:#0d1726;border-style:dashed}}.drawSide small{{color:#64748b;font-size:9px;font-weight:950;letter-spacing:.1em}}.drawSide b{{font-size:20px;overflow-wrap:anywhere}}.drawSide.ref b{{font-size:16px;color:#cbd5e1}}.matchVs{{display:grid;place-items:center;color:#64748b;font-size:12px;font-weight:1000}}.byeDraw{{grid-template-columns:minmax(0,1fr) 1fr}}.byeTag{{display:grid;place-items:center;border-radius:15px;background:#26330f;border:1px solid #64791d;color:#d9f99d;font-weight:1000}}
    .specialTitle{{font-size:30px;font-weight:1000;text-align:center;margin-bottom:16px}}.specialGrid{{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px;width:100%}}.pair{{padding:15px;border-radius:18px;background:#151c31;border:1px solid #4a5568;text-align:center}}.pair>small{{display:block;color:#94a3b8;font-weight:900;margin-bottom:9px}}.pairDuel{{display:grid;grid-template-columns:minmax(0,1fr) 38px minmax(0,1fr);gap:7px;align-items:center}}.pairSide{{min-height:68px;padding:10px 8px;border-radius:14px;background:#10263a;border:1px solid #29465e;display:flex;flex-direction:column;justify-content:center}}.pairSide.anim{{opacity:0;transform:translateY(8px);animation:reveal .4s ease var(--d) forwards}}.pairSide em{{font-style:normal;color:#64748b;font-size:9px;font-weight:950;letter-spacing:.1em}}.pairSide b{{font-size:19px;line-height:1.12;overflow-wrap:anywhere}}.pairVs{{color:#64748b;font-size:11px;font-weight:1000}}.lucky{{margin-top:18px;padding:16px 22px;border-radius:18px;border:1px solid #fbbf24;background:#422006;color:#fde68a;font-size:22px;font-weight:1000;text-align:center;opacity:0;animation:reveal .4s ease 4.2s forwards}}
    .bigReveal{{text-align:center;padding:36px 24px;border-radius:24px;background:linear-gradient(145deg,#10293b,#101827);border:1px solid #31536f;min-width:min(720px,100%)}}.bigReveal .icon{{font-size:54px}}.bigReveal h2{{font-size:34px;margin:8px 0}}.bigReveal p{{font-size:22px;color:#86efac;font-weight:900}}
    .loader{{width:45px;height:45px;border-radius:50%;border:4px solid #25405d;border-top-color:#34d399;animation:rot .8s linear infinite;margin:auto auto 12px}}
    @keyframes reveal{{to{{opacity:1;transform:none}}}}@keyframes rot{{to{{transform:rotate(360deg)}}}}@keyframes spin{{to{{transform:rotate(var(--rot))}}}}
    @media(max-width:760px){{.tvroot{{padding:16px 12px;min-height:520px}}.top{{align-items:flex-start}}.live{{font-size:9px}}.wheelWrap{{grid-template-columns:1fr;gap:10px}}.result{{text-align:center}}.wheelBox{{width:min(78vw,400px)}}.drawGrid,.matchDrawGrid,.specialGrid,.grid{{grid-template-columns:1fr}}.stage{{min-height:400px}}}}
    </style>
    <script>
    (()=>{{
      const FEED={url_js}; const root=document.getElementById('stage'); const headline=document.getElementById('headline');
      const seen=new Set(); const queue=[]; let initialized=false, playing=false, latest=null, timer=null;
      const esc=s=>String(s??'').replace(/[&<>"']/g,m=>({{'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}}[m]));
      const short=s=>{{s=String(s||'');const wc=s.match(/Dowolna drużyna(?: #(\\d+))?/i);if(wc)return wc[1]?`WC ${{wc[1]}}`:'WILD CARD';return s.replace('Manchester City','MAN CITY').replace('Bayern Monachium','BAYERN').replace('FC Barcelona','BARCA').slice(0,15).toUpperCase()}};
      function phaseName(p){{return ({{draft_order:'Losowanie kolejności draftu',team_draft:'Draft drużyn',team_draw:'Koło drużyn',structure_draw:'Losowanie struktury'}})[p]||'Przygotowanie FIFA Night'}}
      function wheelMarkup(pool,player,spinning,target,result){{
        pool=pool||[]; const n=Math.max(pool.length,1); const idx=Math.max(0,pool.indexOf(target)); const colors=['#2563EB','#DB2777','#0891B2','#EA580C','#16A34A','#7C3AED','#CA8A04','#DC2626'];
        const parts=pool.length?pool.map((_,i)=>`${{colors[i%colors.length]}} ${{i*360/n}}deg ${{(i+1)*360/n}}deg`).join(','):'#10283b 0deg 360deg';
        const labels=pool.map((x,i)=>{{const a=i*360/n+180/n;return `<span class="wlabel" style="transform:translate(-50%,-50%) rotate(${{a}}deg) translateY(-184px) rotate(${{-a}}deg)">${{esc(short(x))}}</span>`}}).join('');
        const rot=2880+(360-(idx*360/n+180/n)); const spinClass=spinning?' spin':''; const rotStyle=spinning?`;--rot:${{rot}}deg`:'';
        const resultHtml=result?`<div class="team">${{esc(result)}}</div>`:'<div class="team idleTeam">Kliknij „Zakręć kołem” na telefonie</div>';
        return `<div class="wheelWrap"><div class="wheelBox">${{spinning?'<div class="pointer"></div>':''}}<div class="wheel${{spinClass}}" style="background:conic-gradient(${{parts}})${{rotStyle}}">${{labels}}</div><div class="hub">FC</div></div><div class="result"><div class="who">${{spinning?'Losujemy dla':'Następny los'}}</div><div class="name">${{esc(player||'—')}}</div>${{resultHtml}}<div class="chips">${{pool.map(x=>`<span class="chip">${{esc(short(x))}}</span>`).join('')}}</div></div></div>`;
      }}
      function idle(feed){{if(playing)return; const t=feed?.tournament||{{}}, ps=feed?.players||[], meta=feed?.meta||{{}}; headline.textContent=phaseName(t.phase); let body='';
        if(t.phase==='team_draw'){{
          const waitingPlayers=ps.filter(p=>!Number(p.team_revealed)); const pool=waitingPlayers.map(p=>String(p.team||'')).filter(Boolean); const waiting=waitingPlayers[0]; const player=waiting?.name||'Losowanie drużyn zakończone';
          body=wheelMarkup(pool.length?pool:(meta.team_pool||[]),player,false,'','');
        }} else if(!ps.length) body='<div class="muted">Czekam na uczestników…</div>'; else body='<div class="grid">'+ps.map((p,i)=>`<div class="card"><small>${{i+1}}. GRACZ</small><b>${{esc(p.name)}}</b><div class="muted">${{p.team_revealed?esc(p.team||'—'):'oczekuje na losowanie'}}</div></div>`).join('')+'</div>';
        root.innerHTML=body;
      }}
      function finish(ms){{clearTimeout(timer);timer=setTimeout(()=>{{playing=false;idle(latest);playNext()}},ms)}}
      function play(ev){{playing=true; const p=ev.payload||{{}};
        if(ev.kind==='team_wheel'){{
          headline.textContent='🎡 Koło drużyn'; const pool=(p.pool||[]); root.innerHTML=wheelMarkup(pool,p.name,true,p.wheel_team,p.team||p.wheel_team||''); finish(12250); return;
        }}
        if(ev.kind==='draft_order'){{headline.textContent='🎱 Kto wybiera pierwszy?'; const rows=(p.players||[]).map((x,i)=>`<div class="row" style="--d:${{.9+i*4.5}}s"><span class="num">${{i+1}}</span><b>${{esc(x.name)}}</b></div>`).join(''); root.innerHTML=`<div class="order">${{rows}}</div>`;finish(2300+Math.max((p.players||[]).length-1,0)*4500);return}}
        if(ev.kind==='structure_draw'){{headline.textContent='🎲 Oficjalne losowanie turnieju';const preview=p.preview||[];if(preview.length){{let maxOrder=0;const side=(x,pos)=>{{if(!x)return '';if(x.kind==='player'){{const ord=Number(x.reveal_order||0);maxOrder=Math.max(maxOrder,ord);return `<div class="drawSide player" style="--d:${{1.0+ord*4.5}}s"><small>${{pos===0?'1. LOS':'2. LOS'}}</small><b>${{esc(x.name||'?')}}</b></div>`}}return `<div class="drawSide ref"><small>ZALEŻNOŚĆ</small><b>${{esc(x.name||x.label||'?')}}</b></div>`}};const cards=preview.map(x=>{{const badge=(x.match_no?`M${{x.match_no}} • `:'')+esc(x.stage_label||x.stage||'MECZ');const cls=String(x.stage||'')==='PLAY_IN'?' playin':'';const duel=x.away?`<div class="matchDuel">${{side(x.home,0)}}<div class="matchVs">VS</div>${{side(x.away,1)}}</div>`:`<div class="matchDuel byeDraw">${{side(x.home,0)}}<div class="byeTag">🍀 WOLNY LOS</div></div>`;return `<div class="matchDraw${{cls}}"><div class="matchBadge">${{badge}}</div>${{duel}}</div>`}}).join('');root.innerHTML=`<div class="matchDrawGrid">${{cards}}</div>`;finish(2500+maxOrder*4500);return}}const items=(p.items||[]).map((x,i)=>`<div class="drawItem" style="--d:${{1.0+i*4.5}}s"><span>${{esc(x.slot)}}</span><b>${{esc(x.name)}}</b></div>`).join('');root.innerHTML=`<div class="drawGrid">${{items}}</div>`;finish(2500+Math.max((p.items||[]).length-1,0)*4500);return}}
        if(ev.kind==='draft_pick'||ev.kind==='wildcard_confirm'){{headline.textContent=ev.kind==='draft_pick'?'⚽ Wybór drużyny':'🃏 Wild Card';root.innerHTML=`<div class="bigReveal"><div class="icon">${{ev.kind==='draft_pick'?'⚽':'🃏'}}</div><h2>${{esc(p.name)}}</h2><p>${{esc(p.team)}}</p></div>`;finish(2200);return}}
        if(ev.kind==='special_draw'){{const randomDraw=p.is_random_draw!==false;headline.textContent=randomDraw?'🎲 Losowanie w trakcie turnieju':'🎯 Ustalone pary fazy pucharowej';const pairs=(p.pairs||[]).map((x,i)=>{{const base=.9+i*4.5;const badge=(x.match_no?`M${{x.match_no}}`:(x.key||'PARA'))+(x.stage_label?' • '+x.stage_label:(x.stage?' • '+x.stage:''));const side=(name,pos,delay)=>`<div class="pairSide${{randomDraw?' anim':''}}"${{randomDraw?` style="--d:${{delay}}s"`:''}}><em>${{randomDraw?(pos===0?'1. LOS':'2. LOS'):'PARA'}}</em><b>${{esc(name||'?')}}</b></div>`;return `<div class="pair"><small>${{esc(badge)}}</small><div class="pairDuel">${{side(x.home_name,0,base)}}<div class="pairVs">VS</div>${{side(x.away_name,1,base+2.25)}}</div></div>`}}).join('');let lucky=p.selected_lucky?.name||p.name||'';root.innerHTML=`<div style="width:100%"><div class="specialTitle">${{p.special_kind==='group_playoffs'?'Faza pucharowa • pary z regulaminu':p.special_kind==='double7_combined'?'Winners + Szczęśliwy los':'Losowanie drabinki'}}</div><div class="specialGrid">${{pairs}}</div>${{lucky?`<div class="lucky slowLucky" style="animation-delay:${{1.2+(p.pairs||[]).length*4.5}}s">🍀 ${{esc(lucky)}}</div>`:''}}</div>`;finish(randomDraw?5200+Math.max((p.pairs||[]).length-1,0)*4500+(lucky?2800:0):1800);return}}
        if(ev.kind==='tournament_start'){{headline.textContent='✅ Losowanie zakończone';root.innerHTML='<div class="bigReveal"><div class="icon">🔥</div><h2>DRABINKA GOTOWA</h2><p>Zaczynamy FIFA Night</p></div>';finish(1800);return}}
        if(ev.kind==='stage'){{headline.textContent=esc(p.title||'Kolejny etap');root.innerHTML='<div class="bigReveal"><div class="icon">🎲</div><h2>'+esc(p.title||'Kolejny etap')+'</h2></div>';finish(1500);return}}
        finish(600);
      }}
      function playNext(){{if(playing||!queue.length)return;play(queue.shift())}}
      async function poll(){{try{{const r=await fetch(FEED,{{cache:'no-store'}});if(!r.ok)throw new Error('HTTP '+r.status);const feed=await r.json();latest=feed;const events=feed.events||[];const now=Date.now();
          if(!initialized){{events.forEach(e=>{{const age=now-Date.parse(e.created_at||0);seen.add(e.id);if(age>=0&&age<20000)queue.push(e)}});initialized=true}} else {{events.forEach(e=>{{if(!seen.has(e.id)){{seen.add(e.id);queue.push(e)}}}})}}
          if(!playing&&!queue.length)idle(feed);playNext();
        }}catch(e){{if(!playing){{headline.textContent='Czekam na połączenie…';root.innerHTML='<div><div class="loader"></div><div class="muted">Serwer TV chwilowo nie odpowiada. Próba ponownie za moment.</div></div>'}}}}}}
      poll();setInterval(poll,500);
    }})();
    </script>
    """,height=680,scrolling=False)


def render_visible_pair_draw(state: dict, *, title: str | None = None):
    """Large TV-friendly renderer for a true pair draw during a tournament."""
    pairs=list(state.get("pairs") or [])
    random_draw=state.get("is_random_draw") is not False
    stage_map={
        "PLAY_IN":"PLAY-IN","WB":"WINNERS BRACKET","WB_FINAL":"FINAŁ WINNERS",
        "LB":"LOSER BRACKET","LB_BRIDGE":"LOSER BRACKET • BRIDGE","LB_FINAL":"FINAŁ LOSER BRACKET",
        "SF":"PÓŁFINAŁ","QF":"ĆWIERĆFINAŁ","BARRAGE":"BARAŻ","FINAL":"WIELKI FINAŁ",
        "SWISS_R2":"SWISS • RUNDA 2","SWISS_R3":"SWISS • RUNDA 3",
    }
    cards=[]
    for i,p in enumerate(pairs):
        base=.8+i*4.5
        no=p.get("match_no")
        stage=str(p.get("stage") or "")
        label=str(p.get("stage_label") or stage_map.get(stage) or stage or "MECZ")
        badge=(f"M{int(no)} • " if no else "")+label
        playin=" playin" if stage=="PLAY_IN" else ""
        def side(name, pos, delay):
            label2=("1. LOS" if pos==0 else "2. LOS") if random_draw else "PARA"
            anim=" anim" if random_draw else ""
            style=f" style='--d:{delay:.2f}s'" if random_draw else ""
            return f"<div class='vside{anim}'{style}><span>{label2}</span><b>{html.escape(str(name or '?'))}</b></div>"
        cards.append(
            f"<div class='vpair{playin}'><div class='vbadge'>{html.escape(badge)}</div>"
            f"<div class='vduel'>{side(p.get('home_name'),0,base)}<div class='vvs'>VS</div>{side(p.get('away_name'),1,base+2.25)}</div></div>"
        )
    bye_html=""
    bye_pid=state.get("bye_player_id")
    if bye_pid:
        cand=next((x for x in (state.get("bye_candidates") or []) if str(x.get("player_id"))==str(bye_pid)),{})
        bye_html=f"<div class='vbye'>🍀 SZCZĘŚLIWY LOS • <b>{html.escape(str(cand.get('name') or '?'))}</b></div>"
    heading=title or ("Losowanie drabinki" if random_draw else "Ustalone pary")
    sub=("Najpierw pojawia się pierwszy zawodnik, potem jego rywal. Pokazane pary są wynikiem tego losowania."
         if random_draw else "Pary wynikają z regulaminu formatu — to reveal, nie losowanie.")
    finish=.8+max(len(pairs)-1,0)*4.5+(2.7 if pairs else .8)
    components.html(f"""<div class='visibleDraw'><div class='veye'>{'OFICJALNE LOSOWANIE' if random_draw else 'OFICJALNE ZESTAWIENIE'}</div><div class='vtitle'>{html.escape(heading)}</div><div class='vsub'>{html.escape(sub)}</div><div class='vgrid'>{''.join(cards)}</div>{bye_html}<div class='vfoot'>✅ {'Losowanie zakończone.' if random_draw else 'Pary potwierdzone.'}</div></div>
    <style>html,body{{margin:0;background:transparent;font-family:Inter,system-ui}}*{{box-sizing:border-box}}.visibleDraw{{max-width:1080px;margin:3px auto;padding:24px;border-radius:26px;background:radial-gradient(circle at 50% 0,#1a3f5c,#101d32 43%,#0b1220);border:1px solid rgba(148,163,184,.24);color:#f8fafc;text-align:center}}.veye{{font-size:11px;font-weight:950;letter-spacing:.2em;color:#7dd3fc}}.vtitle{{font-size:29px;font-weight:1000;margin:5px 0 2px}}.vsub{{color:#94a3b8;font-size:13px;margin-bottom:16px}}.vgrid{{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:14px}}.vpair{{padding:16px;border-radius:20px;background:#101c31;border:1px solid #334155;text-align:left;box-shadow:0 10px 25px rgba(0,0,0,.16)}}.vpair.playin{{background:linear-gradient(145deg,#35250d,#151b29);border-color:#b7791f}}.vbadge{{display:inline-block;margin-bottom:10px;padding:5px 10px;border-radius:999px;background:#17283c;color:#a5def7;font-size:11px;font-weight:1000;letter-spacing:.08em}}.playin .vbadge{{background:#503609;color:#fde68a}}.vduel{{display:grid;grid-template-columns:minmax(0,1fr) 42px minmax(0,1fr);align-items:stretch;gap:8px}}.vside{{min-height:82px;padding:12px 10px;border-radius:15px;background:#14243a;border:1px solid rgba(148,163,184,.2);display:flex;flex-direction:column;justify-content:center;text-align:center}}.vside span{{font-size:9px;font-weight:1000;letter-spacing:.13em;color:#64748b}}.vside b{{font-size:21px;line-height:1.12;overflow-wrap:anywhere}}.vside.anim{{opacity:0;transform:translateY(9px) scale(.98);animation:vreveal .42s ease var(--d) forwards}}.vvs{{display:grid;place-items:center;font-size:12px;color:#64748b;font-weight:1000}}.vbye{{margin:15px auto 0;max-width:520px;padding:13px;border-radius:16px;background:#3b2b08;border:1px solid #a16207;color:#fde68a;font-size:17px}}.vfoot{{margin-top:15px;color:#86efac;font-size:13px;font-weight:850;opacity:0;animation:vreveal .35s ease {finish:.2f}s forwards}}@keyframes vreveal{{to{{opacity:1;transform:none}}}}@media(max-width:760px){{.visibleDraw{{padding:16px 9px}}.vgrid{{grid-template-columns:1fr;gap:9px}}.vtitle{{font-size:23px}}.vside b{{font-size:18px}}}}</style>{FIT_SCRIPT}""",height=max(430,245+((len(cards)+1)//2)*130+(55 if bye_html else 0)),scrolling=True)

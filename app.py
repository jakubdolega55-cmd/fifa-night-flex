from __future__ import annotations

import html
import os
import pandas as pd
import streamlit as st

from database import Database
from logic import BASE_TEAMS, SEVEN_TEAMS, FORMAT_LABELS, FORMAT_MATCH_COUNTS
from ui import (hero, inject_css, render_wheel, render_structure_draw, render_draft_order, standings_df, result_text,
                render_double5_mid_draw, render_double7_lb_bye, render_playoff_reveal)

st.set_page_config(page_title="FIFA Night Flex",page_icon="⚽",layout="wide",initial_sidebar_state="collapsed")
inject_css(); db=Database()
if not st.session_state.get("_flex_schema_ready"):
    db.init_schema(); st.session_state._flex_schema_ready=True


def esc(x):return html.escape(str(x or ""))
def format_option(x):return f"{FORMAT_LABELS[x]} • {FORMAT_MATCH_COUNTS[x]}"
def rr():st.rerun()
def rf():st.rerun(scope="fragment")

def admin_password():
    value=os.getenv("ADMIN_PASSWORD")
    if value:return value
    try:return str(st.secrets.get("ADMIN_PASSWORD") or "")
    except Exception:return ""

def admin_ok(value):
    secret=admin_password()
    return bool(secret) and str(value)==secret

def render_history_admin():
    st.markdown("### 🔐 Historia i baza")
    locked=db.history_locked(); secret_ready=bool(admin_password())
    if locked: st.success("🔒 Historia jest zablokowana przed usuwaniem.")
    else: st.warning("🔓 Historia jest odblokowana.")
    if not secret_ready:
        st.error("Brak ADMIN_PASSWORD w Streamlit Secrets. Operacje administracyjne są wyłączone.")
        return
    if locked:
        with st.form("unlock_history"):
            pwd=st.text_input("Hasło administratora",type="password",key="unlock_pwd")
            go=st.form_submit_button("🔓 ODBLOKUJ HISTORIĘ",use_container_width=True)
        if go:
            if admin_ok(pwd): db.set_history_locked(False);st.success("Historia odblokowana.");rr()
            else: st.error("Nieprawidłowe hasło.")
        return
    with st.form("lock_history"):
        pwd=st.text_input("Hasło administratora",type="password",key="lock_pwd")
        go=st.form_submit_button("🔒 ZABLOKUJ HISTORIĘ",use_container_width=True)
    if go:
        if admin_ok(pwd): db.set_history_locked(True);st.success("Historia zablokowana.");rr()
        else: st.error("Nieprawidłowe hasło.")
    last=db.last_completed_tournament()
    if last:
        fmt=FORMAT_LABELS.get(last.get("format_key"),"Klasyczny turniej 6-osobowy")
        st.caption(f"Ostatni turniej: {last.get('player_count','?')} graczy • {fmt} • mistrz: {last.get('champion_name') or '?'}")
        with st.form("delete_last_history"):
            pwd=st.text_input("Hasło administratora",type="password",key="del_last_pwd")
            yes=st.checkbox("Tak, usuń ostatni zakończony turniej nietestowy")
            go=st.form_submit_button("🗑️ USUŃ OSTATNI TURNIEJ",use_container_width=True)
        if go:
            if not admin_ok(pwd): st.error("Nieprawidłowe hasło.")
            elif not yes: st.error("Zaznacz potwierdzenie.")
            else:
                deleted=db.delete_last_completed_tournament();st.success("Ostatni turniej został usunięty." if deleted else "Brak turnieju do usunięcia.");rr()
    else: st.caption("Brak zakończonych turniejów nietestowych do usunięcia.")
    with st.form("clear_all_history"):
        pwd=st.text_input("Hasło administratora",type="password",key="clear_all_pwd")
        confirm=st.text_input("Wpisz USUŃ HISTORIĘ")
        go=st.form_submit_button("💣 WYCZYŚĆ CAŁĄ HISTORIĘ",use_container_width=True)
    if go:
        if not admin_ok(pwd): st.error("Nieprawidłowe hasło.")
        elif confirm!="USUŃ HISTORIĘ": st.error("Wpisz dokładnie: USUŃ HISTORIĘ")
        else: db.clear_all_history();st.success("Historia wszystkich turniejów została wyczyszczona. Zapamiętane nicki zostały zachowane.");rr()

def format_for(count:int)->str:
    if count==4:return "league4_final"
    if count==5:return st.session_state.get("format5","double5")
    if count==6:return st.session_state.get("format6","groups6")
    return st.session_state.get("format7","double7")

def start_defaults(count:int):
    key=f"_lineup_init_{count}"
    if st.session_state.get(key):return
    vals=db.last_lineup(count)
    for i in range(count):st.session_state[f"p_{count}_{i}"]=vals[i] if i<len(vals) else ""
    st.session_state[key]=True


def render_start():
    hero("Wybierz liczbę graczy i format turnieju.")
    if not db.is_postgres:st.warning("Tryb lokalny SQLite. Na Streamlit Cloud podłącz DATABASE_URL z Neon.")
    default=db.last_player_count() if "player_count" not in st.session_state else st.session_state.player_count
    if default not in (4,5,6,7):default=6
    count=st.segmented_control("Liczba graczy",[4,5,6,7],default=default,key="player_count") or default
    start_defaults(count)
    if count==5:
        st.session_state.format5=st.radio("Format dla 5 graczy",["double5","league5_final"],format_func=format_option,horizontal=False,key="format5_radio")
    elif count==6:
        st.session_state.format6=st.radio("Format dla 6 graczy",["groups6","groups6_full"],format_func=format_option,horizontal=False,key="format6_radio")
    elif count==7:
        st.session_state.format7=st.radio("Format dla 7 graczy",["double7","groups7","groups7_sf"],format_func=format_option,horizontal=False,key="format7_radio")
    fmt=format_for(count)
    st.markdown(f"**Format:** {FORMAT_LABELS[fmt]}  \n**Łącznie:** {FORMAT_MATCH_COUNTS[fmt]}")
    with st.form(f"create_{count}_{fmt}"):
        cols=st.columns(2); names=[]
        for i in range(count):
            with cols[i%2]:names.append(st.text_input(f"Gracz {i+1}",key=f"p_{count}_{i}",placeholder="Wpisz nick"))
        if count in (4,5):
            teams=BASE_TEAMS.copy()
            st.markdown("**Draft drużyn:** najpierw losujemy kolejność wyboru, potem każdy wybiera z pozostałej puli.")
            st.caption("Bayern • Barcelona • PSG • Liverpool • Man City • Wild Card (Real Madryt banned)")
        elif count==6:
            teams=BASE_TEAMS.copy(); st.caption("Pula drużyn: Bayern, Barcelona, PSG, Liverpool, Man City + dzika karta (Real banned).")
        else:
            teams=SEVEN_TEAMS.copy(); st.caption("Pula drużyn: 5 klubów + 2 dzikie karty. Real Madryt banned.")
        test=st.toggle("🧪 Tryb testowy",value=True,key=f"test_{count}")
        go=st.form_submit_button("🎮 UTWÓRZ TURNIEJ",type="primary",use_container_width=True)
    if go:
        try:db.create_tournament(names,count,fmt,teams,test);st.session_state.pop("last_spin",None);rr()
        except ValueError as e:st.error(str(e))
    with st.expander("⚙️ Historia i baza"):
        render_history_admin()

@st.fragment
def draft_order(tid:str):
    b=db.bundle(tid); players=b["players"]; meta=b["meta"]; extra=meta["extra"]
    revealed=bool(extra.get("draft_order_revealed",False))
    if not revealed:
        if st.button("🎱 LOSUJ KOLEJNOŚĆ WYBORU",type="primary",use_container_width=True,key=f"draft_reveal_{tid}"):
            db.reveal_draft_order(tid);rf()
        return
    render_draft_order(players,int(extra.get("draft_redraw_count",0)))
    c1,c2=st.columns(2)
    with c1:
        if st.button("✅ ZATWIERDŹ KOLEJNOŚĆ",type="primary",use_container_width=True,key=f"draft_accept_{tid}"):
            db.confirm_draft_order(tid);rr()
    with c2:
        if st.button("💸 ZAPŁAĆ I WYLOSUJ PONOWNIE",use_container_width=True,key=f"draft_reroll_{tid}_{extra.get('draft_redraw_count',0)}"):
            db.reroll_draft_order(tid);rf()


def render_draft_order_stage(t):
    hero(f"Etap 1/3 • losowanie kolejności wyboru • {t['player_count']} graczy")
    draft_order(t["id"]);reset_controls(t,"draft_order")


@st.fragment
def team_draft(tid:str):
    b=db.bundle(tid); players=b["players"]; pool=b["meta"]["team_pool"]
    picked=[p for p in players if int(p.get("team_revealed") or 0)]
    waiting=[p for p in players if not int(p.get("team_revealed") or 0)]
    if not waiting:
        if st.button("🎲 PRZEJDŹ DO LOSOWANIA TURNIEJU",type="primary",use_container_width=True,key=f"draft_done_{tid}"):
            db.start_structure_draw(tid);rr()
        return
    current=waiting[0]; remaining=db.available_draft_teams(tid)
    st.markdown(f"### {len(picked)+1}. wybór — {esc(current['name'])}")
    if picked:
        st.markdown("**Wybrane:** " + " • ".join(f"{esc(p['name'])}: {esc(p['team'])}" for p in picked))
    with st.form(f"pick_team_{tid}_{current['player_id']}"):
        slot=st.selectbox("Drużyna",remaining,key=f"pick_slot_{tid}_{current['player_id']}")
        wildcard=st.text_input("Wild Card — wpisz drużynę",placeholder="np. Arsenal",key=f"wild_{tid}_{current['player_id']}")
        ok=st.form_submit_button("✅ WYBIERAM",type="primary",use_container_width=True)
    if ok:
        try:
            finished=db.draft_pick(tid,current["player_id"],slot,wildcard)
            if finished:rr()
            rf()
        except ValueError as e:st.error(str(e))


def render_team_draft(t):
    hero(f"Etap 2/3 • draft drużyn • {t['player_count']} graczy")
    team_draft(t["id"]);reset_controls(t,"team_draft")


@st.fragment
def team_draw(tid:str):
    bundle=db.bundle(tid);players=bundle["players"];pool=bundle["meta"]["team_pool"]
    hidden=[p for p in players if not p["team_revealed"]];last=st.session_state.get("last_spin")
    done=len(players)-len(hidden);st.progress(done/len(players),text=f"Wylosowano {done}/{len(players)} drużyn")
    if last:
        render_wheel(last["team"],last["name"],tid,pool)
        if st.button("➡️ LOSUJEMY DALEJ",type="primary",use_container_width=True,key=f"next_{tid}_{done}"):
            st.session_state.pop("last_spin",None)
            if not hidden:db.start_structure_draw(tid);rr()
            rf()
        return
    if hidden:
        nxt=sorted(hidden,key=lambda x:x["team_reveal_order"])[0];st.subheader(f"🎡 Następny: {nxt['name']}")
        if st.button("🎰 ZAKRĘĆ KOŁEM",type="primary",use_container_width=True,key=f"spin_{nxt['player_id']}"):
            st.session_state.last_spin=db.reveal_next_team(tid);rf()
    else:
        if st.button("🎲 PRZEJDŹ DO KOLEJNEGO LOSOWANIA",type="primary",use_container_width=True,key=f"struct_{tid}"):
            db.start_structure_draw(tid);rr()


def render_team_draw(t):
    hero(f"Etap 1/2 • losowanie drużyn • {t['player_count']} graczy")
    team_draw(t["id"]);reset_controls(t,"draw")


@st.fragment
def structure_draw(tid:str):
    b=db.bundle(tid);m=b["meta"]
    if not int(m["draw_revealed"]):
        if st.button("🎱 LOSUJ",type="primary",use_container_width=True,key=f"reveal_struct_{tid}"):
            db.reveal_structure(tid);rf()
        return
    name_map={p["player_id"]:p["name"] for p in b["players"]}
    render_structure_draw(m["format_key"],m["draw"],int(m["redraw_count"]),name_map=name_map)
    c1,c2=st.columns(2)
    with c1:
        if st.button("🏁 ZACZYNAMY TURNIEJ",type="primary",use_container_width=True,key=f"accept_{tid}"):
            db.confirm_structure(tid);rr()
    with c2:
        if st.button("💸 ZAPŁAĆ I WYLOSUJ PONOWNIE — PODGRZANE KULKI",use_container_width=True,key=f"reroll_{tid}_{m['redraw_count']}"):
            db.reroll_structure(tid);rf()


def render_structure(t):
    title={"league4_final":"losowanie ustawienia ligi","double5":"losowanie drabinki","league5_final":"losowanie ustawienia ligi","groups6":"losowanie grup","groups6_full":"losowanie grup","double7":"losowanie drabinki","groups7":"losowanie grup","groups7_sf":"losowanie grup"}[t["format_key"]]
    step="Etap 3/3" if int(t["player_count"]) in (4,5) else "Etap 2/2"
    hero(f"{step} • {title}");structure_draw(t["id"]);reset_controls(t,"structure")


def stage_name(m):
    s=m["stage"]
    if s=="GROUP":return f"GRUPA {m['group_name']}"
    return {"LEAGUE":"LIGA","WB":"DRABINKA WYGRANYCH","WB_FINAL":"FINAŁ WINNERS","LB":"DRABINKA PRZEGRANYCH","LB_FINAL":"FINAŁ LOSERS","QF":"ĆWIERĆFINAŁ","SF":"PÓŁFINAŁ","FINAL":"FINAŁ","RESET_FINAL":"RESET FINAL"}.get(s,s)

def max_matches(fmt):return {"league4_final":7,"double5":9,"league5_final":11,"groups6":9,"groups6_full":11,"double7":13,"groups7":14,"groups7_sf":12}[fmt]

def source_placeholder(fmt,no):
    maps={
      "league4_final":{7:"1. miejsce ligi — 2. miejsce ligi"},
      "double5":{3:"Wolny los — wylosowany zwycięzca M1/M2",4:"Przegrany M1 — Przegrany M2",5:"Drugi zwycięzca M1/M2 — Zwycięzca M3",6:"Zwycięzca M4 — Przegrany M3",7:"Zwycięzca M6 — Przegrany M5",8:"Mistrz winners — Mistrz losers",9:"Reset finału (jeśli potrzebny)"},
      "league5_final":{11:"1. miejsce ligi — 2. miejsce ligi"},
      "groups6":{7:"1A — 2B / 1B — 2A",8:"Drugi półfinał",9:"Zwycięzca SF1 — Zwycięzca SF2"},
      "groups6_full":{7:"2A — 3B / 2B — 3A",8:"Drugi ćwierćfinał",9:"Zwycięzca grupy — Zwycięzca QF",10:"Zwycięzca grupy — Zwycięzca QF",11:"Zwycięzca SF1 — Zwycięzca SF2"},
      "double7":{4:"W1 — W2",5:"W3 — Wolny los",6:"Dwóch przegranych bez BYE",7:"Wylosowany BYE LB — przegrany półfinału WB",8:"Zwycięzca M6 — drugi przegrany półfinału WB",9:"Finał winners",10:"Drabinka przegranych",11:"Finał losers",12:"Mistrz winners — Mistrz losers",13:"Reset finału (jeśli potrzebny)"},
      "groups7":{10:"2A — 3B / 2B — 3A",11:"Drugi ćwierćfinał",12:"Zwycięzca grupy — Zwycięzca QF",13:"Zwycięzca grupy — Zwycięzca QF",14:"Zwycięzca SF1 — Zwycięzca SF2"},
      "groups7_sf":{10:"1A — 2B / 1B — 2A",11:"Drugi półfinał",12:"Zwycięzca SF1 — Zwycięzca SF2"},
    }
    return maps.get(fmt,{}).get(no,"Do ustalenia")


def score_form(tid,m):
    no=int(m["match_no"]);pending=st.session_state.get("pending_ko")
    if pending and pending.get("tid")==tid and pending.get("no")==no:
        st.markdown("### ⚽ Karne")
        with st.form(f"pens_{tid}_{no}"):
            c1,c2=st.columns(2)
            with c1:hp=st.number_input(m["home_name"],0,30,4,1,key=f"hp_{tid}_{no}")
            with c2:ap=st.number_input(m["away_name"],0,30,3,1,key=f"ap_{tid}_{no}")
            ok=st.form_submit_button("✅ ZATWIERDŹ KARNE",type="primary",use_container_width=True)
        if ok:
            if hp==ap:st.error("Karne muszą wskazać zwycięzcę.")
            else:db.save_result(tid,no,pending["hs"],pending["as"],int(hp),int(ap));st.session_state.pop("pending_ko",None);rf()
        if st.button("↩️ Zmień wynik przed karnymi",use_container_width=True,key=f"change_{tid}_{no}"):st.session_state.pop("pending_ko",None);rf()
        return
    with st.form(f"score_{tid}_{no}"):
        c1,mid,c2=st.columns([1,.18,1])
        with c1:hs=st.number_input(m["home_name"],0,99,0,1,key=f"hs_{tid}_{no}")
        with mid:st.markdown("<div class='score-separator'>:</div>",unsafe_allow_html=True)
        with c2:ass=st.number_input(m["away_name"],0,99,0,1,key=f"as_{tid}_{no}")
        ok=st.form_submit_button("✅ ZATWIERDŹ WYNIK",type="primary",use_container_width=True)
    if ok:
        ko=m["stage"] not in ("GROUP","LEAGUE")
        if ko and int(hs)==int(ass):st.session_state.pending_ko={"tid":tid,"no":no,"hs":int(hs),"as":int(ass)};rf()
        else:db.save_result(tid,no,int(hs),int(ass));rf()


def render_special_event(tid:str, b:dict) -> bool:
    fmt=b["meta"]["format_key"]
    if fmt=="double5":
        state=db.double5_draw_state(tid)
        if state and not state.get("ack"):
            st.markdown("### 🎱 Losowanie przeciwnika dla wolnego losu")
            if not state.get("selected"):
                names=" • ".join(c["name"] for c in state.get("candidates",[]))
                st.markdown(f"**{esc(state['player_name'])}** czeka. W puli: **{esc(names)}**")
                if st.button("🎰 LOSUJ PRZECIWNIKA",type="primary",use_container_width=True,key=f"d5_mid_{tid}"):
                    db.reveal_double5_opponent(tid);rf()
            else:
                render_double5_mid_draw(state["player_name"],state.get("candidates",[]),state["selected"])
                if st.button("➡️ GRAMY DALEJ",type="primary",use_container_width=True,key=f"d5_mid_ack_{tid}"):
                    db.ack_double5_draw(tid);rf()
            return True
    if fmt=="double7":
        state=db.double7_lb_draw_state(tid)
        if state and not state.get("ack"):
            st.markdown("### 💀 Losowanie pierwszego BYE w Losers Bracket")
            if not state.get("selected"):
                if st.button("🎱 LOSUJ SZCZĘŚCIE W NIESZCZĘŚCIU",type="primary",use_container_width=True,key=f"d7_lb_{tid}"):
                    db.reveal_double7_lb_bye(tid);rf()
            else:
                render_double7_lb_bye(state.get("candidates",[]),state["selected"])
                if st.button("➡️ DRABINKA GOTOWA",type="primary",use_container_width=True,key=f"d7_lb_ack_{tid}"):
                    db.ack_double7_lb_draw(tid);rf()
            return True
    if fmt in ("groups6","groups6_full","groups7","groups7_sf"):
        state=db.group_playoff_reveal_state(tid)
        if state:
            render_playoff_reveal(fmt,state.get("pairs",[]),state.get("direct",[]))
            if st.button("🔥 ZACZYNAMY FAZĘ PUCHAROWĄ",type="primary",use_container_width=True,key=f"po_ack_{tid}"):
                db.ack_group_playoffs(tid);rf()
            return True
    return False


@st.fragment
def live(tid:str):
    b=db.bundle(tid);t=b["tournament"];meta=b["meta"]
    if t["status"]=="completed":
        champ=next((p["name"] for p in b["players"] if p["player_id"]==t["champion_player_id"]),"Mistrz")
        st.markdown(f'<div class="winner"><div class="match-no">MISTRZ TURNIEJU</div><div style="font-size:3rem">🏆</div><div class="player-big">{esc(champ)}</div></div>',unsafe_allow_html=True)
        if st.session_state.get("celebrated")!=tid:st.balloons();st.session_state.celebrated=tid
        if t["is_test"]:st.info("Turniej testowy — nie liczy się do statystyk wszech czasów.")
        if st.button("➕ NOWY TURNIEJ",type="primary",use_container_width=True,key=f"new_{tid}"):db.start_new();rr()
        return
    if render_special_event(tid,b): return
    b=db.bundle(tid)
    cur=db.current_match_from(b["matches"])
    if not cur:st.info("Czekam na rozstrzygnięcie poprzedniego etapu…");return
    total=max_matches(meta["format_key"]);suffix="" if cur["stage"]!="RESET_FINAL" else " • JEŚLI POTRZEBNY"
    st.markdown(f'<div class="match-no">MECZ {cur["match_no"]}/{total} • {stage_name(cur)}{suffix}</div>',unsafe_allow_html=True)
    st.markdown(f'<div class="match-card"><div style="display:flex;justify-content:space-between;gap:16px;align-items:center;text-align:center"><div style="flex:1"><div class="player-big">{esc(cur["home_name"])}</div><div class="team-small">{esc(cur["home_team"])}</div></div><div style="font-size:1.5rem;font-weight:900;color:#94a3b8">VS</div><div style="flex:1"><div class="player-big">{esc(cur["away_name"])}</div><div class="team-small">{esc(cur["away_team"])}</div></div></div></div>',unsafe_allow_html=True)
    score_form(tid,cur)
    nxt=[m for m in b["matches"] if int(m["match_no"])>int(cur["match_no"]) and m.get("home_player_id") and m.get("home_score") is None]
    if nxt:st.caption(f"Następny: **{nxt[0]['home_name']} vs {nxt[0]['away_name']}**")
    if st.button("↩️ Cofnij ostatni wynik",use_container_width=True,key=f"undo_{tid}_{cur['match_no']}"):
        st.session_state.pop("pending_ko",None);db.undo_last_result(tid);rf()
    tables=db.standings(tid)
    if tables:
        st.divider()
        if "L" in tables:st.subheader("Tabela ligowa");st.dataframe(standings_df(tables["L"]),hide_index=True,use_container_width=True)
        else:
            c1,c2=st.columns(2)
            with c1:st.subheader("Grupa A");st.dataframe(standings_df(tables["A"]),hide_index=True,use_container_width=True)
            with c2:st.subheader("Grupa B");st.dataframe(standings_df(tables["B"]),hide_index=True,use_container_width=True)


def render_schedule(t):
    b=db.bundle(t["id"]);fmt=b["meta"]["format_key"];st.subheader("📅 Terminarz")
    for m in b["matches"]:
        if m.get("home_player_id"):
            names=f"{esc(m['home_name'])} — {esc(m['away_name'])}";result=result_text(m);icon="✅" if m.get("home_score") is not None else "▶️"
        else:names=source_placeholder(fmt,int(m["match_no"]));result="—";icon="🔒"
        optional=" • opcjonalny" if m["stage"]=="RESET_FINAL" else ""
        st.markdown(f'<div class="mini-card"><span class="match-no">{icon} MECZ {m["match_no"]} • {stage_name(m)}{optional}</span><br><b>{names}</b><span style="float:right" class="scoreline">{esc(result)}</span></div>',unsafe_allow_html=True)


def render_stats(t):
    st.subheader("📊 Statystyki wszech czasów")
    st.caption("Wszystkie zakończone turnieje nietestowe zapisane w bazie.")
    stats=db.all_time_stats()
    if not stats:st.info("Brak zakończonych turniejów nietestowych.")
    else:
        leader=stats[0];c1,c2,c3,c4=st.columns(4);c1.metric("🐐 Lider",leader["name"]);c2.metric("🏆 Tytuły",leader["titles"]);tg=max(stats,key=lambda x:x["gf"]);c3.metric("⚽ Król bramek",tg["name"],f"{tg['gf']} goli");tw=max(stats,key=lambda x:x["w"]);c4.metric("🔥 Najwięcej wygranych",tw["name"],f"{tw['w']} W")
        df=pd.DataFrame([{"#":i+1,"Gracz":s["name"],"Turnieje":s["tournaments"],"🏆":s["titles"],"Finały":s["finals"],"M":s["matches"],"W":s["w"],"R":s["d"],"P":s["l"],"Bramki":f'{s["gf"]}:{s["ga"]}',"+/-":s["gd"],"W%":s["win_pct"],"Karne W":s["pen_wins"]} for i,s in enumerate(stats)]);st.dataframe(df,hide_index=True,use_container_width=True)


def reset_controls(t,loc):
    if t.get("status")=="completed": return
    st.divider()
    with st.expander("🔄 Reset bieżącego turnieju"):
        with st.form(f"reset_{loc}_{t['id']}"):
            yes=st.checkbox("Tak, usuń bieżący turniej");go=st.form_submit_button("Usuń i zacznij od nowa",use_container_width=True)
        if go:
            if not yes:st.error("Najpierw zaznacz potwierdzenie.")
            else:db.reset_current(t["id"]);st.session_state.pop("last_spin",None);rr()


def render_live(t):
    hero(f"{t['player_count']} graczy • {FORMAT_LABELS[t['format_key']]}")
    st.markdown(f'<span class="status-chip">{"🧪 TEST" if t["is_test"] else "🏆 PRODUKCYJNY"}</span>',unsafe_allow_html=True)
    opts=["🏠 Ekran główny","📅 Terminarz","📊 Statystyki"];view=st.segmented_control("Widok",opts,default=opts[0],key="view",label_visibility="collapsed") or opts[0]
    if view==opts[0]:live(t["id"]);reset_controls(t,"live")
    elif view==opts[1]:render_schedule(t)
    else:render_stats(t)


t=db.current_tournament()
if not t:render_start()
elif t["phase"]=="draft_order":render_draft_order_stage(t)
elif t["phase"]=="team_draft":render_team_draft(t)
elif t["phase"]=="team_draw":render_team_draw(t)
elif t["phase"]=="structure_draw":render_structure(t)
else:render_live(t)

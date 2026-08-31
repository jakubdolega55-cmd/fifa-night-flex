from __future__ import annotations

import html
import os
import pandas as pd
import streamlit as st

from database import Database
from logic import BASE_TEAMS, SEVEN_TEAMS, EIGHT_TEAMS, FORMAT_LABELS, FORMAT_MATCH_COUNTS
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

@st.cache_data(ttl=30,show_spinner=False)
def official_player_names_cached():
    return db.official_player_names()

@st.cache_data(ttl=30,show_spinner=False)
def wildcard_team_suggestions_cached():
    return db.wildcard_team_suggestions()

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
    if count==7:return st.session_state.get("format7","double7")
    return st.session_state.get("format8","groups8_sf")

def start_defaults(count:int, official_names:list[str]):
    key=f"_lineup_init_{count}"
    if st.session_state.get(key):return
    vals=db.last_lineup(count)
    canonical={n.casefold():n for n in official_names}
    for i in range(count):
        field_key=f"p_{count}_{i}"
        remembered=vals[i] if i<len(vals) else ""
        # Automatycznie przywracamy tylko zweryfikowane nicki z oficjalnych statystyk.
        # Nazwę spoza statystyk nadal można normalnie wpisać jako nową.
        matched=canonical.get(remembered.casefold()) if remembered else None
        if matched: st.session_state[field_key]=matched
        else: st.session_state.pop(field_key,None)
    st.session_state[key]=True


def render_start():
    hero("Wybierz liczbę graczy i format turnieju.")
    if not db.is_postgres:st.warning("Tryb lokalny SQLite. Na Streamlit Cloud podłącz DATABASE_URL z Neon.")
    default=db.last_player_count() if "player_count" not in st.session_state else st.session_state.player_count
    if default not in (4,5,6,7,8):default=6
    count=st.segmented_control("Liczba graczy",[4,5,6,7,8],default=default,key="player_count") or default
    official_names=official_player_names_cached()
    start_defaults(count,official_names)
    if count==5:
        st.session_state.format5=st.radio("Format dla 5 graczy",["double5","league5_final"],format_func=format_option,horizontal=False,key="format5_radio")
    elif count==6:
        st.session_state.format6=st.radio("Format dla 6 graczy",["groups6","groups6_full"],format_func=format_option,horizontal=False,key="format6_radio")
    elif count==7:
        st.session_state.format7=st.radio("Format dla 7 graczy",["double7","groups7","groups7_sf"],format_func=format_option,horizontal=False,key="format7_radio")
    elif count==8:
        st.session_state.format8=st.radio("Format dla 8 graczy",["groups8_sf","double8","groups8_barrage"],format_func=format_option,horizontal=False,key="format8_radio")
    fmt=format_for(count)
    st.markdown(f"**Format:** {FORMAT_LABELS[fmt]}  \n**Łącznie:** {FORMAT_MATCH_COUNTS[fmt]}")
    with st.form(f"create_{count}_{fmt}"):
        st.caption("Nicki z oficjalnych statystyk są podpowiadane podczas wpisywania. Możesz też wpisać nowego gracza.")
        cols=st.columns(2); names=[]
        for i in range(count):
            with cols[i%2]:
                names.append(st.selectbox(
                    f"Gracz {i+1}",
                    options=official_names,
                    index=None,
                    key=f"p_{count}_{i}",
                    placeholder="Wpisz nick lub wybierz z listy",
                    accept_new_options=True,
                ))
        if count in (4,5):
            teams=BASE_TEAMS.copy()
            st.markdown("**Draft drużyn:** najpierw losujemy kolejność wyboru, potem każdy wybiera z pozostałej puli.")
            st.caption("Bayern • Barcelona • PSG • Liverpool • Man City • Wild Card (Real Madryt banned)")
        elif count==6:
            teams=BASE_TEAMS.copy(); st.caption("Pula drużyn: Bayern, Barcelona, PSG, Liverpool, Man City + dzika karta (Real banned).")
        elif count==7:
            teams=SEVEN_TEAMS.copy(); st.caption("Pula drużyn: 5 klubów + 2 dzikie karty. Real Madryt banned.")
        else:
            teams=EIGHT_TEAMS.copy(); st.caption("Pula drużyn: 5 klubów + 3 dzikie karty. Real Madryt banned.")
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
        wildcard=st.selectbox("Wild Card — wpisz lub wybierz drużynę",options=wildcard_team_suggestions_cached(),index=None,
                              placeholder="np. Arsenal",accept_new_options=True,key=f"wild_{tid}_{current['player_id']}")
        ok=st.form_submit_button("✅ WYBIERAM",type="primary",use_container_width=True)
    if ok:
        try:
            finished=db.draft_pick(tid,current["player_id"],slot,wildcard)
            wildcard_team_suggestions_cached.clear()
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
    pending=db.pending_wildcard(tid)
    done=len(players)-len(hidden);st.progress(done/len(players),text=f"Wylosowano {done}/{len(players)} drużyn")
    if pending:
        render_wheel(pending["team"],pending["name"],tid,pool)
        st.markdown(f"### 🃏 Wild Card — {esc(pending['name'])}")
        with st.form(f"wildcard_draw_{tid}_{pending['player_id']}"):
            choice=st.selectbox("Wpisz lub wybierz drużynę",options=wildcard_team_suggestions_cached(),index=None,
                                placeholder="np. Arsenal",accept_new_options=True,key=f"wheel_wc_{tid}_{pending['player_id']}")
            ok=st.form_submit_button("✅ ZATWIERDŹ DRUŻYNĘ",type="primary",use_container_width=True)
        if ok:
            try:
                wheel_team=pending["team"]
                team=db.confirm_wildcard_team(tid,pending["player_id"],choice)
                st.session_state.last_spin={"player_id":pending["player_id"],"name":pending["name"],"team":team,"wheel_team":wheel_team}
                wildcard_team_suggestions_cached.clear();rf()
            except ValueError as e:st.error(str(e))
        return
    if last:
        render_wheel(last.get("wheel_team",last["team"]),last["name"],tid,pool,display_result=last["team"])
        bundle=db.bundle(tid);hidden=[p for p in bundle["players"] if not p["team_revealed"]]
        if hidden:
            nxt=sorted(hidden,key=lambda x:x["team_reveal_order"])[0]
            if st.button(f"🎰 ZAKRĘĆ DLA {nxt['name']}",type="primary",use_container_width=True,key=f"next_spin_{tid}_{done}"):
                st.session_state.pop("last_spin",None)
                result=db.reveal_next_team(tid)
                if result and not result.get("wildcard"):st.session_state.last_spin=result
                rf()
        else:
            if st.button("🎲 PRZEJDŹ DO KOLEJNEGO LOSOWANIA",type="primary",use_container_width=True,key=f"next_stage_{tid}_{done}"):
                st.session_state.pop("last_spin",None);db.start_structure_draw(tid);rr()
        return
    if hidden:
        nxt=sorted(hidden,key=lambda x:x["team_reveal_order"])[0];st.subheader(f"🎡 Następny: {nxt['name']}")
        if st.button("🎰 ZAKRĘĆ KOŁEM",type="primary",use_container_width=True,key=f"spin_{nxt['player_id']}"):
            result=db.reveal_next_team(tid)
            if result and not result.get("wildcard"):st.session_state.last_spin=result
            rf()
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
    title={"league4_final":"losowanie ustawienia ligi","double5":"losowanie drabinki","league5_final":"losowanie ustawienia ligi","groups6":"losowanie grup","groups6_full":"losowanie grup","double7":"losowanie drabinki","groups7":"losowanie grup","groups7_sf":"losowanie grup","groups8_sf":"losowanie grup","double8":"losowanie drabinki","groups8_barrage":"losowanie grup"}[t["format_key"]]
    step="Etap 3/3" if int(t["player_count"]) in (4,5) else "Etap 2/2"
    hero(f"{step} • {title}");structure_draw(t["id"]);reset_controls(t,"structure")


def stage_name(m):
    s=m["stage"]
    if s=="GROUP":return f"GRUPA {m['group_name']}"
    return {"LEAGUE":"LIGA","WB":"DRABINKA WYGRANYCH","WB_FINAL":"FINAŁ WINNERS","LB":"DRABINKA PRZEGRANYCH","LB_FINAL":"FINAŁ LOSERS","QF":"ĆWIERĆFINAŁ","BARRAGE":"BARAŻ","SF":"PÓŁFINAŁ","FINAL":"FINAŁ","RESET_FINAL":"RESET FINAL"}.get(s,s)

def max_matches(fmt):return {"league4_final":7,"double5":8,"league5_final":11,"groups6":9,"groups6_full":11,"double7":12,"groups7":14,"groups7_sf":12,"groups8_sf":15,"double8":14,"groups8_barrage":17}[fmt]

def source_placeholder(fmt,no):
    maps={
      "league4_final":{7:"1. miejsce ligi — 2. miejsce ligi"},
      "double5":{3:"Wolny los — wylosowany zwycięzca M1/M2",4:"Przegrany M1 — Przegrany M2",5:"Drugi zwycięzca M1/M2 — Zwycięzca M3",6:"Zwycięzca M4 — Przegrany M3",7:"Zwycięzca M6 — Przegrany M5",8:"Mistrz winners (start 1:0) — Mistrz losers"},
      "league5_final":{11:"1. miejsce ligi — 2. miejsce ligi"},
      "groups6":{7:"1A — 2B / 1B — 2A",8:"Drugi półfinał",9:"Zwycięzca SF1 — Zwycięzca SF2"},
      "groups6_full":{7:"2A — 3B / 2B — 3A",8:"Drugi ćwierćfinał",9:"Zwycięzca grupy — Zwycięzca QF",10:"Zwycięzca grupy — Zwycięzca QF",11:"Zwycięzca SF1 — Zwycięzca SF2"},
      "double7":{4:"W1 — W2",5:"W3 — Wolny los",6:"Dwóch przegranych bez BYE",7:"Wylosowany BYE LB — przegrany półfinału WB",8:"Zwycięzca M6 — drugi przegrany półfinału WB",9:"Finał winners",10:"Drabinka przegranych",11:"Finał losers",12:"Mistrz winners (start 1:0) — Mistrz losers"},
      "groups7":{10:"2A — 3B / 2B — 3A",11:"Drugi ćwierćfinał",12:"Zwycięzca grupy — Zwycięzca QF",13:"Zwycięzca grupy — Zwycięzca QF",14:"Zwycięzca SF1 — Zwycięzca SF2"},
      "groups7_sf":{10:"1A — 2B / 1B — 2A",11:"Drugi półfinał",12:"Zwycięzca SF1 — Zwycięzca SF2"},
      "groups8_sf":{13:"1A — 2B / 1B — 2A",14:"Drugi półfinał",15:"Zwycięzca SF1 — Zwycięzca SF2"},
      "double8":{5:"W1 — W2",6:"W3 — W4",7:"L1 — L2",8:"L3 — L4",9:"Zwycięzca LB M7 — przegrany WB M6",10:"Zwycięzca LB M8 — przegrany WB M5",11:"Finał winners",12:"Zwycięzcy M9 — M10",13:"Finał losers",14:"Mistrz winners (start 1:0) — Mistrz losers"},
      "groups8_barrage":{13:"2B — 3A / 2A — 3B",14:"Drugi baraż",15:"Zwycięzca grupy — Zwycięzca barażu",16:"Zwycięzca grupy — Zwycięzca barażu",17:"Zwycięzca SF1 — Zwycięzca SF2"},
    }
    return maps.get(fmt,{}).get(no,"Do ustalenia")


def _scorer_side_form(tid,m,side,team_name,player_name):
    options=db.team_scorer_options(team_name)
    st.markdown(f"**⚽ {esc(team_name)} — strzelcy**")
    st.caption("Klikaj +/–. Nic nie zapisuje się ani nie odświeża do zatwierdzenia wyniku.")
    items=[]
    top=options[:5]; rest=options[5:]
    for i,row in enumerate(top):
        goals=st.number_input(row["name"],0,20,0,1,key=f"sc_{tid}_{m['match_no']}_{side}_{i}_{row['name']}")
        items.append({"name":row["name"],"goals":int(goals)})
    if rest:
        with st.expander(f"Pozostali zawodnicy ({len(rest)})"):
            for j,row in enumerate(rest,5):
                goals=st.number_input(row["name"],0,20,0,1,key=f"sc_{tid}_{m['match_no']}_{side}_{j}_{row['name']}")
                items.append({"name":row["name"],"goals":int(goals)})
    known=[r["name"] for r in options]
    st.markdown("**➕ Inny zawodnik**")
    for k in range(2):
        c1,c2=st.columns([2,1])
        with c1:
            name=st.selectbox(f"Inny strzelec {k+1}",options=known,index=None,accept_new_options=True,
                              placeholder="Wpisz nazwisko",key=f"sc_other_name_{tid}_{m['match_no']}_{side}_{k}")
        with c2:
            goals=st.number_input("Gole",0,20,0,1,key=f"sc_other_goals_{tid}_{m['match_no']}_{side}_{k}")
        if name and int(goals)>0:items.append({"name":name,"goals":int(goals)})
    # merge duplicates from top + custom picker
    merged={}
    for item in items:
        n=" ".join(str(item.get("name") or "").strip().split());g=int(item.get("goals") or 0)
        if n and g>0:merged[n.casefold()]={"name":n,"goals":merged.get(n.casefold(),{}).get("goals",0)+g}
    return {"team":team_name,"items":list(merged.values())}


def render_match_context(m):
    ctx=db.match_context(m["home_player_id"],m["away_player_id"])
    tags=[]
    if ctx.get("rivalry"):tags.append("🔥 RIVALRY")
    if ctx.get("derby"):tags.append("⚔️ DERBY")
    if tags:st.markdown("**"+" · ".join(tags)+"**")
    hf=" ".join(ctx.get("home_form") or []) or "—"; af=" ".join(ctx.get("away_form") or []) or "—"
    st.caption(f"H2H: {m['home_name']} {ctx['home_wins']}–{ctx['away_wins']} {m['away_name']} • remisy {ctx['draws']} • mecze {ctx['meetings']}")
    st.caption(f"Forma (ostatnie 5): {m['home_name']} {hf} | {m['away_name']} {af}")
    last=ctx.get("last")
    if last:st.caption(f"Ostatnio: {last.get('home_name')} {last.get('home_score')}:{last.get('away_score')} {last.get('away_name')}")


def score_form(tid,m,fmt):
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
            else:
                try:
                    db.save_result(tid,no,pending["hs"],pending["as"],int(hp),int(ap),pending.get("scorers"));st.session_state.pop("pending_ko",None);rf()
                except ValueError as e:st.error(str(e))
        if st.button("↩️ Zmień wynik przed karnymi",use_container_width=True,key=f"change_{tid}_{no}"):st.session_state.pop("pending_ko",None);rf()
        return
    wb_bonus = fmt in ("double5","double7","double8") and m.get("stage")=="FINAL"
    start_home = 1 if wb_bonus else 0
    if wb_bonus and st.session_state.get(f"hs_{tid}_{no}",1) < 1:
        st.session_state[f"hs_{tid}_{no}"] = 1
    with st.form(f"score_{tid}_{no}"):
        c1,mid,c2=st.columns([1,.18,1])
        with c1:hs=st.number_input(m["home_name"],min_value=start_home,max_value=99,value=start_home,step=1,key=f"hs_{tid}_{no}")
        with mid:st.markdown("<div class='score-separator'>:</div>",unsafe_allow_html=True)
        with c2:ass=st.number_input(m["away_name"],min_value=0,max_value=99,value=0,step=1,key=f"as_{tid}_{no}")
        st.divider()
        home_sc=_scorer_side_form(tid,m,"home",m["home_team"],m["home_name"])
        st.divider()
        away_sc=_scorer_side_form(tid,m,"away",m["away_team"],m["away_name"])
        if wb_bonus:
            st.caption("Bonusowe 1:0 z Winners Bracket nie ma strzelca — nie dodawaj go do listy strzelców.")
        st.caption("Strzelcy są opcjonalni i nie muszą sumować się do wyniku — możesz wpisać tylko znane gole, a samobóje lub nieuzupełnione bramki zostawić bez przypisania.")
        ok=st.form_submit_button("✅ ZATWIERDŹ WYNIK",type="primary",use_container_width=True)
    if ok:
        scorers={"home":home_sc,"away":away_sc}
        ko=m["stage"] not in ("GROUP","LEAGUE")
        if ko and int(hs)==int(ass):st.session_state.pending_ko={"tid":tid,"no":no,"hs":int(hs),"as":int(ass),"scorers":scorers};rf()
        else:
            try:db.save_result(tid,no,int(hs),int(ass),scorers=scorers);rf()
            except ValueError as e:st.error(str(e))


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
    if fmt in ("groups6","groups6_full","groups7","groups7_sf","groups8_sf","groups8_barrage"):
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
        summary=db.tournament_summary(tid);champ=summary.get("champion") or "Mistrz"
        st.markdown(f'<div class="winner"><div class="match-no">MISTRZ TURNIEJU</div><div style="font-size:3rem">🏆</div><div class="player-big">{esc(champ)}</div></div>',unsafe_allow_html=True)
        if st.session_state.get("celebrated")!=tid:st.balloons();st.session_state.celebrated=tid
        st.markdown("### 📋 Podsumowanie turnieju")
        c1,c2,c3,c4=st.columns(4)
        c1.metric("🥈 Finalista",summary.get("runner_up") or "—")
        c2.metric("⚽ Najwięcej goli",summary.get("top_goals",{}).get("name") or "—",summary.get("top_goals",{}).get("value",0))
        c3.metric("🛡️ Najlepsza defensywa",summary.get("best_defense",{}).get("name") or "—",f"{summary.get('best_defense',{}).get('value',0)} straconych")
        c4.metric("🔥 Najwięcej wygranych",summary.get("best_form",{}).get("name") or "—",summary.get("best_form",{}).get("wins",0))
        c1,c2=st.columns(2)
        if summary.get("biggest"):c1.info(f"💥 Największe zwycięstwo: **{summary['biggest']['home']} {summary['biggest']['score']} {summary['biggest']['away']}**")
        if summary.get("highest"):c2.info(f"🎯 Najbardziej bramkowy mecz: **{summary['highest']['home']} {summary['highest']['score']} {summary['highest']['away']}**")
        mot=summary.get("match_of_tournament")
        if mot:
            mot_score=mot["score"]
            if mot.get("home_penalties") is not None and mot.get("away_penalties") is not None:mot_score+=f" (k. {mot['home_penalties']}:{mot['away_penalties']})"
            st.warning(f"🎬 **Mecz turnieju:** {mot['home']} {mot_score} {mot['away']} • {stage_name({'stage':mot.get('stage'),'group_name':mot.get('group_name') or ''})}")
        if summary.get("real_top_scorer"):st.success(f"🥇 Strzelec turnieju: **{summary['real_top_scorer']['name']} — {summary['real_top_scorer']['goals']} goli**")
        if summary.get("rivalry_match"):st.info(f"🔥 Rivalry match turnieju: **{summary['rivalry_match']['home']} {summary['rivalry_match']['score']} {summary['rivalry_match']['away']}**")
        if summary.get("new_records"):
            st.markdown("#### 🆕 Nowe rekordy")
            for r in summary["new_records"]:st.success(r)
        if t["is_test"]:st.info("Turniej testowy — nie liczy się do statystyk wszech czasów.")
        if st.button("➕ NOWY TURNIEJ",type="primary",use_container_width=True,key=f"new_{tid}"):db.start_new();rr()
        return
    if render_special_event(tid,b): return
    b=db.bundle(tid)
    cur=db.current_match_from(b["matches"])
    if not cur:st.info("Czekam na rozstrzygnięcie poprzedniego etapu…");return
    total=max_matches(meta["format_key"])
    st.markdown(f'<div class="match-no">MECZ {cur["match_no"]}/{total} • {stage_name(cur)}</div>',unsafe_allow_html=True)
    if meta["format_key"] in ("double5","double7","double8") and cur.get("stage")=="FINAL":
        st.markdown(f"<div class='winner' style='padding:18px;margin:10px 0 16px'><div class='match-no'>🏆 BONUS WINNERS BRACKET</div><div class='player-big' style='font-size:2rem'>{esc(cur['home_name'])} zaczyna finał 1:0</div><div class='team-small'>Jeden finał. Bez resetu. Bonusowy gol nie ma strzelca.</div></div>",unsafe_allow_html=True)
    st.markdown(f'<div class="match-card"><div style="display:flex;justify-content:space-between;gap:16px;align-items:center;text-align:center"><div style="flex:1"><div class="player-big">{esc(cur["home_name"])}</div><div class="team-small">{esc(cur["home_team"])}</div></div><div style="font-size:1.5rem;font-weight:900;color:#94a3b8">VS</div><div style="flex:1"><div class="player-big">{esc(cur["away_name"])}</div><div class="team-small">{esc(cur["away_team"])}</div></div></div></div>',unsafe_allow_html=True)
    render_match_context(cur)
    score_form(tid,cur,meta["format_key"])
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
        bonus = " • START 1:0 DLA WINNERS" if fmt in ("double5","double7","double8") and m["stage"]=="FINAL" else ""
        st.markdown(f'<div class="mini-card"><span class="match-no">{icon} MECZ {m["match_no"]} • {stage_name(m)}{bonus}</span><br><b>{names}</b><span style="float:right" class="scoreline">{esc(result)}</span></div>',unsafe_allow_html=True)


def render_stats(t):
    st.subheader("📊 Statystyki wszech czasów")
    st.caption("Wszystkie zakończone turnieje nietestowe zapisane w bazie.")
    stats=db.all_time_stats()
    if not stats:st.info("Brak zakończonych turniejów nietestowych.");return
    tab1,tab2,tab3,tab4,tab5,tab6=st.tabs(["🏆 Ranking","⚔️ H2H","🏛️ Rekordy","👥 Drużyny","👤 Gracze","⚽ Strzelcy"])
    with tab1:
        leader=stats[0];c1,c2,c3,c4=st.columns(4);c1.metric("🐐 Lider",leader["name"]);c2.metric("🏆 Tytuły",leader["titles"]);tg=max(stats,key=lambda x:x["gf"]);c3.metric("⚽ Król bramek",tg["name"],f"{tg['gf']} goli");tw=max(stats,key=lambda x:x["w"]);c4.metric("🔥 Najwięcej wygranych",tw["name"],f"{tw['w']} W")
        df=pd.DataFrame([{"#":i+1,"Gracz":s["name"],"Turnieje":s["tournaments"],"🏆":s["titles"],"Finały":s["finals"],"M":s["matches"],"W":s["w"],"R":s["d"],"P":s["l"],"Bramki":f'{s["gf"]}:{s["ga"]}',"+/-":s["gd"],"W%":s["win_pct"],"Karne W":s["pen_wins"]} for i,s in enumerate(stats)]);st.dataframe(df,hide_index=True,use_container_width=True)
        st.markdown("#### 🔥 Aktualna forma — ostatnie 5 oficjalnych meczów")
        forms=db.recent_forms()
        if forms:
            best=forms[0];st.success(f"Najlepsza aktualna forma: **{best['name']} — {' '.join(best['form'])}**")
            st.dataframe(pd.DataFrame([{"Gracz":x["name"],"Forma":" ".join(x["form"]),"W":x["w"],"R":x["d"],"P":x["l"]} for x in forms]),hide_index=True,use_container_width=True)
    with tab2:
        st.markdown("### ⚔️ Head to head")
        opts={p["name"]:p["player_id"] for p in stats}
        names=list(opts)
        with st.form("h2h_explorer"):
            c1,c2=st.columns(2)
            with c1:a=st.selectbox("Gracz 1",names,index=0)
            with c2:b=st.selectbox("Gracz 2",names,index=1 if len(names)>1 else 0)
            go=st.form_submit_button("Pokaż H2H",use_container_width=True)
        if go:
            if a==b:st.warning("Wybierz dwóch różnych graczy.")
            else:
                h=db.h2h(opts[a],opts[b]);c1,c2,c3,c4=st.columns(4);c1.metric("Mecze",h["meetings"]);c2.metric(a,h["wins1"]);c3.metric("Remisy",h["draws"]);c4.metric(b,h["wins2"])
                st.caption(f"Bramki: {a} {h['gf1']}–{h['gf2']} {b}")
                if h["recent"]:
                    st.markdown("**Ostatnie spotkania:**")
                    for m in h["recent"]:st.write(f"{m['home']} {m['score']} {m['away']}")
    with tab3:
        r=db.all_time_records()
        if not r:st.info("Za mało danych do rekordów.")
        else:
            st.markdown("### 🏛️ Hall of Fame")
            c1,c2,c3=st.columns(3)
            c1.metric("👑 Najwięcej tytułów",r["most_titles"]["name"],r["most_titles"]["titles"])
            c2.metric("🔥 Seria zwycięstw",r["win_streak"]["name"],r["win_streak"]["value"])
            c3.metric("⚽ Gole w jednym turnieju",r["goals_one_tournament"]["name"],r["goals_one_tournament"]["value"])
            c1,c2,c3=st.columns(3)
            c1.metric("🏁 Najwięcej finałów",r["most_finals"]["name"],r["most_finals"]["finals"])
            c2.metric("🥈 Najwięcej przegranych finałów",r["most_lost_finals"]["name"],r["most_lost_finals"]["finals"]-r["most_lost_finals"]["titles"])
            c3.metric("🧱 Bez porażki",r["unbeaten_streak"]["name"],r["unbeaten_streak"]["value"])
            st.markdown("### 📚 Rekordy")
            rows=[]
            def add(name,value):rows.append({"Rekord":name,"Wynik":value})
            add("Najwięcej wygranych",f"{r['most_wins']['name']} — {r['most_wins']['w']}")
            add("Najwięcej strzelonych goli",f"{r['most_goals']['name']} — {r['most_goals']['gf']}")
            add("Najdłuższa seria bez wygranej",f"{r['winless_streak']['name']} — {r['winless_streak']['value']}")
            if r.get("best_win_pct"):
                p=r['best_win_pct'];m=p['w']+p['d']+p['l'];add("Najlepszy % zwycięstw (min. 10 M)",f"{p['name']} — {round(p['w']/m*100,1)}%")
            if r.get("best_goal_avg"):
                p=r['best_goal_avg'];m=p['w']+p['d']+p['l'];add("Najlepsza średnia goli",f"{p['name']} — {round(p['gf']/m,2)}/mecz")
            if r.get("best_defense"):
                p=r['best_defense'];m=p['w']+p['d']+p['l'];add("Najmniej straconych na mecz",f"{p['name']} — {round(p['ga']/m,2)}")
            add("Największe zwycięstwo",f"{r['biggest_win']['home']} {r['biggest_win']['score']} {r['biggest_win']['away']}")
            add("Najbardziej bramkowy mecz",f"{r['highest_scoring']['home']} {r['highest_scoring']['score']} {r['highest_scoring']['away']}")
            add("Tytuły z rzędu",f"{r['consecutive_titles']['name']} — {r['consecutive_titles']['value']}")
            if r.get("most_frequent_h2h"):p=r['most_frequent_h2h'];add("Najczęstsze H2H",f"{p['name_a']} vs {p['name_b']} — {p['n']} meczów")
            if r.get("balanced_rivalry"):p=r['balanced_rivalry'];add("Najbardziej wyrównana rywalizacja",f"{p['name_a']} {p['aw']}–{p['bw']} {p['name_b']} ({p['n']} M)")
            if r.get("h2h_dominance"):p=r['h2h_dominance'];add("Największa dominacja H2H",f"{p['name_a']} {p['aw']}–{p['bw']} {p['name_b']} ({p['n']} M)")
            st.dataframe(pd.DataFrame(rows),hide_index=True,use_container_width=True)
    with tab4:
        team_stats=db.team_stats()
        if not team_stats:st.info("Brak danych o drużynach z oficjalnych turniejów.")
        else:
            most_titles=max(team_stats,key=lambda x:(x["titles"],x["w"]))
            eligible=[x for x in team_stats if x["matches"]>=5];best_pct=max(eligible,key=lambda x:(x["win_pct"],x["w"])) if eligible else max(team_stats,key=lambda x:x["win_pct"])
            most_goals=max(team_stats,key=lambda x:x["gf"]);most_wins=max(team_stats,key=lambda x:x["w"])
            c1,c2,c3,c4=st.columns(4)
            c1.metric("🏆 Najwięcej tytułów",most_titles["team"],most_titles["titles"])
            c2.metric("📈 Najlepszy W%",best_pct["team"],f"{best_pct['win_pct']}%")
            c3.metric("⚽ Najwięcej goli",most_goals["team"],most_goals["gf"])
            c4.metric("🔥 Najwięcej wygranych",most_wins["team"],most_wins["w"])
            df=pd.DataFrame([{"Drużyna":x["team"],"Tytuły":x["titles"],"M":x["matches"],"W":x["w"],"R":x["d"],"P":x["l"],"W%":x["win_pct"],"Bramki":f"{x['gf']}:{x['ga']}","G/mecz":x["goals_per_match"],"Gracze":x["players"],"Najlepszy gracz":x["best_player"]} for x in team_stats])
            st.dataframe(df,hide_index=True,use_container_width=True)
    with tab5:
        st.markdown("### 👤 Profil i historia gracza")
        opts={p["name"]:p["player_id"] for p in stats};names=list(opts)
        selected=st.selectbox("Gracz",names,key="player_profile_select")
        profile=db.player_profile(opts[selected])
        if profile:
            c1,c2,c3,c4=st.columns(4)
            c1.metric("🏆 Tytuły",profile["titles"]);c2.metric("🏁 Finały",profile["finals"]);c3.metric("🔥 Wygrane",profile["w"],f"{profile['win_pct']}%")
            c4.metric("⚽ Bramki",profile["gf"],f"{profile['gd']:+d} bilans")
            st.caption("Forma — ostatnie 5: **"+" ".join(profile.get("form") or [])+"**" if profile.get("form") else "Brak ostatnich meczów")
            c1,c2,c3=st.columns(3)
            freq=profile.get("most_frequent");nem=profile.get("nemesis");fav=profile.get("favorite")
            c1.metric("🤝 Najczęstszy rywal",freq["name"] if freq else "—",f"{freq['meetings']} M" if freq else None)
            c2.metric("😈 Nemesis",nem["name"] if nem else "—",f"{nem['w']}W–{nem['l']}P" if nem else None)
            c3.metric("🎯 Ulubiony rywal",fav["name"] if fav else "—",f"{fav['w']}W–{fav['l']}P" if fav else None)
            if profile.get("teams"):
                st.markdown("#### 🎮 Drużyny gracza")
                st.dataframe(pd.DataFrame([{"Drużyna":x["team"],"M":x["matches"],"W":x["w"],"R":x["d"],"P":x["l"],"W%":x["win_pct"],"Bramki":f"{x['gf']}:{x['ga']}"} for x in profile["teams"]]),hide_index=True,use_container_width=True)
            if profile.get("history"):
                st.markdown("#### 🕘 Ostatnie 10 oficjalnych meczów")
                stage_labels={"GROUP":"GRUPA","LEAGUE":"LIGA","WB":"WINNERS","WB_FINAL":"FINAŁ WINNERS","LB":"LOSERS","LB_FINAL":"FINAŁ LOSERS","QF":"ĆWIERĆFINAŁ","BARRAGE":"BARAŻ","SF":"PÓŁFINAŁ","FINAL":"FINAŁ","RESET_FINAL":"RESET FINAL"}
                hist=[]
                for x in profile["history"]:
                    raw=x.get("played_at") or "";date=raw[:10] if raw else "—"
                    hist.append({"Data":date,"Wynik":x["result"],"Faza":stage_labels.get(x.get("stage"),x.get("stage") or "—"),"Rywal":x["opponent"],"Drużyna":x["team"],"Rezultat":x["score"]})
                st.dataframe(pd.DataFrame(hist),hide_index=True,use_container_width=True)

    with tab6:
        scorers=db.scorer_stats()
        if not scorers:st.info("Brak zapisanych strzelców w oficjalnych turniejach.")
        else:
            df=pd.DataFrame([{"#":i+1,"Zawodnik":x["name"],"Gole":x["goals"],"Mecze z golem":x["matches_scored"],"Drużyny":x["teams"]} for i,x in enumerate(scorers)])
            st.dataframe(df,hide_index=True,use_container_width=True)

        st.markdown("### ✏️ Listy zawodników drużyn")
        st.caption("Tu możesz dopisać zawodników do podpowiedzi. Wpisywanie w formularzu nie odświeża strony — zapis następuje dopiero po kliknięciu przycisku.")
        teams=db.scorer_roster_teams()
        selected_team=st.selectbox("Drużyna",teams,key="scorer_roster_team")
        current=db.team_scorer_options(selected_team)
        if current:
            st.caption("Aktualne podpowiedzi: " + " • ".join(x["name"] for x in current))
        with st.form("add_scorer_roster",clear_on_submit=True):
            raw=st.text_area("Dodaj zawodników",placeholder="Po jednym nazwisku w każdej linii",height=110)
            add_btn=st.form_submit_button("➕ Dodaj do drużyny",use_container_width=True)
        if add_btn:
            names=[x.strip() for x in raw.splitlines() if x.strip()]
            if not names:st.warning("Wpisz przynajmniej jednego zawodnika.")
            else:
                try:
                    n=db.add_team_scorers(selected_team,names)
                    if n:st.success(f"Dodano {n} zawodników do {selected_team}.");rf()
                    else:st.info("Wszyscy wpisani zawodnicy byli już na liście.")
                except ValueError as e:st.error(str(e))


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

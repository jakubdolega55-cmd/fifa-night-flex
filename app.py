from __future__ import annotations

import html
import os
import time
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

from database import Database
from export_utils import generate_summary_png, generate_settlement_png, generate_awards_png, generate_year_summary_png
from logic import BASE_TEAMS, FIXED_TEAMS, SIX_TEAMS, SEVEN_TEAMS, EIGHT_TEAMS, FORMAT_LABELS, FORMAT_MATCH_COUNTS
from ui import (hero, inject_css, render_wheel, render_structure_draw, render_draft_order, standings_df, result_text,
                render_double5_mid_draw, render_double7_combined_draw, render_double_wb_pairing_draw, render_playoff_reveal)



def fmt_history_datetime(value):
    """Format stored UTC ISO timestamps for the FIFA Night history timeline in Poland time."""
    raw=str(value or "").strip()
    if not raw:
        return "—"
    try:
        dt=datetime.fromisoformat(raw.replace("Z","+00:00"))
        if dt.tzinfo is None:
            dt=dt.replace(tzinfo=timezone.utc)
        dt=dt.astimezone(ZoneInfo("Europe/Warsaw"))
        return dt.strftime("%d.%m.%Y %H:%M")
    except Exception:
        # Older/manual rows may contain only YYYY-MM-DD. Preserve them instead of failing the page.
        return raw[:16].replace("T"," ") or "—"

st.set_page_config(page_title="FIFA Night Flex",page_icon="⚽",layout="wide",initial_sidebar_state="collapsed")
inject_css(); db=Database()
if not st.session_state.get("_flex_schema_ready"):
    db.init_schema(); st.session_state._flex_schema_ready=True


def esc(x):return html.escape(str(x or ""))
def format_option(x):return f"{FORMAT_LABELS[x]} • {FORMAT_MATCH_COUNTS[x]}"
def pln_cents(cents:int)->str:
    return f"{int(cents or 0)/100:.2f}".replace(".",",")
def pln_value(value:float)->str:
    return f"{float(value or 0):.2f}".replace(".",",")
def rr():st.rerun()
def rf():st.rerun(scope="fragment")

@st.cache_data(ttl=30,show_spinner=False)
def official_player_names_cached():
    return db.official_player_names()

@st.cache_data(ttl=30,show_spinner=False)
def wildcard_team_suggestions_cached():
    return db.wildcard_team_suggestions()

@st.cache_data(show_spinner=False)
def tournament_summary_png_cached(bundle:dict, summary:dict, official_no:int|None):
    return generate_summary_png(bundle, summary, FORMAT_LABELS, official_no)

def render_tournament_status_control(t:dict, loc:str):
    is_test=bool(int(t.get("is_test") or 0))
    current="🧪 Testowy" if is_test else "🏆 Oficjalny"
    stake=float(t.get("stake_per_player") or 0)
    stake_label=f" • 💰 {pln_value(stake)} zł/os." if stake>0 else ""
    if t.get("format_key")=="duel1v1":
        with st.expander(f"⚙️ Status meczu • ⚔️ Oficjalny{stake_label}",expanded=False):
            st.caption("Mecz 1 vs 1 jest zawsze oficjalny. Stawka jest opcjonalna i nie zmienia statusu meczu.")
        return
    with st.expander(f"⚙️ Status turnieju • {current}{stake_label}",expanded=False):
        st.caption("Status można zmienić bez resetowania turnieju. Wyniki, drabinka i strzelcy zostają bez zmian. Po zakończeniu status decyduje, czy rozgrywka liczy się do oficjalnych statystyk.")
        if is_test:
            st.info("🏆 Zmiana turnieju testowego na oficjalny wymaga hasła i jednocześnie włącza sterowanie na tym urządzeniu.")
            with st.form(f"promote_official_{loc}_{t['id']}"):
                pwd=st.text_input("Hasło administratora",type="password",key=f"promote_pwd_{loc}_{t['id']}")
                go=st.form_submit_button("🏆 ZMIEŃ NA OFICJALNY",use_container_width=True)
            if go:
                if not admin_ok(pwd):
                    st.error("Nieprawidłowe hasło.")
                else:
                    db.set_test_mode(t["id"],False)
                    st.session_state._controller_access=True
                    st.session_state.awards_admin_ok=True
                    official_player_names_cached.clear()
                    tournament_summary_png_cached.clear()
                    st.success("Turniej jest oficjalny. Sterowanie na tym urządzeniu zostało włączone.")
                    rr()
        else:
            if st.button("Zmień na testowy",use_container_width=True,key=f"mode_{loc}_{t['id']}_0"):
                db.set_test_mode(t["id"],True)
                official_player_names_cached.clear()
                tournament_summary_png_cached.clear()
                rr()

def admin_password():
    value=os.getenv("ADMIN_PASSWORD")
    if value:return value
    try:return str(st.secrets.get("ADMIN_PASSWORD") or "")
    except Exception:return ""

def admin_ok(value):
    secret=admin_password()
    return bool(secret) and str(value)==secret

def controller_access() -> bool:
    """Whether this browser session may change tournament data."""
    return bool(st.session_state.get("_controller_access",False))

def render_access_settings():
    st.subheader("⚙️ Ustawienia dostępu")
    if controller_access():
        st.success("🎮 To urządzenie ma włączone sterowanie FIFA Night.")
        st.caption("Możesz tworzyć oficjalne FIFA Night, losować, wpisywać wyniki oraz korzystać z pozostałych funkcji edycyjnych. Mecz 1 vs 1 jest zawsze oficjalny i można go prowadzić także bez sterowania. Operacje szczególnie wrażliwe, takie jak kasowanie historii, nadal wymagają osobnego potwierdzenia hasłem.")
        if st.button("📺 WYŁĄCZ STEROWANIE NA TYM URZĄDZENIU",use_container_width=True,key="controller_disable"):
            st.session_state._controller_access=False
            st.session_state.awards_admin_ok=False
            st.session_state.start_view="stats"
            st.session_state.viewer_view="📺 LIVE"
            st.session_state.public_view="fifa"
            rr()
    else:
        st.info("📺 To urządzenie działa bez sterowania. Możesz przeglądać dane, uruchamiać i prowadzić turnieje testowe oraz grać oficjalne 1 vs 1. Do rozpoczęcia oficjalnego turnieju FIFA Night potrzebne jest sterowanie.")
        if not admin_password():
            st.error("Brak ADMIN_PASSWORD w Streamlit Secrets. Nie można włączyć sterowania.")
            return
        with st.form("controller_unlock_form"):
            pwd=st.text_input("Hasło administratora",type="password",key="controller_unlock_pwd")
            go=st.form_submit_button("🎮 WŁĄCZ STEROWANIE NA TYM URZĄDZENIU",type="primary",use_container_width=True)
        if go:
            if admin_ok(pwd):
                st.session_state._controller_access=True
                st.session_state.awards_admin_ok=True
                st.session_state.start_view="fifa"
                st.success("Sterowanie włączone.")
                rr()
            else:
                st.error("Nieprawidłowe hasło.")
        st.caption("Dostęp jest zapamiętany w bieżącej sesji przeglądarki. Po zamknięciu sesji, ponownym otwarciu aplikacji lub jej wybudzeniu może być potrzebne ponowne wpisanie hasła.")

def render_history_admin():
    st.markdown("### 🔐 Historia i baza")
    locked=db.history_locked(); secret_ready=bool(admin_password())
    if locked: st.success("🔒 Historia jest zablokowana przed usuwaniem.")
    else: st.warning("🔓 Historia jest odblokowana.")
    if not secret_ready:
        st.error("Brak ADMIN_PASSWORD w Streamlit Secrets. Operacje administracyjne są wyłączone.")
        return

    st.markdown("#### ✏️ Zmiana nazwy gracza")
    st.caption("Zmiana dotyczy całego profilu gracza, więc nowy nick pojawi się również przy wszystkich historycznych turniejach, meczach, H2H, statystykach i AWARDS. To nie łączy dwóch różnych profili graczy.")
    admin_players=db.admin_players()
    if admin_players:
        player_options={str(x["id"]):str(x["name"]) for x in admin_players}
        with st.form("rename_player_admin"):
            rename_pid=st.selectbox("Gracz",list(player_options),format_func=lambda x:player_options.get(str(x),str(x)),key="rename_player_id")
            rename_new=st.text_input("Nowa nazwa",value=player_options.get(str(rename_pid),""),key="rename_player_new")
            rename_pwd=st.text_input("Hasło administratora",type="password",key="rename_player_pwd")
            rename_confirm=st.checkbox("Potwierdzam zmianę nazwy także w historii",key="rename_player_confirm")
            rename_go=st.form_submit_button("✏️ ZMIEŃ NAZWĘ GRACZA",use_container_width=True)
        if rename_go:
            if not admin_ok(rename_pwd): st.error("Nieprawidłowe hasło.")
            elif not rename_confirm: st.error("Zaznacz potwierdzenie zmiany historycznej.")
            else:
                try:
                    result=db.rename_player(rename_pid,rename_new)
                    official_player_names_cached.clear(); tournament_summary_png_cached.clear()
                    old_name=str(result.get("old_name") or ""); new_name=str(result.get("new_name") or "")
                    for k in list(st.session_state.keys()):
                        if str(k).startswith("_lineup_init_"): st.session_state.pop(k,None)
                        elif str(k).startswith("p_") and isinstance(st.session_state.get(k),str) and st.session_state.get(k).strip().casefold()==old_name.strip().casefold():
                            st.session_state[k]=new_name
                    if result.get("changed"): st.success(f"Zmieniono nazwę: {old_name} → {new_name}. Historia została zachowana pod nową nazwą.")
                    else: st.info("Nazwa gracza nie wymagała zmiany.")
                    rr()
                except ValueError as e: st.error(str(e))
    else:
        st.caption("Brak graczy w bazie.")

    st.divider()
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
        unfinished=str(last.get("status") or "")=="abandoned"
        ending="niedokończony" if unfinished else f"mistrz: {last.get('champion_name') or '?'}"
        st.caption(f"Ostatni turniej: {last.get('player_count','?')} graczy • {fmt} • {ending}")
        with st.form("delete_last_history"):
            pwd=st.text_input("Hasło administratora",type="password",key="del_last_pwd")
            yes=st.checkbox("Tak, usuń ostatni zamknięty turniej nietestowy")
            go=st.form_submit_button("🗑️ USUŃ OSTATNI TURNIEJ",use_container_width=True)
        if go:
            if not admin_ok(pwd): st.error("Nieprawidłowe hasło.")
            elif not yes: st.error("Zaznacz potwierdzenie.")
            else:
                deleted=db.delete_last_completed_tournament();st.success("Ostatni turniej został usunięty." if deleted else "Brak turnieju do usunięcia.");rr()
    else: st.caption("Brak zamkniętych turniejów nietestowych do usunięcia.")
    with st.form("clear_all_history"):
        pwd=st.text_input("Hasło administratora",type="password",key="clear_all_pwd")
        confirm=st.text_input("Wpisz USUŃ HISTORIĘ")
        go=st.form_submit_button("💣 WYCZYŚĆ CAŁĄ HISTORIĘ",use_container_width=True)
    if go:
        if not admin_ok(pwd): st.error("Nieprawidłowe hasło.")
        elif confirm!="USUŃ HISTORIĘ": st.error("Wpisz dokładnie: USUŃ HISTORIĘ")
        else: db.clear_all_history();st.success("Historia wszystkich turniejów została wyczyszczona. Zapamiętane nicki zostały zachowane.");rr()

def format_for(count:int)->str:
    if count==3:return "league3_final"
    if count==4:return st.session_state.get("format4","league4_final")
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
        matched=canonical.get(remembered.casefold()) if remembered else None
        if matched: st.session_state[field_key]=matched
        else: st.session_state.pop(field_key,None)
        st.session_state.setdefault(f"cash_{count}_{i}",True)
    st.session_state[key]=True


def render_duel_start(official_names:list[str]):
    st.markdown("### ⚔️ Mecz 1 vs 1")
    st.caption("Ręczny wybór graczy i drużyn. 1v1 liczy się do H2H, formy i statystyk meczowych, ale nie do tytułów ani statystyk turniejowych.")
    team_options=list(dict.fromkeys(FIXED_TEAMS + wildcard_team_suggestions_cached()))
    with st.form("create_duel_form"):
        c1,c2=st.columns(2)
        with c1:
            p1=st.selectbox("Gracz 1",official_names,index=None,accept_new_options=True,placeholder="Wpisz nick lub wybierz",key="duel_p1")
            t1=st.selectbox("Drużyna gracza 1",team_options,index=None,accept_new_options=True,placeholder="Wpisz lub wybierz drużynę",key="duel_t1")
            cash1=st.checkbox("💰 Gra za kasę",value=True,key="duel_cash1")
        with c2:
            p2=st.selectbox("Gracz 2",official_names,index=None,accept_new_options=True,placeholder="Wpisz nick lub wybierz",key="duel_p2")
            t2=st.selectbox("Drużyna gracza 2",team_options,index=None,accept_new_options=True,placeholder="Wpisz lub wybierz drużynę",key="duel_t2")
            cash2=st.checkbox("💰 Gra za kasę",value=True,key="duel_cash2")
        stake=st.number_input("💰 Stawka na osobę (zł)",min_value=0.0,step=5.0,format="%.2f",value=float(db.last_stake()),key="duel_stake")
        st.caption("Jeśli choć jedna osoba odznaczy „Gra za kasę”, mecz automatycznie będzie bezpłatny.")
        st.info("⚔️ Każdy mecz 1 vs 1 jest oficjalny. Może być grany za kasę albo bez stawki i nie wymaga przejęcia sterowania.")
        go=st.form_submit_button("⚔️ UTWÓRZ MECZ 1 VS 1",type="primary",use_container_width=True)
    if go:
        try:
            db.create_duel([p1,p2],[t1,t2],False,stake,[cash1,cash2])
            st.session_state.pop("last_spin",None);rr()
        except ValueError as e:st.error(str(e))



def render_pending_goal_milestones(compact:bool=False):
    data=db.global_milestones();pending=data.get("pending_goal_scorers") or []
    if not pending:return
    item=pending[0];m=item.get("match") or {};key=str(item.get("key") or "")
    title=str(item.get("title") or "Jubileuszowy gol")
    exp_label=f"⚽ Do uzupełnienia: {title}" if len(pending)==1 else f"⚽ Do uzupełnienia: {len(pending)} jubileuszowe gole"
    with st.expander(exp_label,expanded=not compact):
        st.warning(f"**{title}** padł w meczu **{item.get('detail','—')}**. W bazie znamy liczbę goli strzelców, ale nie kolejność bramek — wskaż autora jubileuszowego gola.")
        candidates=item.get("candidates") or []
        cand_map={}
        for i,c in enumerate(candidates):
            cid=f"cand_{i}"
            cand_map[cid]=c
        with st.form(f"goal_milestone_{key}"):
            if cand_map:
                choice=st.selectbox("Strzelec",list(cand_map),format_func=lambda x:f"{cand_map[x].get('scorer_name')} — {cand_map[x].get('player_name')} • {cand_map[x].get('team') or '—'} ({cand_map[x].get('goals')} goli w tym meczu)",key=f"gm_choice_{key}")
                manual=st.text_input("Jeśli nie ma go na liście, wpisz ręcznie",key=f"gm_manual_{key}")
                sides={str(m.get('home_player_id') or ''):str(m.get('home_name') or '?'),str(m.get('away_player_id') or ''):str(m.get('away_name') or '?')}
                manual_pid=st.selectbox("Jeśli wpisujesz ręcznie — dla którego gracza strzelał?",list(sides),format_func=lambda x:sides.get(x,x),key=f"gm_manual_pid_{key}") if sides else None
            else:
                st.caption("W tym historycznym meczu nie zapisano strzelców. Możesz wpisać autora ręcznie, jeśli go pamiętasz.")
                manual=st.text_input("Strzelec jubileuszowego gola",key=f"gm_manual_{key}")
                sides={str(m.get('home_player_id') or ''):str(m.get('home_name') or '?'),str(m.get('away_player_id') or ''):str(m.get('away_name') or '?')}
                manual_pid=st.selectbox("Dla którego gracza strzelał?",list(sides),format_func=lambda x:sides.get(x,x),key=f"gm_manual_pid_{key}") if sides else None
                choice=None
            pwd=st.text_input("Hasło administratora",type="password",key=f"gm_pwd_{key}")
            go=st.form_submit_button("💾 ZAPISZ STRZELCA",use_container_width=True)
        if go:
            if not admin_ok(pwd):st.error("Nieprawidłowe hasło.")
            else:
                try:
                    if str(manual or "").strip():
                        pid=str(manual_pid or "");pname=sides.get(pid,"")
                        db.set_goal_milestone_scorer(key,manual,pid,pname)
                    elif cand_map and choice:
                        c=cand_map[choice];db.set_goal_milestone_scorer(key,c.get("scorer_name"),c.get("player_id"),c.get("player_name"))
                    else:raise ValueError("Wybierz lub wpisz strzelca.")
                    st.success("Jubileuszowy strzelec zapisany.");rr()
                except ValueError as e:st.error(str(e))
        if len(pending)>1:st.caption(f"Po zapisaniu pojawi się kolejny brakujący jubileuszowy gol ({len(pending)-1} pozostałych).")

def render_fifa_night_setup(official_names:list[str], force_test:bool=False):
    if force_test:
        st.info("🧪 Bez sterowania możesz uruchamiać turnieje testowe oraz oficjalne 1 vs 1. Aby rozpocząć oficjalny turniej FIFA Night dla 3–8 graczy, włącz sterowanie w Ustawieniach.")

    # 1 vs 1 jest zwykłym wariantem FIFA Night, obok turniejów 3–8 osobowych.
    # Nie dokładamy osobnej warstwy nawigacji tylko po to, żeby wybrać liczbę graczy.
    default_count=db.last_player_count()
    if default_count not in (3,4,5,6,7,8):default_count=6
    variant_key=f"fifa_variant_{int(force_test)}"
    variant_default=str(default_count)
    variant=st.segmented_control(
        "Wariant",
        ["1 vs 1","3","4","5","6","7","8"],
        default=None if variant_key in st.session_state else variant_default,
        key=variant_key,
    ) or str(st.session_state.get(variant_key) or variant_default)
    if variant=="1 vs 1":
        render_duel_start(official_names)
        return

    if not db.is_postgres:st.warning("Tryb lokalny SQLite. Na Streamlit Cloud podłącz DATABASE_URL z Neon.")
    count=int(variant)
    start_defaults(count,official_names)
    if count==4:
        st.session_state.format4=st.radio("Format dla 4 graczy",["league4_final","double4"],format_func=format_option,horizontal=False,key="format4_radio")
    elif count==5:
        st.session_state.format5=st.radio("Format dla 5 graczy",["double5","league5_final"],format_func=format_option,horizontal=False,key="format5_radio")
    elif count==6:
        st.session_state.format6=st.radio("Format dla 6 graczy",["groups6","groups6_full","double6"],format_func=format_option,horizontal=False,key="format6_radio")
    elif count==7:
        st.session_state.format7=st.radio("Format dla 7 graczy",["double7","groups7","groups7_sf"],format_func=format_option,horizontal=False,key="format7_radio")
    elif count==8:
        st.session_state.format8=st.radio("Format dla 8 graczy",["groups8_sf","double8","groups8_barrage"],format_func=format_option,horizontal=False,key="format8_radio")
    fmt=format_for(count)
    st.markdown(f"**Format:** {FORMAT_LABELS[fmt]}  \n**Łącznie:** {FORMAT_MATCH_COUNTS[fmt]}")
    if "stake_per_player" not in st.session_state:st.session_state.stake_per_player=float(db.last_stake())
    with st.form(f"create_{count}_{fmt}_{int(force_test)}"):
        st.caption("Nicki z oficjalnych statystyk są podpowiadane. Przy każdym graczu możesz wyłączyć udział w puli pieniężnej.")
        names=[];cash_flags=[]
        for i in range(count):
            c_name,c_cash=st.columns([3.4,1.35],vertical_alignment="bottom")
            with c_name:
                names.append(st.selectbox(f"Gracz {i+1}",official_names,index=None,key=f"p_{count}_{i}",placeholder="Wpisz nick lub wybierz z listy",accept_new_options=True))
            with c_cash:
                cash_flags.append(st.checkbox("💰 Gra za kasę",value=True,key=f"cash_{count}_{i}"))
        if count in (3,4,5):
            teams=BASE_TEAMS.copy()
            st.markdown("**Draft drużyn:** losujemy kolejność, potem każdy wybiera klub z puli stałej albo dostępny Wild Card.")
            st.caption("Stałe: Bayern • Barcelona • PSG • Liverpool. Wild Card może być użyty kilka razy, ale konkretny klub tylko raz.")
        elif count==6:
            teams=SIX_TEAMS.copy();st.caption("Pula: Bayern • Barcelona • PSG • Liverpool + 2 sloty Wild Card. Man City jest Wild Cardem.")
        elif count==7:
            teams=SEVEN_TEAMS.copy();st.caption("Pula: 4 kluby stałe + 3 sloty Wild Card. Real Madryt banned.")
        else:
            teams=EIGHT_TEAMS.copy();st.caption("Pula: 4 kluby stałe + 4 sloty Wild Card. Real Madryt banned.")
        stake=st.number_input("💰 Stawka na osobę (zł)",min_value=0.0,step=5.0,format="%.2f",key="stake_per_player")
        jackpot=db.current_jackpot_cents()
        if jackpot>0:st.warning(f"🎰 Aktualny jackpot do przejęcia przez kolejnego uprawnionego mistrza: **{pln_cents(jackpot)} zł**")
        st.caption("Gracz z wyłączonym „Gra za kasę” gra normalnie sportowo, ale nie wpłaca i nie może odebrać puli. Jeśli wygra — pula przechodzi do jackpotu.")
        if force_test:
            test=True
            st.caption("🧪 Ten turniej zostanie utworzony jako testowy.")
        else:
            test=st.toggle("🧪 Tryb testowy",value=True,key=f"test_{count}")
        go=st.form_submit_button("🎮 UTWÓRZ TURNIEJ",type="primary",use_container_width=True)
    if go:
        try:
            db.create_tournament(names,count,fmt,teams,test,stake,cash_flags)
            st.session_state.pop("last_spin",None);rr()
        except ValueError as e:st.error(str(e))
    if not force_test:
        with st.expander("⚙️ Historia i baza"):
            render_history_admin()


def render_start(public_mode:bool=False):
    state_key="public_view" if public_mode else "start_view"
    current=st.session_state.get(state_key,"fifa")
    subtitles={
        "fifa":"Wybierz wariant FIFA Night i rozpocznij rozgrywkę.",
        "stats":"Rankingi, profile, drużyny, strzelcy, rozliczenia i historia.",
        "awards":"FIFA Night Awards i kamienie milowe.",
        "settings":"Sterowanie i ustawienia dostępu.",
    }
    hero(subtitles.get(current,subtitles["fifa"]))
    cols=st.columns(4)
    nav=[("fifa","🎮 FIFA NIGHT"),("stats","📊 STATYSTYKI"),("awards","🏆 AWARDS"),("settings","⚙️ USTAWIENIA")]
    for col,(key,label) in zip(cols,nav):
        with col:
            if st.button(label,type="primary" if current==key else "secondary",use_container_width=True,key=f"{'public' if public_mode else 'start'}_nav_{key}"):
                st.session_state[state_key]=key;rr()
    if public_mode:
        st.caption("🧪 Turnieje testowe oraz ⚔️ oficjalne 1 vs 1 są dostępne bez hasła. Do rozpoczęcia oficjalnego turnieju FIFA Night potrzebne jest sterowanie w Ustawieniach.")
    render_pending_goal_milestones(compact=current not in ("fifa","stats"))
    if current=="stats":render_stats(readonly=public_mode);return
    if current=="awards":render_awards(readonly=public_mode);return
    if current=="settings":render_access_settings();return
    render_fifa_night_setup(official_player_names_cached(),force_test=public_mode)


@st.fragment
def draft_order(tid:str):
    b=db.setup_bundle(tid); players=b["players"]; meta=b["meta"]; extra=meta["extra"]
    revealed=bool(extra.get("draft_order_revealed",False))
    draw_slot=st.empty()
    if not revealed:
        reveal_slot=st.empty()
        with reveal_slot.container():
            reveal=st.button("🎱 LOSUJ KOLEJNOŚĆ WYBORU",type="primary",use_container_width=True,key=f"draft_reveal_{tid}")
        if not reveal:
            return
        reveal_slot.empty()
        # The order already exists in DB; revealing it doesn't require another rerun/read.
        db.reveal_draft_order(tid)
        revealed=True
    with draw_slot.container():
        render_draft_order(players,int(extra.get("draft_redraw_count",0)))
    c1,c2=st.columns(2)
    with c1:
        if st.button("✅ ZATWIERDŹ KOLEJNOŚĆ",type="primary",use_container_width=True,key=f"draft_accept_{tid}"):
            db.confirm_draft_order(tid);rr()
    with c2:
        if st.button("💸 ZAPŁAĆ I WYLOSUJ PONOWNIE",use_container_width=True,key=f"draft_reroll_{tid}"):
            refreshed=db.reroll_draft_order(tid)
            draw_slot.empty()
            with draw_slot.container():
                render_draft_order(refreshed.get("players",players),int(refreshed.get("redraw_count",0)))


def render_draft_order_stage(t):
    hero(f"Etap 1/3 • losowanie kolejności wyboru • {t['player_count']} graczy")
    render_tournament_status_control(t,"draft_order")
    draft_order(t["id"]);reset_controls(t,"draft_order")


@st.fragment
def team_draft(tid:str):
    b=db.setup_bundle(tid); players=b["players"]; pool=b["meta"]["team_pool"]
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
        wildcard=st.selectbox("Wild Card — wpisz lub wybierz drużynę",options=db.available_wildcard_suggestions(tid),index=None,
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
    render_tournament_status_control(t,"team_draft")
    team_draft(t["id"]);reset_controls(t,"team_draft")


@st.fragment
def team_draw(tid:str):
    # Setup screens don't need match rows. One lightweight state read is enough.
    bundle=db.setup_bundle(tid);players=bundle["players"];meta=bundle["meta"];pool=meta["team_pool"]
    hidden=[p for p in players if not p["team_revealed"]];last=st.session_state.get("last_spin")
    pending=(meta.get("extra") or {}).get("pending_wildcard")
    if pending: pending={**pending,"wildcard":True}
    done=len(players)-len(hidden)
    progress_slot=st.empty()
    progress_slot.progress(done/len(players),text=f"Wylosowano {done}/{len(players)} drużyn")
    wheel_slot=st.empty()

    def show_wheel(result:dict, display_result:str|None=None):
        wheel_slot.empty()
        with wheel_slot.container():
            render_wheel(result.get("wheel_team",result.get("team")),result["name"],tid,pool,display_result=display_result or result.get("team"))

    def next_after(result:dict, previous_hidden:list[dict], slot=None):
        remaining=[p for p in previous_hidden if str(p.get("player_id"))!=str(result.get("player_id"))]
        new_done=len(players)-len(remaining)
        progress_slot.progress(new_done/len(players),text=f"Wylosowano {new_done}/{len(players)} drużyn")
        target=slot if slot is not None else st.empty()
        target.empty()
        with target.container():
            if remaining:
                nxt=sorted(remaining,key=lambda x:x["team_reveal_order"])[0]
                st.button(f"🎰 ZAKRĘĆ DLA {nxt['name']}",type="primary",use_container_width=True,key=f"next_spin_{tid}_{new_done}")
            else:
                st.button("🎲 PRZEJDŹ DO KOLEJNEGO LOSOWANIA",type="primary",use_container_width=True,key=f"next_stage_{tid}_{new_done}")

    def show_pending_wildcard(result:dict):
        st.markdown(f"### 🃏 Wild Card — {esc(result['name'])}")
        with st.form(f"wildcard_draw_{tid}_{result['player_id']}"):
            st.selectbox("Wpisz lub wybierz drużynę",options=db.available_wildcard_suggestions(tid),index=None,
                         placeholder="np. Arsenal",accept_new_options=True,key=f"wheel_wc_{tid}_{result['player_id']}")
            st.form_submit_button("✅ ZATWIERDŹ DRUŻYNĘ",type="primary",use_container_width=True)

    if pending:
        with wheel_slot.container():
            render_wheel(pending["team"],pending["name"],tid,pool)
        st.markdown(f"### 🃏 Wild Card — {esc(pending['name'])}")
        with st.form(f"wildcard_draw_{tid}_{pending['player_id']}"):
            choice=st.selectbox("Wpisz lub wybierz drużynę",options=db.available_wildcard_suggestions(tid),index=None,
                                placeholder="np. Arsenal",accept_new_options=True,key=f"wheel_wc_{tid}_{pending['player_id']}")
            ok=st.form_submit_button("✅ ZATWIERDŹ DRUŻYNĘ",type="primary",use_container_width=True)
        if ok:
            try:
                wheel_team=pending["team"]
                team=db.confirm_wildcard_team(tid,pending["player_id"],choice)
                result={"player_id":pending["player_id"],"name":pending["name"],"team":team,"wheel_team":wheel_team,"wildcard":False}
                st.session_state.last_spin=result
                wildcard_team_suggestions_cached.clear()
                show_wheel(result,display_result=team)
                next_after(result,hidden)
            except ValueError as e:st.error(str(e))
        return

    if last:
        with wheel_slot.container():
            render_wheel(last.get("wheel_team",last["team"]),last["name"],tid,pool,display_result=last["team"])
        if hidden:
            nxt=sorted(hidden,key=lambda x:x["team_reveal_order"])[0]
            action_slot=st.empty()
            with action_slot.container():
                spin=st.button(f"🎰 ZAKRĘĆ DLA {nxt['name']}",type="primary",use_container_width=True,key=f"next_spin_{tid}_{done}")
            if spin:
                action_slot.empty()
                st.session_state.pop("last_spin",None)
                result=db.reveal_next_team(tid)
                if result:
                    # Render the new wheel immediately in this very run: no fragment rerun
                    # and no second Neon read before the animation starts.
                    show_wheel(result,display_result=result.get("team"))
                    if result.get("wildcard"):
                        st.session_state.pop("last_spin",None)
                        show_pending_wildcard(result)
                    else:
                        st.session_state.last_spin=result
                        next_after(result,hidden,action_slot)
            return
        if st.button("🎲 PRZEJDŹ DO KOLEJNEGO LOSOWANIA",type="primary",use_container_width=True,key=f"next_stage_{tid}_{done}"):
            st.session_state.pop("last_spin",None);db.start_structure_draw(tid);rr()
        return

    if hidden:
        nxt=sorted(hidden,key=lambda x:x["team_reveal_order"])[0]
        title_slot=st.empty();title_slot.subheader(f"🎡 Następny: {nxt['name']}")
        action_slot=st.empty()
        with action_slot.container():
            spin=st.button("🎰 ZAKRĘĆ KOŁEM",type="primary",use_container_width=True,key=f"spin_{nxt['player_id']}")
        if spin:
            action_slot.empty()
            result=db.reveal_next_team(tid)
            if result:
                title_slot.empty()
                show_wheel(result,display_result=result.get("team"))
                if result.get("wildcard"):
                    show_pending_wildcard(result)
                else:
                    st.session_state.last_spin=result
                    next_after(result,hidden,action_slot)
    else:
        if st.button("🎲 PRZEJDŹ DO KOLEJNEGO LOSOWANIA",type="primary",use_container_width=True,key=f"struct_{tid}"):
            db.start_structure_draw(tid);rr()


def render_team_draw(t):
    hero(f"Etap 1/2 • losowanie drużyn • {t['player_count']} graczy")
    render_tournament_status_control(t,"team_draw")
    team_draw(t["id"]);reset_controls(t,"draw")


@st.fragment
def structure_draw(tid:str):
    b=db.setup_bundle(tid);m=b["meta"]
    name_map={p["player_id"]:p["name"] for p in b["players"]}
    draw_slot=st.empty()
    revealed=bool(int(m["draw_revealed"]))
    if not revealed:
        reveal_slot=st.empty()
        with reveal_slot.container():
            reveal=st.button("🎱 LOSUJ",type="primary",use_container_width=True,key=f"reveal_struct_{tid}")
        if not reveal:
            return
        reveal_slot.empty()
        # Draw data is already present in memory. Persist reveal, then start animation
        # immediately instead of doing another fragment rerun + Neon fetch.
        db.reveal_structure(tid)
        revealed=True
    with draw_slot.container():
        render_structure_draw(m["format_key"],m["draw"],int(m["redraw_count"]),name_map=name_map)
    c1,c2=st.columns(2)
    with c1:
        if st.button("🏁 ZACZYNAMY TURNIEJ",type="primary",use_container_width=True,key=f"accept_{tid}"):
            db.confirm_structure(tid);rr()
    with c2:
        if st.button("💸 ZAPŁAĆ I WYLOSUJ PONOWNIE — PODGRZANE KULKI",use_container_width=True,key=f"reroll_{tid}"):
            refreshed=db.reroll_structure(tid)
            draw_slot.empty()
            with draw_slot.container():
                render_structure_draw(refreshed.get("format_key",m["format_key"]),refreshed.get("draw",m["draw"]),int(refreshed.get("redraw_count",0)),name_map=name_map)


def render_structure(t):
    title={"league3_final":"losowanie ustawienia ligi","league4_final":"losowanie ustawienia ligi","double4":"losowanie drabinki","double5":"losowanie drabinki","league5_final":"losowanie ustawienia ligi","groups6":"losowanie grup","groups6_full":"losowanie grup","double6":"losowanie drabinki","double7":"losowanie drabinki","groups7":"losowanie grup","groups7_sf":"losowanie grup","groups8_sf":"losowanie grup","double8":"losowanie drabinki","groups8_barrage":"losowanie grup"}[t["format_key"]]
    step="Etap 3/3" if int(t["player_count"]) in (3,4,5) else "Etap 2/2"
    hero(f"{step} • {title}")
    render_tournament_status_control(t,"structure")
    structure_draw(t["id"]);reset_controls(t,"structure")


def stage_name(m):
    s=m["stage"]
    if s=="GROUP":return f"GRUPA {m['group_name']}"
    return {"DUEL":"1 VS 1","LEAGUE":"LIGA","WB":"DRABINKA WYGRANYCH","WB_FINAL":"FINAŁ WINNERS","LB":"DRABINKA PRZEGRANYCH","LB_FINAL":"FINAŁ LOSERS","QF":"ĆWIERĆFINAŁ","BARRAGE":"BARAŻ","SF":"PÓŁFINAŁ","FINAL":"FINAŁ","RESET_FINAL":"RESET FINAL"}.get(s,s)

def max_matches(fmt):return {"duel1v1":1,"league3_final":4,"league4_final":7,"double4":6,"double5":8,"league5_final":11,"groups6":9,"groups6_full":11,"double6":10,"double7":12,"groups7":14,"groups7_sf":12,"groups8_sf":15,"double8":14,"groups8_barrage":17}[fmt]

def source_placeholder(fmt,no):
    maps={
      "duel1v1":{},
      "league3_final":{4:"1. miejsce ligi — 2. miejsce ligi"},
      "league4_final":{7:"1. miejsce ligi — 2. miejsce ligi"},
      "double4":{3:"Przegrany M1 — Przegrany M2",4:"Zwycięzca M1 — Zwycięzca M2",5:"Zwycięzca M3 — Przegrany finału Winners",6:"Mistrz Winners (start 1:0) — Mistrz Losers"},
      "double5":{3:"Szczęśliwy los — wylosowany zwycięzca M1/M2",4:"Przegrany M1 — Przegrany M2",5:"Drugi zwycięzca M1/M2 — Zwycięzca M3",6:"Zwycięzca M4 — Przegrany M3",7:"Zwycięzca M6 — Przegrany M5",8:"Mistrz winners (start 1:0) — Mistrz losers"},
      "league5_final":{11:"1. miejsce ligi — 2. miejsce ligi"},
      "groups6":{7:"1A — 2B / 1B — 2A",8:"Drugi półfinał",9:"Zwycięzca SF1 — Zwycięzca SF2"},
      "groups6_full":{7:"2A — 3B / 2B — 3A",8:"Drugi ćwierćfinał",9:"Zwycięzca grupy — Zwycięzca QF",10:"Zwycięzca grupy — Zwycięzca QF",11:"Zwycięzca SF1 — Zwycięzca SF2"},
      "double6":{3:"Zwycięzca M1 — Szczęśliwy los E",4:"Zwycięzca M2 — Szczęśliwy los F",5:"Przegrany M1 — Przegrany M2",6:"Zwycięzca M5 — Przegrany M3",7:"Finał Winners",8:"Zwycięzca M6 — Przegrany M4",9:"Finał Losers",10:"Mistrz Winners (start 1:0) — Mistrz Losers"},
      "double7":{4:"Losowanie Winners + Szczęśliwy los po pierwszej rundzie",5:"Drugi wylosowany półfinał Winners",6:"Dwóch przegranych bez Szczęśliwego losu",7:"Szczęśliwy los LB — przegrany półfinału WB",8:"Zwycięzca M6 — drugi przegrany półfinału WB",9:"Finał winners",10:"Drabinka przegranych",11:"Finał losers",12:"Mistrz winners (start 1:0) — Mistrz losers"},
      "groups7":{10:"2A — 3B / 2B — 3A",11:"Drugi ćwierćfinał",12:"Zwycięzca grupy — Zwycięzca QF",13:"Zwycięzca grupy — Zwycięzca QF",14:"Zwycięzca SF1 — Zwycięzca SF2"},
      "groups7_sf":{10:"1A — 2B / 1B — 2A",11:"Drugi półfinał",12:"Zwycięzca SF1 — Zwycięzca SF2"},
      "groups8_sf":{13:"1A — 2B / 1B — 2A",14:"Drugi półfinał",15:"Zwycięzca SF1 — Zwycięzca SF2"},
      "double8":{5:"Losowanie par Winners po pierwszej rundzie",6:"Drugi wylosowany półfinał Winners",7:"L1 — L2",8:"L3 — L4",9:"Zwycięzca LB M7 — przegrany WB M6",10:"Zwycięzca LB M8 — przegrany WB M5",11:"Finał winners",12:"Zwycięzcy M9 — M10",13:"Finał losers",14:"Mistrz winners (start 1:0) — Mistrz losers"},
      "groups8_barrage":{13:"2B — 3A / 2A — 3B",14:"Drugi baraż",15:"Zwycięzca grupy — Zwycięzca barażu",16:"Zwycięzca grupy — Zwycięzca barażu",17:"Zwycięzca SF1 — Zwycięzca SF2"},
    }
    return maps.get(fmt,{}).get(no,"Do ustalenia")


def _scorer_side_form(tid,m,side,team_name,player_name):
    options=db.team_scorer_options(team_name)
    known=[r["name"] for r in options]
    count_key=f"sc_rows_{tid}_{m['match_no']}_{side}"
    st.session_state.setdefault(count_key,3)
    count=max(3,min(8,int(st.session_state.get(count_key) or 3)))
    st.markdown(f"#### {esc(team_name)}")
    st.caption(f"{esc(player_name)} • wybierz tylko tych, których chcesz wpisać")
    for i in range(count):
        name_key=f"sc_name_{tid}_{m['match_no']}_{side}_{i}"
        goals_key=f"sc_goals_{tid}_{m['match_no']}_{side}_{i}"
        st.session_state.setdefault(goals_key,0)
        c_name,c_minus,c_num,c_plus=st.columns([4.6,.7,.85,.7],gap="small",vertical_alignment="center")
        with c_name:
            st.selectbox(f"Strzelec {i+1}",known,index=None,accept_new_options=True,placeholder="Wybierz lub wpisz nazwisko",key=name_key,label_visibility="collapsed")
        with c_minus:
            if st.button("−",key=f"sc_minus_{tid}_{m['match_no']}_{side}_{i}",use_container_width=True):
                st.session_state[goals_key]=max(0,int(st.session_state.get(goals_key) or 0)-1);rf()
        with c_num:
            st.markdown(f"<div style='text-align:center;font-size:1.15rem;font-weight:900;padding:.45rem 0'>{int(st.session_state.get(goals_key) or 0)}</div>",unsafe_allow_html=True)
        with c_plus:
            if st.button("+",key=f"sc_plus_{tid}_{m['match_no']}_{side}_{i}",use_container_width=True):
                st.session_state[goals_key]=min(20,int(st.session_state.get(goals_key) or 0)+1);rf()
    if count<8 and st.button("➕ Dodaj strzelca",key=f"sc_add_{tid}_{m['match_no']}_{side}",use_container_width=True):
        st.session_state[count_key]=count+1;rf()
    merged={}
    for i in range(count):
        n=" ".join(str(st.session_state.get(f"sc_name_{tid}_{m['match_no']}_{side}_{i}") or "").strip().split())
        g=int(st.session_state.get(f"sc_goals_{tid}_{m['match_no']}_{side}_{i}") or 0)
        if n and g>0:
            key=n.casefold();merged[key]={"name":n,"goals":int(merged.get(key,{}).get("goals",0))+g}
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
    wb_bonus = fmt in ("double4","double5","double6","double7","double8") and m.get("stage")=="FINAL"
    start_home = 1 if wb_bonus else 0
    if wb_bonus and st.session_state.get(f"hs_{tid}_{no}",1) < 1:st.session_state[f"hs_{tid}_{no}"]=1
    c1,mid,c2=st.columns([1,.18,1])
    with c1:hs=st.number_input(m["home_name"],min_value=start_home,max_value=99,value=start_home,step=1,key=f"hs_{tid}_{no}")
    with mid:st.markdown("<div class='score-separator'>:</div>",unsafe_allow_html=True)
    with c2:ass=st.number_input(m["away_name"],min_value=0,max_value=99,value=0,step=1,key=f"as_{tid}_{no}")
    st.divider()
    st.markdown("### ⚽ Strzelcy — opcjonalnie")
    st.caption("Domyślnie są 3 kompaktowe wiersze na drużynę. Możesz dodać kolejne lub zostawić wszystko puste.")
    sc1,sc2=st.columns(2)
    with sc1:home_sc=_scorer_side_form(tid,m,"home",m["home_team"],m["home_name"])
    with sc2:away_sc=_scorer_side_form(tid,m,"away",m["away_team"],m["away_name"])
    if wb_bonus:st.caption("Bonusowe 1:0 z Winners Bracket nie ma strzelca.")
    if st.button("✅ ZATWIERDŹ WYNIK",type="primary",use_container_width=True,key=f"save_score_{tid}_{no}"):
        scorers={"home":home_sc,"away":away_sc};ko=m["stage"] not in ("GROUP","LEAGUE")
        if ko and int(hs)==int(ass):st.session_state.pending_ko={"tid":tid,"no":no,"hs":int(hs),"as":int(ass),"scorers":scorers};rf()
        else:
            try:db.save_result(tid,no,int(hs),int(ass),scorers=scorers);rf()
            except ValueError as e:st.error(str(e))


def render_special_event(tid:str, b:dict) -> bool:
    fmt=b["meta"]["format_key"]
    if fmt=="double7":
        state=db.double7_combined_draw_state(tid)
        if state and not state.get("ack"):
            st.markdown("### 🎱 Losowanie Double Elimination")
            st.caption("Jednym losowaniem ustalamy pary Winners Bracket i Szczęśliwy los w Losers Bracket.")
            if not state.get("selected"):
                action=st.empty()
                with action.container():
                    go=st.button("🎰 LOSUJ DRABINKĘ",type="primary",use_container_width=True,key=f"d7_combo_draw_{tid}")
                if go:
                    action.empty()
                    revealed=db.reveal_double7_combined_draw(tid)
                    # Start the reveal animation from the data returned by the write itself.
                    # No extra fragment rerun/read is needed before showing it.
                    render_double7_combined_draw(revealed.get("pairs",[]),revealed.get("candidates",[]),revealed.get("selected_lucky"))
                    st.button("➡️ DRABINKA GOTOWA",type="primary",use_container_width=True,key=f"d7_combo_ack_{tid}")
            else:
                render_double7_combined_draw(state.get("pairs",[]),state.get("candidates",[]),state.get("selected_lucky"))
                if st.button("➡️ DRABINKA GOTOWA",type="primary",use_container_width=True,key=f"d7_combo_ack_{tid}"):
                    db.ack_double7_combined_draw(tid);rf()
            return True
    if fmt=="double8":
        state=db.double_wb_draw_state(tid)
        if state and not state.get("ack"):
            st.markdown("### 🎱 Losowanie par Winners Bracket")
            if not state.get("selected"):
                action=st.empty()
                with action.container():
                    go=st.button("🎰 LOSUJ PARY WINNERS",type="primary",use_container_width=True,key=f"wb_pair_draw_{fmt}_{tid}")
                if go:
                    action.empty()
                    revealed=db.reveal_double_wb_draw(tid)
                    render_double_wb_pairing_draw(fmt,revealed.get("pairs",[]))
                    st.button("➡️ DRABINKA GOTOWA",type="primary",use_container_width=True,key=f"wb_pair_ack_{fmt}_{tid}")
            else:
                render_double_wb_pairing_draw(fmt,state.get("pairs",[]))
                if st.button("➡️ DRABINKA GOTOWA",type="primary",use_container_width=True,key=f"wb_pair_ack_{fmt}_{tid}"):
                    db.ack_double_wb_draw(tid);rf()
            return True
    if fmt=="double5":
        state=db.double5_draw_state(tid)
        if state and not state.get("ack"):
            st.markdown("### 🎱 Losowanie przeciwnika dla Szczęśliwego losu")
            if not state.get("selected"):
                names=" • ".join(c["name"] for c in state.get("candidates",[]))
                st.markdown(f"**{esc(state['player_name'])}** czeka. W puli: **{esc(names)}**")
                action=st.empty()
                with action.container():
                    go=st.button("🎰 LOSUJ PRZECIWNIKA",type="primary",use_container_width=True,key=f"d5_mid_{tid}")
                if go:
                    action.empty()
                    selected=db.reveal_double5_opponent(tid)
                    render_double5_mid_draw(state["player_name"],state.get("candidates",[]),selected)
                    st.button("➡️ GRAMY DALEJ",type="primary",use_container_width=True,key=f"d5_mid_ack_{tid}")
            else:
                render_double5_mid_draw(state["player_name"],state.get("candidates",[]),state["selected"])
                if st.button("➡️ GRAMY DALEJ",type="primary",use_container_width=True,key=f"d5_mid_ack_{tid}"):
                    db.ack_double5_draw(tid);rf()
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
    b=db.bundle(tid);t=b["tournament"];meta=b["meta"];fmt=meta["format_key"]
    if t["status"]=="completed":
        summary=db.tournament_summary(tid);champ=summary.get("champion") or "Zwycięzca"
        finance=db.finance_event(tid) if not int(t.get("is_test") or 0) else None
        if fmt=="duel1v1":
            m=next((x for x in b.get("matches",[]) if x.get("home_score") is not None),None)
            score=(f"{m.get('home_score')}:{m.get('away_score')}" if m else "—")
            if m and m.get("home_penalties") is not None:score+=f" (k. {m.get('home_penalties')}:{m.get('away_penalties')})"
            st.markdown(f'<div class="winner"><div class="match-no">ZWYCIĘZCA 1 VS 1</div><div style="font-size:3rem">⚔️</div><div class="player-big">{esc(champ)}</div></div>',unsafe_allow_html=True)
            if st.session_state.get("celebrated")!=tid:st.balloons();st.session_state.celebrated=tid
            if m:st.success(f"**{esc(m.get('home_name'))} {score} {esc(m.get('away_name'))}**")
            if finance and int(finance.get("prize_cents") or 0)>0:
                st.info(f"💰 Zwycięzca otrzymuje **{pln_cents(finance['prize_cents'])} zł**. Mecz 1v1 nie rusza jackpotu turniejowego.")
            elif float((meta.get("extra") or {}).get("stake_per_player") or 0)<=0:
                st.caption("Mecz bezpłatny.")
            st.caption("Wynik liczy się do H2H, formy i statystyk meczowych, ale nie do tytułów, finałów ani Gracza Roku.")
            if t["is_test"]:st.info("Mecz testowy — nie liczy się do statystyk oficjalnych.")
            if st.button("➕ NOWY MECZ 1 VS 1",type="primary",use_container_width=True,key=f"new_duel_{tid}"):
                db.start_new()
                if controller_access():
                    st.session_state.start_view="fifa";st.session_state["fifa_variant_0"]="1 vs 1"
                else:
                    st.session_state.public_view="fifa";st.session_state["fifa_variant_1"]="1 vs 1"
                rr()
            return

        export_meta=db.tournament_export_meta(tid)
        png_bytes=tournament_summary_png_cached(b,summary,export_meta.get("official_no"))
        file_tag=f"turniej-{export_meta.get('official_no') or 'test'}-{str(export_meta.get('completed_at') or export_meta.get('created_at') or '')[:10]}".strip('-')
        st.markdown(f'<div class="winner"><div class="match-no">MISTRZ TURNIEJU</div><div style="font-size:3rem">🏆</div><div class="player-big">{esc(champ)}</div></div>',unsafe_allow_html=True)
        if st.session_state.get("celebrated")!=tid:st.balloons();st.session_state.celebrated=tid
        st.markdown("### 📋 Podsumowanie turnieju")
        stake=float((meta.get("extra") or {}).get("stake_per_player") or 0)
        cash_names=list((meta.get("extra") or {}).get("cash_player_names") or [])
        if stake>0:
            cash_count=len(cash_names) if "cash_player_names" in (meta.get("extra") or {}) else len(b.get("players",[]))
            st.info(f"💰 **Stawka:** {pln_value(stake)} zł / płacąca osoba • **wpłaty tego turnieju:** {pln_value(stake*cash_count)} zł • płaci: {cash_count}/{len(b.get('players',[]))}")
        if finance:
            jin=int(finance.get("jackpot_in_cents") or 0);jout=int(finance.get("jackpot_out_cents") or 0);prize=int(finance.get("prize_cents") or 0)
            if jin>0:st.warning(f"🎰 Do tego turnieju wszedł jackpot **{pln_cents(jin)} zł**.")
            if prize>0:st.success(f"💸 Do odbioru przez **{finance.get('prize_winner_name') or champ}**: **{pln_cents(prize)} zł**.")
            elif jout>0 and int(finance.get("contribution_cents") or 0)>0:
                st.warning(f"🎰 Mistrz nie grał za kasę — **{pln_cents(jout)} zł** przechodzi jako jackpot na następny oficjalny płatny turniej.")
        champ_record=summary.get("champion_record") or {}
        champ_team=next((p.get("team") for p in b.get("players",[]) if p.get("name")==champ),"—")
        st.success(f"🏆 **1. miejsce: {champ} • {champ_team}**\n\nBilans: {champ_record.get('w',0)}W / {champ_record.get('d',0)}R / {champ_record.get('l',0)}P • Bramki {champ_record.get('gf',0)}:{champ_record.get('ga',0)}")
        third=summary.get("third_place") or {};fourth=summary.get("fourth_place") or {}
        runner_name=summary.get("runner_up") or "—";runner_team=next((p.get("team") for p in b.get("players",[]) if p.get("name")==runner_name),"—")
        st.markdown("#### 🏅 Klasyfikacja")
        p1,p2,p3=st.columns(3);p1.info(f"🥈 **2. miejsce:** {runner_name} • {runner_team}")
        if third:p2.info(f"🥉 **3. miejsce:** {third.get('name','—')} • {third.get('team','—')}")
        if fourth:p3.info(f"4️⃣ **4. miejsce:** {fourth.get('name','—')} • {fourth.get('team','—')}")
        c1,c2=st.columns(2)
        if summary.get("biggest"):c1.info(f"💥 Największe zwycięstwo: **{summary['biggest']['home']} {summary['biggest']['score']} {summary['biggest']['away']}**")
        if summary.get("highest"):c2.info(f"🎯 Najbardziej bramkowy mecz: **{summary['highest']['home']} {summary['highest']['score']} {summary['highest']['away']}**")
        mot=summary.get("match_of_tournament")
        if mot:
            mot_score=mot["score"]
            if mot.get("home_penalties") is not None and mot.get("away_penalties") is not None:mot_score+=f" (k. {mot['home_penalties']}:{mot['away_penalties']})"
            st.warning(f"🎬 **Mecz turnieju:** {mot['home']} {mot_score} {mot['away']} • {stage_name({'stage':mot.get('stage'),'group_name':mot.get('group_name') or ''})}")
        if summary.get("real_top_scorer"):st.success(f"🥇 Strzelec turnieju: **{summary['real_top_scorer']['name']} — {summary['real_top_scorer']['goals']} goli**")
        else:st.info("⚽ **Strzelcy:** nie uzupełniono strzelców w tym turnieju.")
        if summary.get("rivalry_match"):st.info(f"🔥 Rivalry match turnieju: **{summary['rivalry_match']['home']} {summary['rivalry_match']['score']} {summary['rivalry_match']['away']}**")
        if summary.get("new_records"):
            st.markdown("#### 🆕 Nowe rekordy")
            for r in summary["new_records"]:st.success(r)
        if not int(t.get("is_test") or 0):
            unlocked_now=db.achievements_unlocked_in_tournament(tid)
            milestones_now=db.milestones_in_tournament(tid)
            if unlocked_now:
                st.markdown("#### 🔓 Odblokowane podczas tego FIFA Night")
                for a in unlocked_now:st.success(f"{a.get('icon','🏅')} **{a.get('player_name')} — {a.get('name')}**{f' • {a.get("detail")}' if a.get('detail') else ''}")
            if milestones_now:
                st.markdown("#### 🏛️ Kamienie milowe tego FIFA Night")
                for x in milestones_now:st.info(f"{x.get('icon','💎')} **{x.get('title')}**{f' • {x.get("detail")}' if x.get('detail') else ''}")
        st.markdown("### 🖼️ Eksport")
        e1,e2=st.columns(2)
        with e1:st.download_button("📸 Pobierz podsumowanie PNG",data=png_bytes,file_name=f"{file_tag}.png",mime="image/png",use_container_width=True,key=f"dl_png_{tid}")
        with e2:
            if st.button("➕ NOWY TURNIEJ",type="primary",use_container_width=True,key=f"new_{tid}"):
                db.start_new()
                if controller_access():st.session_state.start_view="fifa"
                else:st.session_state.public_view="fifa"
                rr()
        if t["is_test"]:st.info("Turniej testowy — nie liczy się do statystyk wszech czasów ani finansów.")
        return

    if render_special_event(tid,b): return
    b=db.bundle(tid);cur=db.current_match_from(b["matches"],meta.get("extra") or {})
    if not cur:st.info("Czekam na rozstrzygnięcie poprzedniego etapu…");return
    total=max_matches(fmt)
    if not int(t.get("is_test") or 0):
        global_jubilee=db.upcoming_global_match_milestone()
        if global_jubilee:
            st.markdown(f"<div class='winner' style='padding:18px;margin:8px 0 16px'><div class='match-no'>💎 MECZ JUBILEUSZOWY</div><div class='player-big' style='font-size:2rem'>{esc(global_jubilee['title'])}</div><div class='team-small'>Ten mecz zostanie zapisany w kamieniach milowych FIFA Night.</div></div>",unsafe_allow_html=True)
    st.markdown(f'<div class="match-no">MECZ {cur["match_no"]}/{total} • {stage_name(cur)}</div>',unsafe_allow_html=True)
    if fmt in ("double4","double5","double6","double7","double8") and cur.get("stage")=="FINAL":
        st.markdown(f"<div class='winner' style='padding:18px;margin:10px 0 16px'><div class='match-no'>🏆 BONUS WINNERS BRACKET</div><div class='player-big' style='font-size:2rem'>{esc(cur['home_name'])} zaczyna finał 1:0</div><div class='team-small'>Jeden finał. Bez resetu. Bonusowy gol nie ma strzelca.</div></div>",unsafe_allow_html=True)
    st.markdown(f'<div class="match-card"><div style="display:flex;justify-content:space-between;gap:16px;align-items:center;text-align:center"><div style="flex:1"><div class="player-big">{esc(cur["home_name"])}</div><div class="team-small">{esc(cur["home_team"])}</div></div><div style="font-size:1.5rem;font-weight:900;color:#94a3b8">VS</div><div style="flex:1"><div class="player-big">{esc(cur["away_name"])}</div><div class="team-small">{esc(cur["away_team"])}</div></div></div></div>',unsafe_allow_html=True)
    render_match_context(cur)
    if fmt in ("league3_final","league4_final","league5_final") and cur.get("stage")=="LEAGUE":
        pending_league=[x for x in b.get("matches",[]) if x.get("stage")=="LEAGUE" and x.get("home_score") is None and str(x.get("match_status") or "pending")!="skipped"]
        if len(pending_league)==1:
            check=db.can_skip_match(tid,int(cur["match_no"]))
            if check.get("allowed"):
                finals=" i ".join(check.get("finalists") or [])
                st.info(f"⏭️ Ten mecz nie może już zmienić pary finalistów{f': {finals}' if finals else ''}. Możesz go rozegrać albo pominąć.")
                if st.button("⏭️ POMIŃ MECZ",use_container_width=True,key=f"skip_{tid}_{cur['match_no']}"):
                    try:db.skip_match(tid,int(cur["match_no"]));rf()
                    except ValueError as e:st.error(str(e))
    defer_check=db.can_defer_match(tid,int(cur["match_no"]))
    if defer_check.get("allowed"):
        nxt_label=f"{defer_check.get('next_home','?')} vs {defer_check.get('next_away','?')}"
        st.caption(f"🕒 Nie możecie teraz zagrać? Ten mecz można przesunąć na później. Teraz wskoczy **{nxt_label}**.")
        if st.button("🕒 PRZESUŃ MECZ NA PÓŹNIEJ",use_container_width=True,key=f"defer_{tid}_{cur['match_no']}"):
            try:
                db.defer_match(tid,int(cur["match_no"]));rf()
            except ValueError as e:st.error(str(e))
    score_form(tid,cur,fmt)
    nxt=db.next_ready_match_from(b["matches"],int(cur["match_no"]),meta.get("extra") or {})
    if nxt:st.caption(f"Następny: **{nxt['home_name']} vs {nxt['away_name']}**")
    if st.button("↩️ Cofnij ostatni wynik / pominięcie",use_container_width=True,key=f"undo_{tid}_{cur['match_no']}"):
        st.session_state.pop("pending_ko",None);db.undo_last_result(tid);rf()
    tables=db.standings(tid)
    if tables:
        st.divider()
        if "L" in tables:st.subheader("Tabela ligowa");st.dataframe(standings_df(tables["L"]),hide_index=True,use_container_width=True)
        else:
            c1,c2=st.columns(2)
            with c1:st.subheader("Grupa A");st.dataframe(standings_df(tables["A"]),hide_index=True,use_container_width=True)
            with c2:st.subheader("Grupa B");st.dataframe(standings_df(tables["B"]),hide_index=True,use_container_width=True)



DE_FORMATS={"double4","double5","double6","double7","double8"}


def _de_bracket_layout(fmt:str) -> dict:
    """Visual rounds for the supported single-final Double Elimination formats."""
    return {
        "double4": {"wb":[[1,2],[4]], "lb":[[3],[5]], "final":[6]},
        "double5": {"wb":[[1,2],[3],[5]], "lb":[[4],[6],[7]], "final":[8]},
        "double6": {"wb":[[1,2],[3,4],[7]], "lb":[[5],[6],[8],[9]], "final":[10]},
        "double7": {"wb":[[1,2,3],[4,5],[9]], "lb":[[6],[7,8],[10],[11]], "final":[12]},
        "double8": {"wb":[[1,2,3,4],[5,6],[11]], "lb":[[7,8],[9,10],[12],[13]], "final":[14]},
    }.get(fmt,{"wb":[],"lb":[],"final":[]})


def _de_path_labels(fmt:str) -> dict[int,str]:
    """Human-readable next steps. Dynamic DE5/DE7 draws intentionally stay descriptive until resolved."""
    return {
        "double4": {
            1:"W → M4  •  P → M3", 2:"W → M4  •  P → M3", 3:"W → M5  •  P → odpada",
            4:"W → FINAŁ M6  •  P → M5", 5:"W → FINAŁ M6  •  P → odpada", 6:"🏆 Mistrz",
        },
        "double5": {
            1:"W → M3/M5 (losowanie)  •  P → M4", 2:"W → M3/M5 (losowanie)  •  P → M4",
            3:"W → M5  •  P → M6", 4:"W → M6  •  P → odpada", 5:"W → FINAŁ M8  •  P → M7",
            6:"W → M7  •  P → odpada", 7:"W → FINAŁ M8  •  P → odpada", 8:"🏆 Mistrz",
        },
        "double6": {
            1:"W → M3  •  P → M5", 2:"W → M4  •  P → M5", 3:"W → M7  •  P → M6",
            4:"W → M7  •  P → M8", 5:"W → M6  •  P → odpada", 6:"W → M8  •  P → odpada",
            7:"W → FINAŁ M10  •  P → M9", 8:"W → M9  •  P → odpada", 9:"W → FINAŁ M10  •  P → odpada", 10:"🏆 Mistrz",
        },
        "double7": {
            1:"W → M4/M5 (losowanie)  •  P → M6/M7", 2:"W → M4/M5 (losowanie)  •  P → M6/M7",
            3:"W → M4/M5 (losowanie)  •  P → M6/M7", 4:"W → M9  •  P → M7/M8", 5:"W → M9  •  P → M7/M8",
            6:"W → M8  •  P → odpada", 7:"W → M10  •  P → odpada", 8:"W → M10  •  P → odpada",
            9:"W → FINAŁ M12  •  P → M11", 10:"W → M11  •  P → odpada", 11:"W → FINAŁ M12  •  P → odpada", 12:"🏆 Mistrz",
        },
        "double8": {
            1:"W → M5/M6 (losowanie)  •  P → M7", 2:"W → M5/M6 (losowanie)  •  P → M7",
            3:"W → M5/M6 (losowanie)  •  P → M8", 4:"W → M5/M6 (losowanie)  •  P → M8",
            5:"W → M11  •  P → M10", 6:"W → M11  •  P → M9", 7:"W → M9  •  P → odpada",
            8:"W → M10  •  P → odpada", 9:"W → M12  •  P → odpada", 10:"W → M12  •  P → odpada",
            11:"W → FINAŁ M14  •  P → M13", 12:"W → M13  •  P → odpada", 13:"W → FINAŁ M14  •  P → odpada", 14:"🏆 Mistrz",
        },
    }.get(fmt,{})


def _de_round_title(lane:str, idx:int, count:int) -> str:
    if lane=="wb":
        return "FINAŁ WINNERS" if idx==count-1 else ("1. RUNDA WINNERS" if idx==0 else f"RUNDA {idx+1} WINNERS")
    if lane=="lb":
        return "FINAŁ LOSERS" if idx==count-1 else ("1. RUNDA LOSERS" if idx==0 else f"RUNDA {idx+1} LOSERS")
    return "WIELKI FINAŁ"


def _de_lucky_match_labels(b:dict,fmt:str) -> dict[int,dict[str,str]]:
    """Lucky-pass badges keyed by the *single match where the player enters after the bye*.

    A player must not carry the badge through every later card in the bracket.  The marker
    belongs only to the first match reached thanks to the lucky pass.
    """
    labels:dict[int,dict[str,str]]={}
    meta=b.get("meta") or {}; draw=meta.get("draw") or {}; slots=draw.get("slots") or {}; extra=meta.get("extra") or {}
    matches=b.get("matches",[]) or []

    def add(match_no:int,pid,txt:str):
        if pid:
            labels.setdefault(int(match_no),{})[str(pid)]=txt

    if fmt=="double5":
        # Slot E skips the opening round and enters directly in M3.
        add(3,slots.get("E"),"🎟️ SZCZĘŚLIWY LOS • wolny los w 1. rundzie Winners")
    elif fmt=="double6":
        # E and F enter the two Winners semifinals directly.
        add(3,slots.get("E"),"🎟️ SZCZĘŚLIWY LOS • wolny los w 1. rundzie Winners")
        add(4,slots.get("F"),"🎟️ SZCZĘŚLIWY LOS • wolny los w 1. rundzie Winners")
    elif fmt=="double7":
        # G skips round one. The post-R1 draw decides whether G lands in M4 or M5,
        # so locate the resolved card instead of marking the player globally.
        g=slots.get("G")
        if g:
            target=next((int(m.get("match_no") or 0) for m in matches
                         if int(m.get("match_no") or 0) in (4,5)
                         and str(g) in (str(m.get("home_player_id") or ""),str(m.get("away_player_id") or ""))),None)
            if target:add(target,g,"🎟️ SZCZĘŚLIWY LOS • wolny los w 1. rundzie Winners")

        # One loser of M1-M3 also skips the first Losers match and enters directly in M7.
        if extra.get("d7_lb_bye_match"):
            try:
                lucky_no=int(extra.get("d7_lb_bye_match"))
                mm={int(m["match_no"]):m for m in matches}
                src=mm.get(lucky_no)
                if src and src.get("winner_player_id"):
                    loser=src.get("away_player_id") if src.get("winner_player_id")==src.get("home_player_id") else src.get("home_player_id")
                    add(7,loser,"🍀 SZCZĘŚLIWY LOS • wolny los w 1. rundzie Losers")
            except Exception:
                pass
    return labels


def _de_bracket_match_card(m:dict,fmt:str,cur_no:int|None,path_label:str,lucky_labels:dict[str,str]|None=None,abandoned:bool=False) -> str:
    no=int(m["match_no"]); skipped=str(m.get("match_status") or "pending")=="skipped"; played=m.get("home_score") is not None
    ready=bool(m.get("home_player_id") and m.get("away_player_id")) and not played and not skipped
    if skipped: state="skipped"; badge="POMINIĘTY"
    elif played: state="played"; badge=result_text(m)
    elif abandoned: state="locked"; badge="NIE ROZEGRANO"
    elif cur_no==no: state="current"; badge="TERAZ"
    elif ready: state="ready"; badge="GOTOWY"
    else: state="locked"; badge="CZEKA"

    lucky_labels=lucky_labels or {}
    winner=str(m.get("winner_player_id") or "")
    def player_html(side:str)->str:
        pid=m.get(f"{side}_player_id")
        if not pid:return ""
        name=esc(m.get(f"{side}_name") or "?")
        team=esc(m.get(f"{side}_team") or "")
        result_cls=" winner" if played and str(pid)==winner else (" loser" if played and winner else "")
        lucky=lucky_labels.get(str(pid))
        lucky_html=f"<span class='lucky-pill'>{esc(lucky)}</span>" if lucky else ""
        return f"<div class='de-player{result_cls}'><span class='de-name'>{name}</span>{f'<small>{team}</small>' if team else ''}{lucky_html}</div>"

    if m.get("home_player_id") and m.get("away_player_id"):
        h=player_html("home"); a=player_html("away")
    else:
        ph=source_placeholder(fmt,no); parts=[x.strip() for x in ph.split("—",1)]
        h=f"<div class='de-player placeholder'><span class='de-name'>{esc(parts[0] if parts else ph)}</span></div>"
        a=f"<div class='de-player placeholder'><span class='de-name'>{esc(parts[1] if len(parts)>1 else 'do ustalenia')}</span></div>"

    bonus="<div class='de-bonus'>⭐ Winners Bracket zaczyna Wielki Finał od 1:0</div>" if m.get("stage")=="FINAL" else ""
    # Split the path into two visually distinct directions instead of one tiny line of text.
    path_parts=[x.strip() for x in str(path_label or "").split("•") if x.strip()]
    path_html="".join(f"<span>{esc(x)}</span>" for x in path_parts)
    return f"""
      <div class="de-match {state}">
        <div class="de-head"><span>M{no}</span><b>{esc(stage_name(m))}</b><em>{esc(badge)}</em></div>
        {h}
        <div class="de-vs">VS</div>
        {a}
        {bonus}
        <div class="de-path">{path_html}</div>
      </div>
    """


def render_de_bracket(t:dict,b:dict,fmt:str,cur_no:int|None):
    """One compact left-to-right Double Elimination map. Fixed layout on every device."""
    layout=_de_bracket_layout(fmt); by_no={int(m["match_no"]):m for m in b["matches"]}; paths=_de_path_labels(fmt)
    if not layout.get("final"):
        st.info("Brak widoku drzewka dla tego formatu.");return

    wb=layout.get("wb") or []; lb=layout.get("lb") or []; max_rounds=max(len(wb),len(lb),1)
    lucky_by_match=_de_lucky_match_labels(b,fmt)
    abandoned=str(t.get("status") or "")=="abandoned"
    st.caption("Jedno drzewko całego Double Elimination. W = zwycięzca • P = przegrany. Szczęśliwy los jest oznaczony tylko przy meczu, do którego gracz wszedł dzięki wolnemu losowi.")

    def lane_html(lane:str,rounds_list:list[list[int]])->str:
        accent="#178a57" if lane=="wb" else "#c54848"
        title="WINNERS BRACKET" if lane=="wb" else "LOSERS BRACKET"
        icon="🌿" if lane=="wb" else "🩸"
        pieces=[f"<section class='lane {lane}'><div class='lane-title' style='--accent:{accent}'><span>{icon}</span>{title}</div><div class='lane-grid'>"]
        # Keep the rounds adjacent. The previous version spread a 3-round Winners path
        # over a 4-column Losers canvas, which visually created a fake missing round.
        for idx,nos in enumerate(rounds_list):
            pieces.append(f"<div class='round'><div class='round-title'>{esc(_de_round_title(lane,idx,len(rounds_list)))}</div><div class='round-stack'>")
            for no in nos:
                m=by_no.get(no)
                if m:pieces.append(_de_bracket_match_card(m,fmt,cur_no,paths.get(no,""),lucky_by_match.get(no,{}),abandoned))
            pieces.append("</div></div>")
        pieces.append("</div></section>")
        return "".join(pieces)

    final_html=[]
    for no in layout["final"]:
        m=by_no.get(no)
        if m:final_html.append(_de_bracket_match_card(m,fmt,cur_no,paths.get(no,""),lucky_by_match.get(no,{}),abandoned))

    # 4 DE rounds + Grand Final now fit inside a normal desktop viewport; phones keep
    # the exact same left-to-right map and simply scroll horizontally.
    col_w=174; gap=12; final_w=188
    width=max(690,max_rounds*col_w+(max_rounds-1)*gap+final_w+72)
    height={"double4":650,"double5":720,"double6":790,"double7":860,"double8":930}.get(fmt,800)
    html_doc=f"""
    <!doctype html><html><head><meta charset='utf-8'><style>
    *{{box-sizing:border-box}} html,body{{margin:0;padding:0;background:transparent;font-family:Inter,ui-sans-serif,system-ui,-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;color:#202532}}
    .scroll{{overflow-x:auto;padding:2px 2px 12px;scrollbar-width:thin}}
    .board{{width:{width}px;max-width:none;background:#f8fafc;border:1px solid #e1e6ed;border-radius:18px;padding:14px;box-shadow:0 7px 22px rgba(15,23,42,.05)}}
    .main{{display:grid;grid-template-columns:minmax(0,1fr) {final_w}px;gap:14px;align-items:stretch}}
    .routes{{min-width:0}}
    .lane{{position:relative;padding:10px 8px 14px;border-radius:15px;border:1px solid transparent}}
    .lane.wb{{background:linear-gradient(90deg,#f2faf6,#f8fbfa);border-color:#dcefe5}}
    .lane.lb{{background:linear-gradient(90deg,#fff6f6,#fbf8f8);border-color:#f0dddd;margin-top:14px}}
    .lane-title{{display:flex;align-items:center;gap:7px;color:var(--accent);font-size:11px;font-weight:950;letter-spacing:.08em;margin:0 2px 10px}}
    .lane-title:after{{content:'';height:1px;flex:1;background:color-mix(in srgb,var(--accent) 24%,transparent)}}
    .lane-grid{{display:grid;grid-template-columns:repeat({max_rounds},{col_w}px);gap:{gap}px;align-items:stretch}}
    .round{{position:relative;display:flex;flex-direction:column;justify-content:center;min-width:0}}
    .round + .round:before{{content:'›';position:absolute;left:-17px;top:50%;transform:translateY(-50%);width:18px;height:18px;border-radius:50%;display:flex;align-items:center;justify-content:center;background:#fff;border:1px solid #d7dde6;color:#768091;font-size:16px;font-weight:900;z-index:4;box-shadow:0 2px 5px rgba(15,23,42,.05)}}
    .round-title{{text-align:center;font-size:9px;font-weight:900;letter-spacing:.065em;color:#697383;text-transform:uppercase;margin-bottom:6px;min-height:22px;display:flex;align-items:flex-end;justify-content:center}}
    .round-stack{{display:flex;flex-direction:column;justify-content:center;gap:8px;height:100%}}
    .de-match{{position:relative;background:#fff;border:1px solid #d8dee7;border-radius:11px;padding:8px 9px;box-shadow:0 3px 9px rgba(15,23,42,.05);min-height:100px}}
    .de-match.played{{border-left:4px solid #7d8797}} .de-match.current{{border:2px solid #19a463;box-shadow:0 0 0 3px rgba(25,164,99,.10)}}
    .de-match.ready{{border-left:4px solid #e0a92d}} .de-match.locked{{opacity:.58;background:#f7f9fb}} .de-match.skipped{{opacity:.62}}
    .de-head{{display:grid;grid-template-columns:auto 1fr auto;gap:4px;align-items:center;font-size:8px;margin-bottom:6px;color:#6f7785}}
    .de-head span{{font-weight:1000;color:#343a46}} .de-head b{{text-align:center;font-size:8px;text-transform:uppercase}} .de-head em{{font-style:normal;font-weight:950;font-size:8px;color:#343a46}}
    .de-player{{border-radius:8px;padding:3px 4px;margin:-1px -3px;color:#242a35;line-height:1.1}}
    .de-player.winner{{background:#eef9f3}} .de-player.loser{{opacity:.68}}
    .de-name{{display:block;font-weight:900;font-size:11px;overflow-wrap:anywhere}}
    .de-player small{{display:block;font-size:8px;font-weight:650;color:#7b8390;margin-top:2px;overflow-wrap:anywhere}}
    .de-player.placeholder{{background:#f4f6f8;color:#697383}}
    .de-vs{{font-size:7px;font-weight:900;color:#a0a6b0;margin:2px 3px}}
    .lucky-pill{{display:inline-block;margin-top:4px;padding:3px 5px;border-radius:999px;background:#fff4bf;border:1px solid #edd16b;color:#825f00;font-size:7px;font-weight:950;line-height:1.15}}
    .de-path{{margin-top:6px;padding-top:5px;border-top:1px dashed #e0e4ea;display:flex;gap:4px;flex-wrap:wrap}}
    .de-path span{{padding:2px 4px;border-radius:5px;background:#f2f4f7;font-size:7px;font-weight:850;color:#697383;line-height:1.2}}
    .de-bonus{{font-size:7px;font-weight:900;color:#9a6b00;background:#fff8df;border-radius:6px;padding:4px 5px;margin-top:4px}}
    .drop{{display:flex;align-items:center;gap:7px;margin:7px 7px -7px;color:#945d68;font-size:8px;font-weight:900;letter-spacing:.02em}}
    .drop:before,.drop:after{{content:'';height:1px;background:#ead9dd;flex:1}}
    .lucky-note{{margin:9px 8px 0;padding:6px 8px;border:1px solid #ecd47b;background:#fff9df;border-radius:9px;color:#785a00;font-size:8px;line-height:1.3}}
    .lucky-note.muted{{color:#8b7a40;background:#fffdf2}}
    .final{{display:flex;flex-direction:column;justify-content:center;align-self:stretch;background:linear-gradient(180deg,#fff8df,#fffdf5);border:1px solid #e5c85e;border-radius:15px;padding:10px;position:relative;box-shadow:inset 0 0 0 1px rgba(255,255,255,.7)}}
    .final:before{{content:'›';position:absolute;left:-8px;top:50%;transform:translate(-50%,-50%);width:22px;height:22px;border-radius:50%;display:flex;align-items:center;justify-content:center;background:#fff5c8;border:1px solid #dfbd40;color:#9a7000;font-size:18px;font-weight:900;z-index:5}}
    .final-title{{text-align:center;font-size:11px;font-weight:1000;letter-spacing:.07em;color:#8f6800;margin-bottom:8px}}
    .final .de-match{{border-color:#dfc36a;box-shadow:0 4px 12px rgba(135,98,0,.10)}}
    .legend{{display:flex;gap:10px;flex-wrap:wrap;margin-top:10px;font-size:8px;color:#747c89}}
    .dot{{display:inline-block;width:7px;height:7px;border-radius:50%;margin-right:3px}} .green{{background:#19a463}} .amber{{background:#e0a92d}} .grey{{background:#7d8797}}
    @media(max-width:700px){{.board{{padding:10px}}}}
    </style></head><body>
    <div class='scroll'><div class='board'><div class='main'><div class='routes'>
    {lane_html('wb',wb)}
    <div class='drop'>↓ przegrani z Winners trafiają do Losers ↓</div>
    {lane_html('lb',lb)}
    </div><aside class='final'><div class='final-title'>🏆 WIELKI FINAŁ</div>{''.join(final_html)}</aside></div>
    <div class='legend'><span><i class='dot green'></i>TERAZ</span><span><i class='dot amber'></i>GOTOWY</span><span><i class='dot grey'></i>ROZEGRANY</span><span>🎟️ / 🍀 szczęśliwy los</span></div>
    </div></div></body></html>
    """
    components.html(html_doc,height=height,scrolling=True)
    st.caption("Drzewko pokazuje logiczną drogę przez DE. Faktyczną kolejność grania nadal najlepiej śledzić w widoku Lista.")

def _render_match_scorer_details(tid:str,m:dict,no:int):
    """Expandable match details used in both the live schedule and tournament archive."""
    scorers=db.match_scorers(tid,no)
    home=[x for x in scorers if x.get("side")=="home"]
    away=[x for x in scorers if x.get("side")=="away"]
    label=f"⚽ Szczegóły meczu {no} • {m.get('home_name') or '?'} – {m.get('away_name') or '?'}"
    with st.expander(label,expanded=False):
        c1,c2=st.columns(2)
        with c1:
            st.markdown(f"**{esc(m.get('home_name') or '—')}** · {esc(m.get('home_team') or '—')}")
            if home:
                for x in home:st.write(f"⚽ {x.get('scorer_name')}"+(f" ×{int(x.get('goals') or 0)}" if int(x.get('goals') or 0)>1 else ""))
            else:st.caption("Brak zapisanych strzelców.")
        with c2:
            st.markdown(f"**{esc(m.get('away_name') or '—')}** · {esc(m.get('away_team') or '—')}")
            if away:
                for x in away:st.write(f"⚽ {x.get('scorer_name')}"+(f" ×{int(x.get('goals') or 0)}" if int(x.get('goals') or 0)>1 else ""))
            else:st.caption("Brak zapisanych strzelców.")
        if m.get("home_pen") is not None or m.get("away_pen") is not None:
            st.caption(f"Karne: {int(m.get('home_pen') or 0)}:{int(m.get('away_pen') or 0)}")

def render_schedule(t):
    b=db.bundle(t["id"]);fmt=b["meta"]["format_key"];extra=b["meta"].get("extra") or {};st.subheader("📅 Terminarz")
    abandoned=str(t.get("status") or "")=="abandoned"
    cur=None if abandoned else db.current_match_from(b["matches"],extra)
    cur_no=int(cur["match_no"]) if cur else None
    if fmt in DE_FORMATS:
        view=st.segmented_control("Widok terminarza",["📋 Lista","🌳 Drzewko"],default="📋 Lista",key=f"de_schedule_view_{t['id']}",label_visibility="collapsed") or "📋 Lista"
        if view=="🌳 Drzewko":
            render_de_bracket(t,b,fmt,cur_no);return
    matches=db.live_schedule_from(b["matches"],extra)
    ready_pending=[] if abandoned else [m for m in matches if m.get("home_player_id") and m.get("away_player_id") and m.get("home_score") is None and str(m.get("match_status") or "pending")!="skipped"]
    next_no=int(ready_pending[1]["match_no"]) if len(ready_pending)>1 and cur_no is not None and int(ready_pending[0]["match_no"])==cur_no else None
    if cur_no is not None:
        st.caption("Kolejność jest aktualizowana po każdym wyniku. Gotowe mecze są ustawiane zgodnie z faktyczną kolejnością gry, a zablokowane spotkania przesuwają się po ustaleniu uczestników.")
    milestone_by_match={}
    if not int(t.get("is_test") or 0):
        for x in db.milestones_in_tournament(t["id"]):
            if x.get("match_no") is not None:
                milestone_by_match.setdefault(int(x["match_no"]),[]).append(x)
    for m in matches:
        no=int(m["match_no"]);skipped=str(m.get("match_status") or "pending")=="skipped"
        played=m.get("home_score") is not None
        ready=bool(m.get("home_player_id") and m.get("away_player_id")) and not played and not skipped
        if m.get("home_player_id"):
            names=f"{esc(m['home_name'])} — {esc(m['away_name'])}"
            if skipped:result="POMINIĘTY";icon="⏭️";live_tag=" • POMINIĘTY"
            elif played:result=result_text(m);icon="✅";live_tag=""
            elif abandoned:result="NIE ROZEGRANO";icon="⚪";live_tag=""
            elif no==cur_no:result="—";icon="▶️";live_tag=" • TERAZ"
            elif no==next_no:result="—";icon="⏭️";live_tag=" • NASTĘPNY"
            else:result="—";icon="⏳";live_tag=" • GOTOWY" if ready else ""
        else:
            names=source_placeholder(fmt,no);result=("NIE ROZEGRANO" if abandoned else "—");icon=("⚪" if abandoned else "🔒");live_tag=("" if abandoned else " • CZEKA NA ROZSTRZYGNIĘCIE")
        bonus=" • START 1:0 DLA WINNERS" if fmt in ("double4","double5","double6","double7","double8") and m["stage"]=="FINAL" else ""
        tags=milestone_by_match.get(no,[])
        milestone_tag=(" • "+" • ".join(f"{x.get('icon','💎')} {x.get('title')}" for x in tags)) if tags else ""
        st.markdown(f'<div class="mini-card"><span class="match-no">{icon} MECZ {no} • {stage_name(m)}{esc(live_tag)}{bonus}{esc(milestone_tag)}</span><br><b>{names}</b><span style="float:right" class="scoreline">{esc(result)}</span></div>',unsafe_allow_html=True)
        if skipped:st.caption("Pominięty mecz nie jest zapisany jako 0:0 i nie wchodzi do żadnych statystyk.")
        elif played:_render_match_scorer_details(t["id"],m,no)



def render_stats(t=None,readonly:bool=False):
    st.subheader("📊 Statystyki wszech czasów")
    st.caption("Oficjalne mecze, turnieje i 1 vs 1. Rozegrane mecze z niedokończonego oficjalnego turnieju nadal liczą się do statystyk meczowych i Awards, ale taki turniej nie daje mistrza, podium ani tytułu.")
    stats=db.all_time_stats()
    if not stats:
        st.info("Brak rozegranych oficjalnych meczów. Historia testów nadal jest dostępna poniżej.")
        render_tournament_archive(readonly=readonly)
        return
    tab1,tab_records,tab_players,tab_misc,tab_finance,tab_history=st.tabs(["🏆 Ranking","🏛️ Rekordy","👤 Gracze","⚽ Drużyny i strzelcy","💸 Rozliczenia","🗂️ Historia"])
    ach=db.achievement_center();players_ach=ach.get("players") or []
    ms=db.global_milestones();timeline=ms.get("timeline") or []
    tab_teams=tab_misc;tab_scorers=tab_misc
    with tab1:
        leader=stats[0];c1,c2,c3,c4=st.columns(4);c1.metric("🐐 Lider",leader["name"]);c2.metric("🏆 Tytuły",leader["titles"]);tg=max(stats,key=lambda x:x["gf"]);c3.metric("⚽ Król bramek",tg["name"],f"{tg['gf']} goli");tw=max(stats,key=lambda x:x["w"]);c4.metric("🔥 Najwięcej wygranych",tw["name"],f"{tw['w']} W")
        df=pd.DataFrame([{"#":i+1,"Gracz":s["name"],"Turnieje":s["tournaments"],"1v1":s.get("duels",0),"🏆":s["titles"],"Finały":s["finals"],"M":s["matches"],"W":s["w"],"R":s["d"],"P":s["l"],"Bramki":f'{s["gf"]}:{s["ga"]}',"+/-":s["gd"],"W%":s["win_pct"],"Karne W":s["pen_wins"]} for i,s in enumerate(stats)]);st.dataframe(df,hide_index=True,use_container_width=True)
        st.markdown("#### 🔥 Aktualna forma — ostatnie 5 oficjalnych meczów")
        forms=db.recent_forms()
        if forms:
            best=forms[0];st.success(f"Najlepsza aktualna forma: **{best['name']} — {' '.join(best['form'])}**")
            st.dataframe(pd.DataFrame([{"Gracz":x["name"],"Forma":" ".join(x["form"]),"W":x["w"],"R":x["d"],"P":x["l"]} for x in forms]),hide_index=True,use_container_width=True)
    with tab_records:
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
    with tab_teams:
        st.markdown("### 👥 Drużyny")
        st.caption("Statystyki drużynowe i rating niezależne od profili graczy.")
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
            ratings=db.live_team_ratings()
            if ratings:
                st.markdown("#### 📡 Live Team Rating")
                st.caption("Rating aktualizuje się z wynikami; mała próbka jest przyciągana do neutralnych 50 pkt, a nowsze mecze ważą trochę więcej.")
                st.dataframe(pd.DataFrame([{"Drużyna":x["team"],"Rating":x["rating"],"M":x["matches"],"W%":x["win_pct"],"Bramki":f"{x['gf']}:{x['ga']}"} for x in ratings]),hide_index=True,use_container_width=True)
    with tab_players:
        st.markdown("### 👤 Profil i historia gracza")
        opts={p["name"]:p["player_id"] for p in stats};names=list(opts)
        selected=st.selectbox("Gracz",names,key="player_profile_select")
        profile=db.player_profile(opts[selected])
        if profile:
            c1,c2,c3,c4=st.columns(4)
            c1.metric("🏆 Tytuły",profile["titles"]);c2.metric("🏁 Finały",profile["finals"]);c3.metric("🔥 Wygrane",profile["w"],f"{profile['win_pct']}%")
            c4.metric("⚽ Bramki",profile["gf"],f"{profile['gd']:+d} bilans")
            st.caption("Forma — ostatnie 5: **"+" ".join(profile.get("form") or [])+"**" if profile.get("form") else "Brak ostatnich meczów")
            st.markdown("#### 🏆 Gablota")
            selected_pid=str(opts[selected]);pa_profile=next((x for x in players_ach if str(x.get("player_id"))==selected_pid),{})
            tc1,tc2,tc3=st.columns(3)
            tc1.metric("🏆 Tytuły",profile["titles"]);tc2.metric("🥈 Finały",profile["finals"]);tc3.metric("🏅 Odznaki",f"{pa_profile.get('count',0)}/{pa_profile.get('total',len(ach.get('catalog') or []))}")
            awards_won=db.player_award_wins(selected_pid)
            if awards_won:
                st.markdown("**FIFA Night Awards:** " + " • ".join(f"{x['title']} {x['year']}" for x in awards_won))
            badges=pa_profile.get("unlocked") or []
            if badges:
                st.markdown("#### 🏅 Odznaki")
                bcols=st.columns(2)
                for i,a in enumerate(badges):
                    with bcols[i%2]:
                        with st.expander(f"{a.get('icon','🏅')} {a.get('name','Odznaka')}",expanded=False):
                            st.write(a.get("desc") or "—")
                            date=str(a.get("earned_at") or "")[:10] or "—"
                            where=f"FIFA Night #{a.get('tournament_no')}" if a.get("tournament_no") else "oficjalny mecz"
                            if a.get("match_no") is not None:where+=f" • mecz {a.get('match_no')}"
                            detail=(" • "+str(a.get("detail"))) if a.get("detail") else ""
                            st.caption(f"Zdobyta: {date} • {where}{detail}")
            else:
                st.caption("Brak odblokowanych odznak.")
            locked_badges=pa_profile.get("locked") or []
            if locked_badges:
                with st.expander("🔒 Odznaki do zdobycia",expanded=False):
                    st.dataframe(pd.DataFrame([{"Odznaka":f"{a.get('icon','🏅')} {a.get('name','')}","Za co":a.get("desc") or "—","Postęp":a.get("progress","—")} for a in locked_badges]),hide_index=True,use_container_width=True)
            moments=[x for x in timeline if selected.casefold() in str(x.get("detail") or "").casefold()]
            if moments:
                with st.expander("💎 Ważne momenty w historii FIFA Night",expanded=False):
                    for x in reversed(moments[-12:]):
                        st.write(f"{x.get('icon','💎')} **{x.get('title')}** — {x.get('detail') or '—'}")
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

    with tab_scorers:
        st.divider()
        st.markdown("### ⚽ Strzelcy")
        st.caption("Zbiorcze statystyki strzelców ze wszystkich oficjalnych rozgrywek.")
        scorers=db.scorer_stats()
        if not scorers:st.info("Brak zapisanych strzelców w oficjalnych turniejach.")
        else:
            df=pd.DataFrame([{"#":i+1,"Zawodnik":x["name"],"Gole":x["goals"],"Mecze z golem":x["matches_scored"],"Drużyny":x["teams"]} for i,x in enumerate(scorers)])
            st.dataframe(df,hide_index=True,use_container_width=True)

        if not readonly:
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
        else:
            st.caption("Tryb podglądu — edycja list zawodników jest dostępna na urządzeniu ze sterowaniem.")

    with tab_history:
        render_tournament_archive(readonly=readonly)

    with tab_finance:
        st.markdown("### 💸 Rozliczenia rozgrywek")
        st.caption("Każdy uczestnik oznaczony „Gra za kasę” wpłaca stawkę. W 1v1 mecz jest płatny tylko wtedy, gdy obaj grają za kasę. W turniejach niewypłacony jackpot przechodzi do następnego płatnego oficjalnego turnieju.")

        st.markdown("#### 📈 Ranking finansowy")
        finance=db.financial_ranking()
        if finance:
            best=finance[0]
            worst=min(finance,key=lambda x:(int(x.get("balance_cents") or 0),str(x.get("name") or "")))
            c1,c2=st.columns(2)
            best_amount=int(best.get("balance_cents") or 0); worst_amount=int(worst.get("balance_cents") or 0)
            best_sign="+" if best_amount>0 else ""; worst_sign="+" if worst_amount>0 else ""
            c1.metric("💰 Najbardziej na plus",f"{best.get('name')} • {best_sign}{pln_cents(best_amount)} zł")
            c2.metric("📉 Najbardziej na minus",f"{worst.get('name')} • {worst_sign}{pln_cents(worst_amount)} zł")
            finance_rows=[]
            for i,row in enumerate(finance,1):
                amount=int(row.get("balance_cents") or 0); sign="+" if amount>0 else ""
                finance_rows.append({
                    "#":i,
                    "Gracz":row.get("name"),
                    "Bilans":f"{sign}{pln_cents(amount)} zł",
                    "Wygrane":f"{pln_cents(row.get('won_cents') or 0)} zł",
                    "Wpłacone":f"{pln_cents(row.get('paid_cents') or 0)} zł",
                    "Płatne rozgrywki":int(row.get("paid_tournaments") or 0),
                    "Wygrane rozgrywki":int(row.get("wins") or 0),
                })
            st.dataframe(pd.DataFrame(finance_rows),hide_index=True,use_container_width=True)
            st.caption("Ranking liczy płatne oficjalne rozgrywki, także 1v1 i wydarzenia już oznaczone jako rozliczone. Jackpot dotyczy wyłącznie turniejów.")
        else:
            st.info("Ranking finansowy pojawi się po zakończeniu pierwszej płatnej oficjalnej rozgrywki.")

        if readonly:
            current_jackpot=db.current_jackpot_cents()
            if current_jackpot>0:st.warning(f"🎰 Aktualny jackpot: **{pln_cents(current_jackpot)} zł**")
            st.caption("Tryb podglądu — bieżące rozliczenia i ich edycja są dostępne tylko na urządzeniu ze sterowaniem.")
            return

        st.divider()
        st.markdown("#### 💳 Bieżące rozliczenie")
        st.caption("Wybierz kilka nierozliczonych rozgrywek, a aplikacja skompensuje wzajemne należności i poda najkrótszą listę końcowych przelewów.")
        current_jackpot=db.current_jackpot_cents()
        if current_jackpot>0:st.warning(f"🎰 Aktualny jackpot do następnego płatnego oficjalnego turnieju: **{pln_cents(current_jackpot)} zł**")
        recent=db.settlement_tournaments(100)
        if not recent:
            st.info("Brak zakończonych oficjalnych rozgrywek do rozliczenia.")
        else:
            by_id={x["id"]:x for x in recent}
            def settle_label(tid):
                x=by_id[tid]; raw=x.get("completed_at") or x.get("created_at") or ""; date=str(raw)[:10] or "—"
                if x.get("format_key")=="duel1v1":no="⚔️ 1v1"
                else:no=f"🏆 turniej #{x.get('official_no')}" if x.get("official_no") else "🏆 turniej"
                status="✅ rozliczony" if x.get("settled") else "🟠 nierozliczony"
                cash=f"{int(x.get('cash_count') or 0)}/{int(x.get('player_count') or 0)} za kasę"
                return f"{no} • {date} • {cash} • 🥇 {x.get('champion_name') or '?'} • {pln_cents(x['stake_cents'])} zł/os. • {status}"

            show_settled=st.toggle("Pokaż także rozliczone rozgrywki",value=False,key="settlement_show_settled")
            available=[x for x in recent if show_settled or not x.get("settled")]
            allowed_ids={x["id"] for x in available}
            positive_unsettled=[x["id"] for x in available if int(x.get("stake_cents") or 0)>0 and not x.get("settled")]
            default_ids=positive_unsettled[:min(4,len(positive_unsettled))]
            select_key="settlement_tournaments_select"
            if select_key not in st.session_state:
                st.session_state[select_key]=default_ids
            else:
                current=st.session_state.get(select_key) or []
                st.session_state[select_key]=[tid for tid in current if tid in allowed_ids]

            if available:
                selected=st.multiselect(
                    "Rozgrywki do wspólnego rozliczenia",
                    options=[x["id"] for x in available],
                    format_func=settle_label,
                    key=select_key,
                    placeholder="Wybierz 2, 3, 4 lub więcej rozgrywek",
                )
                st.caption("Domyślnie zaznaczam maksymalnie 4 ostatnie nierozliczone płatne rozgrywki. Możesz wybrać dowolny zestaw.")
            else:
                selected=[]
                st.success("✅ Wszystkie widoczne rozgrywki są już rozliczone.")

            with st.expander("✏️ Ustaw stawkę lub zmień status starej rozgrywki"):
                edit_tid=st.selectbox("Rozgrywka",options=[x["id"] for x in recent],format_func=settle_label,key="settlement_edit_tid")
                current_stake=float(by_id[edit_tid].get("stake_per_player") or 0)
                current_settled=bool(by_id[edit_tid].get("settled"))
                with st.form(f"settlement_edit_form_{edit_tid}"):
                    edit_stake=st.number_input("Stawka na osobę (zł)",min_value=0.0,value=current_stake,step=5.0,format="%.2f",key=f"settlement_edit_value_{edit_tid}")
                    edit_settled=st.checkbox("✅ Ten turniej jest już rozliczony",value=current_settled,key=f"settlement_edit_settled_{edit_tid}")
                    st.caption("Możesz uzupełnić stawkę starej rozgrywki i od razu oznaczyć ją jako rozliczoną.")
                    save_finance=st.form_submit_button("💾 ZAPISZ",use_container_width=True)
                if save_finance:
                    try:
                        db.set_tournament_finance(edit_tid,edit_stake,edit_settled)
                        st.success("Stawka i status rozliczenia zostały zapisane.")
                        rr()
                    except ValueError as e: st.error(str(e))

            if selected:
                settlement=db.settlement_summary(selected)
                used=settlement.get("tournaments") or []
                if not used:
                    st.warning("Wybrane rozgrywki nie mają jeszcze wpisanej dodatniej stawki.")
                else:
                    def event_label(x):
                        raw=x.get("completed_at") or x.get("created_at") or "";date=str(raw)[:10] or "—"
                        if x.get("format_key")=="duel1v1":kind="⚔️ 1v1"
                        else:kind=f"🏆 turniej #{x.get('official_no')}" if x.get("official_no") else "🏆 turniej"
                        cash=f"{int(x.get('cash_count') or 0)}/{int(x.get('player_count') or 0)} za kasę"
                        return f"{kind} • {date} • {cash} • 🥇 {x.get('champion_name') or '?'} • {pln_cents(x.get('stake_cents') or 0)} zł/os."
                    st.markdown("#### 📋 Rozgrywki objęte rozliczeniem")
                    used_ids={x["id"] for x in used}
                    selected_ids=set(selected)
                    for event in used:
                        suffix=" • 🎰 dodane automatycznie jako źródło jackpotu" if event["id"] not in selected_ids else ""
                        st.write(f"• **{event_label(event)}**{suffix}")
                    c1,c2=st.columns(2)
                    c1.metric("Łączna suma wpisowych",f"{pln_cents(settlement.get('total_pot_cents',0))} zł")
                    pending=int(settlement.get("pending_jackpot_cents") or 0)
                    consumed=max([int(x.get("jackpot_in_cents") or 0) for x in used] or [0])
                    if pending>0:c2.metric("🎰 Jackpot do przeniesienia",f"{pln_cents(pending)} zł")
                    elif consumed>0:c2.metric("🎰 Jackpot wykorzystany",f"{pln_cents(consumed)} zł")
                    else:c2.metric("🎰 Jackpot w tym zestawie","0,00 zł")

                    st.markdown("#### 💳 Kto komu przelewa")
                    transfers=settlement.get("transfers") or []
                    lines=[]
                    if transfers:
                        for tr in transfers:
                            text=f"{tr['from_name']} → {tr['to_name']}: {pln_cents(tr['amount_cents'])} zł"
                            st.success(f"💸 **{text}**");lines.append(text)
                        st.caption("Wzajemne należności są kompensowane — nie trzeba rozliczać każdej rozgrywki osobno.")
                        st.code("\n".join(lines),language=None)
                    elif pending>0:
                        st.warning("🎰 W tym zestawie część pieniędzy nie ma jeszcze odbiorcy — jackpot przechodzi do kolejnego płatnego oficjalnego turnieju.")
                    else:
                        st.success("✅ Po wybranych rozgrywkach nikt nikomu nic nie jest winien.")

                    st.markdown("#### ⚖️ Bilans wybranych rozgrywek")
                    balance_rows=[]
                    for row in settlement.get("balances") or []:
                        amount=int(row.get("balance_cents") or 0);sign="+" if amount>0 else ""
                        balance_rows.append({"Gracz":row.get("name"),"Bilans":f"{sign}{pln_cents(amount)} zł"})
                    if balance_rows:st.dataframe(pd.DataFrame(balance_rows),hide_index=True,use_container_width=True)

                    export_lines=["FIFA NIGHT — ROZLICZENIE","","ROZGRYWKI:"]+[f"- {event_label(x)}" for x in used]
                    export_lines += ["",f"WPISOWE: {pln_cents(settlement.get('total_pot_cents',0))} zł"]
                    if pending:export_lines.append(f"JACKPOT DO PRZENIESIENIA: {pln_cents(pending)} zł")
                    elif consumed:export_lines.append(f"JACKPOT WYKORZYSTANY: {pln_cents(consumed)} zł")
                    export_lines += ["","PRZELEWY:"] + ([f"- {line}" for line in lines] if lines else ["- brak"])+["","BILANS:"]
                    for row in settlement.get("balances") or []:
                        amount=int(row.get("balance_cents") or 0);sign="+" if amount>0 else ""
                        export_lines.append(f"- {row.get('name')}: {sign}{pln_cents(amount)} zł")
                    c1,c2=st.columns(2)
                    with c1:
                        st.download_button("⬇️ Rozliczenie TXT",data="\n".join(export_lines),file_name="fifa-night-rozliczenie.txt",mime="text/plain",use_container_width=True,key="settlement_txt_download")
                    with c2:
                        settlement_png=generate_settlement_png(settlement,[event_label(x) for x in used])
                        st.download_button("⬇️ Rozliczenie PNG 1080×1080",data=settlement_png,file_name="fifa-night-rozliczenie.png",mime="image/png",use_container_width=True,key="settlement_png_download")

                    unsettled_used=[str(x["id"]) for x in used if not x.get("settled")]
                    if unsettled_used:
                        st.caption("Gdy przelewy są już wykonane, oznacz te rozgrywki jako rozliczone. Znikną z domyślnej listy, ale nadal zostaną w rankingu finansowym.")
                        if st.button("✅ OZNACZ WYBRANE ROZGRYWKI JAKO ROZLICZONE",use_container_width=True,key="settlement_mark_selected_paid"):
                            changed=db.set_tournaments_settled(unsettled_used,True)
                            if changed:st.success(f"Oznaczono jako rozliczone: {changed} rozgrywki.")
                            rr()
                    else:
                        st.info("Te rozgrywki są już oznaczone jako rozliczone.")
            elif available:
                st.info("Wybierz rozgrywki, które chcesz razem rozliczyć.")




def render_global_milestones(readonly:bool=False):
    st.markdown("### 🏛️ Kamienie milowe FIFA Night")
    st.caption("Jubileusze całej historii FIFA Night: mecze, gole, zwycięstwa, turnieje, karne, czyste konta, hat-tricki i pierwsze historyczne wydarzenia.")
    ms=db.global_milestones()
    nxt=ms.get("next") or []
    if nxt:
        st.markdown("#### 🎯 Następne jubileusze")
        ncols=st.columns(min(4,len(nxt)))
        for i,x in enumerate(nxt):
            with ncols[i%len(ncols)]:
                st.metric(x["name"],f"{x['current']} / {x['target']}",f"zostało {x['left']}")
    timeline=ms.get("timeline") or []
    if timeline:
        st.markdown("#### 💎 Oś historii")
        grouped={}
        for x in reversed(timeline):
            when=fmt_history_datetime(x.get("earned_at"))
            day,time=(when.split(" ",1)+[""])[:2] if " " in when else (when,"")
            day=(day or "—").replace(".","-")
            grouped.setdefault(day,[]).append((time,x))
        for idx,(day,items) in enumerate(grouped.items()):
            with st.expander(f"📅 {day}",expanded=(idx==0)):
                for tm,x in items:
                    where=(f"FIFA Night #{x.get('tournament_no')}" if x.get("tournament_no") else "")
                    if x.get("match_no") is not None:where+=(" • " if where else "")+f"mecz {x.get('match_no')}"
                    place=f" • {where}" if where else ""
                    detail=f" — {x.get('detail')}" if x.get("detail") else ""
                    clock=f"**{tm}** • " if tm else ""
                    st.markdown(f"- {clock}{x.get('icon','💎')} **{x.get('title','Kamień milowy')}**{place}{detail}")
    else:
        st.info("Pierwsze kamienie milowe pojawią się po rozegraniu oficjalnych spotkań.")
    if ms.get("pending_goal_scorers") and not readonly:
        st.markdown("#### ⚽ Jubileuszowe gole do uzupełnienia")
        st.caption("Jeśli w historycznym meczu nie da się ustalić kolejności bramek automatycznie, organizator może wskazać autora jubileuszowego gola.")
        render_pending_goal_milestones(compact=False)

def render_awards(readonly:bool=False):
    st.subheader("🏆 FIFA Night Awards")
    section=st.segmented_control("Sekcja",["🏆 Awards","🏛️ Kamienie milowe"],default="🏆 Awards",key=f"awards_section_{int(readonly)}",label_visibility="collapsed") or "🏆 Awards"
    if section=="🏛️ Kamienie milowe":
        render_global_milestones(readonly=readonly)
        return
    st.info("📊 TOP 5 liczy algorytm. 🏆 Nagrody rozdaje organizator. VAR-u, komisji odwoławczej i protestów po ceremonii nie przewidziano. 😎 Rankingi aktualizują się wraz z wynikami.")
    current_year=datetime.now().year
    year=int(st.number_input("Rok",min_value=2024,max_value=current_year+1,value=current_year,step=1,key="awards_year"))
    data=db.annual_awards(year);overview=data.get("overview") or {};cats=data.get("categories") or [];selections=data.get("selections") or {};nomination_summary=data.get("nomination_summary") or []
    c1,c2,c3,c4,c5=st.columns(5)
    c1.metric("🏆 Turnieje",overview.get("tournaments",0));c2.metric("⚔️ 1v1",overview.get("duels",0));c3.metric("🎮 Mecze",overview.get("matches",0));c4.metric("⚽ Gole",overview.get("goals",0));c5.metric("👥 Gracze",overview.get("players",0))
    if not cats:
        st.warning(f"Brak wystarczających oficjalnych danych do Awards w {year} roku.")
        return

    award_cats=[c for c in cats if c.get("award")]
    view_cats=[c for c in cats if not c.get("award")]

    # W zwykłym widoku AWARDS pokazujemy dokładnie tę samą kolejność kategorii,
    # w której organizator później wybiera laureatów. Tutaj lista pozostaje płaska:
    # bez etapów, nagłówków grup i dodatkowych opisów kolejności.
    award_priority_keys=[
        "player_year","offensive","defense","player_scorers","clutch",
        "regular","progress","spectacle","penalties","duel","universal","wildcards","debut","outsider",
        "finance","rivalry","team_best","team_worst","superscorer","match_year",
    ]
    award_priority_index={key:i for i,key in enumerate(award_priority_keys)}
    award_cats=sorted(
        award_cats,
        key=lambda c:(award_priority_index.get(str(c.get("key")),len(award_priority_keys)), str(c.get("title") or "")),
    )

    st.markdown("### 📊 Rankingi LIVE — TOP 5")
    for cat in award_cats:
        candidates=cat.get("candidates") or []
        selected=selections.get(cat["key"]) or {}
        selected_note=f" • 🏅 wybrany laureat: **{selected.get('name')}**" if selected.get("name") else ""
        qualified_label=(" • TOP 5" if len(candidates)>=5 else f" • {len(candidates)} zakwalifikowanych")
        with st.expander(f"{cat['title']}{qualified_label}",expanded=cat.get("key") in ("player_year","offensive","defense")):
            st.caption(cat.get("description") or "")
            if selected_note: st.markdown(selected_note)
            if not candidates:
                st.info("Kategoria jest warunkowa albo nie ma jeszcze wystarczającej próby danych.")
            elif cat.get("key")=="debut":
                def debut_table_rows(items):
                    return [{
                        "#":i,
                        "Gracz":x.get("name"),
                        "W-D-L":f"{x.get('w',0)}-{x.get('d',0)}-{x.get('l',0)}",
                        "W%":x.get("win_pct",0),
                        "Pkt/mecz":x.get("points_per_match",0),
                        "Gole":f"{x.get('gf',0)}:{x.get('ga',0)}",
                        "Bilans":f"{int(x.get('gd',0)):+d}",
                        "SF / finały ścieżki":x.get("deep_runs",0),
                        "Finały":x.get("finals",0),
                        "Tytuły":x.get("titles",0),
                    } for i,x in enumerate((items or [])[:5],1)]

                first5=cat.get("debut_first5") or []
                first10=cat.get("debut_first10") or []
                # Zgodność z sesją / backendem sprzed rozszerzenia Debiutu Roku:
                # jeśli główny ranking już ma rekordy z informacją o oknie, nie pokazuj
                # fałszywego komunikatu „nikt nie ma 5/10 meczów”.
                if not first5 and not first10 and candidates:
                    c5=[x for x in candidates if int(x.get("matches") or 0)==5]
                    c10=[x for x in candidates if int(x.get("matches") or 0)==10]
                    if c5:first5=c5
                    if c10:first10=c10
                st.markdown("**⚡ Pierwsze 5 meczów — tempo wejścia do FIFA Night**")
                if first5:
                    st.dataframe(pd.DataFrame(debut_table_rows(first5)),hide_index=True,use_container_width=True)
                else:
                    st.caption("Nikt z tegorocznych debiutantów nie ma jeszcze 5 oficjalnych meczów turniejowych.")
                st.markdown("**🏁 Pierwsze 10 meczów — ranking główny Debiutu Roku**")
                if first10:
                    st.dataframe(pd.DataFrame(debut_table_rows(first10)),hide_index=True,use_container_width=True)
                else:
                    st.caption("Nikt z tegorocznych debiutantów nie ma jeszcze 10 oficjalnych meczów turniejowych — ranking LIVE korzysta tymczasowo z pierwszych 5.")
            else:
                rows=[{"#":i,"Kandydat":x.get("name"),"Dlaczego jest wysoko":x.get("reason") or "—"} for i,x in enumerate(candidates[:5],1)]
                st.dataframe(pd.DataFrame(rows),hide_index=True,use_container_width=True)
                secondary=cat.get("secondary")
                if secondary and cat.get("key")=="finance":
                    st.caption(f"📉 Sponsor FIFA Night: **{secondary.get('name')}** — {secondary.get('reason','')}")

    if view_cats:
        st.markdown("### 👀 Dodatkowe rankingi — bez oficjalnej nagrody")
        cols=st.columns(min(2,len(view_cats)))
        for idx,cat in enumerate(view_cats):
            with cols[idx % len(cols)]:
                st.markdown(f"#### {cat['title']}")
                st.caption(cat.get("description") or "")
                candidates=cat.get("candidates") or []
                if candidates:
                    st.dataframe(pd.DataFrame([{"#":i,"Gracz":x.get("name"),"Argument":x.get("reason") or "—"} for i,x in enumerate(candidates[:5],1)]),hide_index=True,use_container_width=True)
                else: st.caption("Brak wystarczającej próby.")

    if nomination_summary:
        st.divider();st.markdown("### 🌟 Najczęściej nominowani")
        st.caption("Ile różnych indywidualnych kategorii ma danego gracza w TOP 3 i TOP 5. Każda kategoria liczy się maksymalnie raz. Żeby tabela była czytelna, z nazw wypisujemy tylko kategorie, w których gracz jest w TOP 2. W Królu Strzelców nominacja jest przypisana graczowi, dla którego strzelał dany piłkarz; nie liczymy kategorii drużynowych, Meczu Roku, Rywalizacji Roku ani Supersnajpera.")

        # Budujemy nazwy kategorii TOP 2 bezpośrednio z aktualnie wyświetlanych
        # rankingów. Dzięki temu kolumna nie zależy od pomocniczego pola zwracanego
        # przez backend i nie może zostać pusta przy poprawnie policzonym TOP 2.
        direct_player_nomination_keys={
            "player_year","offensive","defense","clutch","penalties","wildcards",
            "progress","spectacle","regular","debut","outsider","universal","finance","duel"
        }
        top2_titles_by_player={}
        for cat in award_cats:
            key=str(cat.get("key") or "")
            if key not in direct_player_nomination_keys and key!="player_scorers":
                continue
            title=str(cat.get("title") or key)
            # Usuń wyłącznie emoji/pierwszy znacznik z tytułu, zachowując pełną nazwę nagrody.
            clean_title=title.split(" ",1)[1] if " " in title else title
            for cand in (cat.get("candidates") or [])[:2]:
                cid=str(cand.get("id") or "")
                pid=cid.split("|",1)[0] if key=="player_scorers" else cid
                if not pid:
                    continue
                top2_titles_by_player.setdefault(pid,[])
                if clean_title not in top2_titles_by_player[pid]:
                    top2_titles_by_player[pid].append(clean_title)

        rows=[]
        for i,x in enumerate(nomination_summary[:10],1):
            pid=str(x.get("player_id") or "")
            live_titles=top2_titles_by_player.get(pid,[])
            # Fallback dla zgodności ze starszym backendem / zapisaną sesją.
            if not live_titles:
                live_titles=[str(c).split(" ",1)[1] if " " in str(c) else str(c) for c in (x.get("categories_top2") or [])]
            cats_txt=", ".join(live_titles)
            rows.append({"#":i,"Gracz":x.get("name"),"TOP 3":x.get("top3",0),"TOP 5":x.get("top5",0),"#1 w rankingu":x.get("first",0),"Kategorie TOP 2":cats_txt or "brak TOP 2"})
        st.dataframe(pd.DataFrame(rows),hide_index=True,use_container_width=True)

    st.divider();st.markdown("### 🔐 Organizator — wybór laureatów")
    st.caption("W każdej kategorii możesz wybrać jedną osobę z TOP 2–3. Liczba już przyznanych nagród jest tylko informacją — nie ma twardego limitu.")
    secret_ready=bool(admin_password())
    if readonly:
        st.info("📺 Tryb podglądu — rankingi i wybrani laureaci są widoczni, ale wyboru laureatów dokonuje się na urządzeniu ze sterowaniem.")
    elif not secret_ready:
        st.warning("Brak ADMIN_PASSWORD w Streamlit Secrets — rankingi działają, ale wybór laureatów jest zablokowany.")
    elif not st.session_state.get("awards_admin_ok"):
        with st.form("awards_unlock"):
            pwd=st.text_input("Hasło administratora",type="password",key="awards_pwd")
            unlock=st.form_submit_button("🔓 ODBLOKUJ WYBÓR LAUREATÓW",use_container_width=True)
        if unlock:
            if admin_ok(pwd):st.session_state.awards_admin_ok=True;rr()
            else:st.error("Nieprawidłowe hasło.")
    else:
        # Kategorie są wybierane w kolejności od najbardziej prestiżowych do bardziej
        # specjalistycznych i zabawowych. Nie blokujemy organizatora: ranking jest
        # podpowiedzią, a licznik nagród pomaga świadomie rozłożyć wyróżnienia.
        direct_player_awards={
            "player_year","offensive","defense","clutch","penalties","wildcards",
            "progress","spectacle","regular","debut","outsider","universal","finance","duel"
        }

        def award_owner_name(cat_key,candidate_id,candidate_name):
            cat_key=str(cat_key or ""); candidate_name=str(candidate_name or "")
            if cat_key in direct_player_awards:
                return candidate_name
            if cat_key=="player_scorers":
                # Kandydat ma postać „Piłkarz — Gracz”; nagrodę liczymy do osoby,
                # dla której dany piłkarz strzelał.
                if " — " in candidate_name:
                    return candidate_name.rsplit(" — ",1)[1].strip()
            return None

        counts={}
        for key,sel in selections.items():
            sel=sel or {}
            owner=award_owner_name(key,sel.get("id"),sel.get("name"))
            if owner:counts[owner]=counts.get(owner,0)+1

        if counts:
            spread_rows=[{"Gracz":name,"Wybrane nagrody":n} for name,n in sorted(counts.items(),key=lambda x:(-x[1],x[0]))]
            st.markdown("#### 🎁 Rozkład nagród do tej pory")
            st.dataframe(pd.DataFrame(spread_rows),hide_index=True,use_container_width=True)
        else:
            st.caption("🎁 Nikt nie ma jeszcze wybranej nagrody — zaczynamy od najważniejszych kategorii.")

        st.caption("Kolejność poniżej jest celowa: najpierw wybierz główne nagrody. Przy kolejnych kategoriach zobaczysz, kto już coś dostał, więc przy zbliżonych kandydaturach możesz świadomie rozłożyć wyróżnienia szerzej. Nic nie jest wymuszane — organizator nadal może wybrać dowolną osobę z TOP 3.")

        award_priority_groups=[
            ("🥇 ETAP 1/3 — Główne nagrody",
             "Najpierw najważniejsze sportowe wyróżnienia. Tu najlepiej trzymać się przede wszystkim rankingu.",
             ["player_year","offensive","defense","player_scorers","clutch"]),
            ("🥈 ETAP 2/3 — Nagrody specjalistyczne",
             "Tu nadal liczy się ranking, ale warto już zerkać na rozkład nagród i TOP 3 kandydatów.",
             ["regular","progress","spectacle","penalties","duel","universal","wildcards","debut","outsider"]),
            ("🥉 ETAP 3/3 — Nagrody specjalne i finał gali",
             "Najbardziej elastyczny etap. Dobry moment, żeby przy zbliżonych wynikach docenić kogoś, kto jeszcze nic nie dostał.",
             ["finance","rivalry","team_best","team_worst","superscorer","match_year"]),
        ]
        cat_by_key={str(c.get("key")):c for c in award_cats}
        pick_no=0
        for group_title,group_desc,keys in award_priority_groups:
            group_cats=[cat_by_key[k] for k in keys if k in cat_by_key and (cat_by_key[k].get("candidates") or [])]
            if not group_cats:continue
            st.markdown(f"#### {group_title}")
            st.caption(group_desc)
            for cat in group_cats:
                pick_no+=1
                candidates=(cat.get("candidates") or [])[:3]
                selected=selections.get(cat["key"]) or {}
                ids=[str(x.get("id")) for x in candidates]
                current_id=str(selected.get("id") or "")
                default_index=ids.index(current_id) if current_id in ids else 0
                label_by={}
                for pos,x in enumerate(candidates,1):
                    cid=str(x.get("id")); cname=str(x.get("name") or "")
                    owner=award_owner_name(cat.get("key"),cid,cname)
                    rank=f"#{pos}"
                    if owner:
                        won=counts.get(owner,0)
                        award_note="🆕 bez nagrody" if won==0 else f"🏅 ma już {won}"
                        if cat.get("key")=="player_scorers":
                            label_by[cid]=f"{rank} {cname} • {owner}: {award_note}"
                        else:
                            label_by[cid]=f"{rank} {cname} • {award_note}"
                    else:
                        label_by[cid]=f"{rank} {cname}"
                current_owner=award_owner_name(cat.get("key"),selected.get("id"),selected.get("name")) if selected else None
                if selected.get("name"):
                    extra=f" • {current_owner} ma łącznie {counts.get(current_owner,0)} nagr." if current_owner else ""
                    st.caption(f"✅ Aktualnie wybrano: **{selected.get('name')}**{extra}")
                with st.form(f"award_pick_{year}_{cat['key']}"):
                    choice=st.selectbox(f"{pick_no}. {cat['title']}",options=ids,index=default_index,format_func=lambda x,m=label_by:m.get(x,x),key=f"award_choice_{year}_{cat['key']}")
                    save=st.form_submit_button("🏅 ZAPISZ LAUREATA",use_container_width=True)
                if save:
                    cand=next(x for x in candidates if str(x.get("id"))==str(choice))
                    db.set_award_selection(year,cat["key"],str(cand.get("id")),str(cand.get("name")))
                    st.success(f"Zapisano: {cat['title']} — {cand.get('name')}");rr()
            st.divider()
        if st.button("🔒 Zablokuj wybór laureatów",use_container_width=True,key="awards_lock"):
            st.session_state.awards_admin_ok=False;rr()

    # Share cards. The Awards graphic intentionally contains only organizer-selected winners.
    selected_rows=[]
    for cat in award_cats:
        sel=selections.get(cat["key"]) or {}
        if sel.get("name"):
            raw_title=str(cat["title"]);plain_title=raw_title.split(" ",1)[1] if " " in raw_title else raw_title
            selected_rows.append({"title":plain_title,"name":sel["name"]})
    st.divider();st.markdown("### 🖼️ Grafiki roczne")
    c1,c2=st.columns(2)
    highlights=[]
    if overview.get("top_player"):highlights.append({"label":"Lider rankingu Gracza Roku","value":overview.get("top_player")})
    if overview.get("top_team"):highlights.append({"label":"Najwyżej sklasyfikowana drużyna","value":overview.get("top_team")})
    match_cat=next((c for c in cats if c.get("key")=="match_year"),None)
    if match_cat and match_cat.get("candidates"):highlights.append({"label":"Mecz Roku — ranking live","value":match_cat["candidates"][0].get("name")})
    with c1:
        year_png=generate_year_summary_png(year,overview,highlights)
        st.download_button("⬇️ FIFA Night — Rok w liczbach (PNG)",data=year_png,file_name=f"fifa-night-{year}-rok-w-liczbach.png",mime="image/png",use_container_width=True,key=f"year_png_{year}")
    with c2:
        awards_png=generate_awards_png(year,selected_rows)
        st.download_button("⬇️ FIFA Night Awards — laureaci (PNG)",data=awards_png,file_name=f"fifa-night-awards-{year}.png",mime="image/png",use_container_width=True,key=f"awards_png_{year}")
        if not selected_rows:st.caption("Grafika Awards będzie uzupełniać się dopiero po wyborze laureatów przez organizatora.")



def render_tournament_archive(readonly:bool=True):
    st.subheader("🗂️ Historia turniejów")
    show_tests=st.checkbox("Pokaż także turnieje testowe",value=False,key=f"archive_tests_{int(readonly)}")
    rows=db.completed_tournaments(include_tests=show_tests,limit=300)
    if not rows:
        st.info("Nie ma jeszcze zapisanych rozgrywek do pokazania.")
        return
    by_id={str(x["id"]):x for x in rows}
    def label(tid):
        r=by_id[str(tid)];fmt=str(r.get("format_key") or "");unfinished=str(r.get("status") or "")=="abandoned"
        when=fmt_history_datetime(r.get("completed_at") or r.get("created_at"));day=when.split(" ",1)[0]
        if int(r.get("is_test") or 0):prefix="🧪 TEST"
        elif fmt=="duel1v1":prefix="⚔️ 1 VS 1"
        elif unfinished:prefix=f"⚠️ FIFA Night #{r.get('official_no') or '—'} • NIEDOKOŃCZONY"
        else:prefix=f"🏆 FIFA Night #{r.get('official_no') or '—'}"
        champ=("bez mistrza" if unfinished else (r.get("champion_name") or "—"))
        return f"{prefix} • {day} • {FORMAT_LABELS.get(fmt,fmt)} • {champ}"
    ids=[str(x["id"]) for x in rows]
    selected=st.selectbox("Wybierz turniej",ids,format_func=label,key=f"archive_select_{int(readonly)}")
    if not selected:return
    row=by_id[selected];b=db.bundle(selected);t=b.get("tournament") or row;meta=b.get("meta") or {};fmt=str(meta.get("format_key") or row.get("format_key") or "")
    unfinished=str(t.get("status") or row.get("status") or "")=="abandoned"
    when=fmt_history_datetime(t.get("completed_at") or t.get("created_at"))
    if int(t.get("is_test") or 0):badge="🧪 TURNIEJ TESTOWY"
    elif fmt=="duel1v1":badge="⚔️ 1 VS 1"
    elif unfinished:badge=f"⚠️ FIFA NIGHT #{row.get('official_no') or '—'} • NIEDOKOŃCZONY"
    else:badge=f"🏆 FIFA NIGHT #{row.get('official_no') or '—'}"
    st.markdown(f"### {badge}")
    st.caption(f"{when} • {FORMAT_LABELS.get(fmt,fmt)} • {int(row.get('player_count') or len(b.get('players') or []))} graczy")
    matches=b.get("matches") or [];played=sum(1 for m in matches if m.get("home_score") is not None);skipped=sum(1 for m in matches if str(m.get("match_status") or "pending")=="skipped")
    if unfinished:
        st.warning(f"Turniej zakończono przed końcem. Rozegrano **{played}** z {len(matches)} zaplanowanych meczów"+(f" • pominięto {skipped}" if skipped else "")+". Rozegrane wyniki i strzelcy pozostają w oficjalnych statystykach oraz danych do Awards. Ten turniej nie ma mistrza, podium, tytułu ani rozliczenia.")
    else:
        summary=db.tournament_summary(selected)
        champ=summary.get("champion") or row.get("champion_name") or "—"
        if fmt=="duel1v1":
            st.success(f"⚔️ **Zwycięzca: {champ}**")
        else:
            c1,c2,c3=st.columns(3);c1.success(f"🏆 **1. {champ}**");c2.info(f"🥈 **2. {summary.get('runner_up') or '—'}**")
            third=summary.get("third_place") or {};c3.info(f"🥉 **3. {third.get('name') or '—'}**")
    players=b.get("players") or []
    if players:
        st.markdown("#### 👥 Uczestnicy")
        st.caption(" • ".join(f"{p.get('name','?')} — {p.get('team') or '—'}" for p in players))
    scorers=db.tournament_live_scorers(selected,5)
    if scorers:
        st.markdown("#### ⚽ Strzelcy turnieju")
        st.caption(" • ".join(f"{x.get('name')} — {x.get('goals')}" for x in scorers))
    st.divider();render_schedule(t)


def render_public_start():
    render_start(public_mode=True)


@st.fragment(run_every="5s")
def render_tv_screen(tid:str):
    fresh=db.current_tournament()
    if not fresh or str(fresh.get("id"))!=str(tid):
        st.info("Brak aktywnego turnieju.")
        return
    b=db.bundle(tid);t=b["tournament"];meta=b["meta"];fmt=meta["format_key"];extra=meta.get("extra") or {}
    status="🧪 TEST" if int(t.get("is_test") or 0) else "🏆 OFICJALNY"
    st.markdown(f"<div style='text-align:center;margin:.2rem 0 .7rem'><span class='status-chip'>{status}</span></div>",unsafe_allow_html=True)

    # Hotfix 25: TV AUTO changes only what is displayed. It never changes the
    # tournament scheduler or the order chosen by the existing fairness algorithm.
    if fmt=="duel1v1":
        tv_mode="📺 LIVE"
    else:
        tv_mode=st.segmented_control(
            "Tryb TV",["📺 LIVE","🔄 AUTO"],default="📺 LIVE",
            key=f"tv_display_mode_{tid}",label_visibility="collapsed"
        ) or "📺 LIVE"
    prev_key=f"_tv_display_prev_{tid}"
    start_key=f"_tv_auto_started_{tid}"
    if tv_mode=="🔄 AUTO" and st.session_state.get(prev_key)!="🔄 AUTO":
        st.session_state[start_key]=time.time()
    st.session_state[prev_key]=tv_mode
    auto_slide=0
    if tv_mode=="🔄 AUTO":
        started=float(st.session_state.get(start_key) or time.time())
        auto_slide=int(max(0,time.time()-started)//10)%3
        labels=["🎮 TERAZ / NASTĘPNY","🗺️ SYTUACJA TURNIEJU","⚽ WYNIKI I STRZELCY"]
        st.caption(f"🔄 TV AUTO • {labels[auto_slide]} • zmiana co około 10 s")
    if t.get("status")=="completed":
        summary=db.tournament_summary(tid);champ=summary.get("champion") or "—"
        label="ZWYCIĘZCA 1 VS 1" if fmt=="duel1v1" else "MISTRZ FIFA NIGHT"
        icon="⚔️" if fmt=="duel1v1" else "🏆"
        st.markdown(f"<div class='winner'><div class='match-no'>{label}</div><div style='font-size:3rem'>{icon}</div><div class='player-big'>{esc(champ)}</div></div>",unsafe_allow_html=True)
        if fmt!="duel1v1":
            runner=summary.get("runner_up") or "—"
            c1,c2=st.columns(2);c1.success(f"🏆 **{champ}**");c2.info(f"🥈 **{runner}**")
        st.caption("Ekran odświeża się automatycznie. Nowy turniej uruchamia urządzenie ze sterowaniem.")
        return
    if str(t.get("phase") or "") in ("draft_order","team_draft","team_draw","structure_draw"):
        phase_names={"draft_order":"Losowanie kolejności wyboru","team_draft":"Wybór drużyn","team_draw":"Losowanie drużyn","structure_draw":"Losowanie struktury turnieju"}
        st.markdown("### 🎱 Turniej w przygotowaniu")
        st.info(phase_names.get(str(t.get("phase")),"Przygotowanie turnieju"))
        players=b.get("players") or []
        if players:
            rows=[{"Gracz":p.get("name"),"Drużyna":p.get("team") or "—"} for p in players]
            st.dataframe(pd.DataFrame(rows),hide_index=True,use_container_width=True)
        st.caption("Ten ekran odświeża się automatycznie co kilka sekund.")
        return
    cur=db.current_match_from(b.get("matches") or [],extra)
    schedule=db.live_schedule_from(b.get("matches") or [],extra)
    ready=[m for m in schedule if m.get("home_player_id") and m.get("away_player_id") and m.get("home_score") is None and str(m.get("match_status") or "pending")!="skipped"]

    if tv_mode=="🔄 AUTO" and auto_slide==1:
        st.markdown("### 🗺️ Sytuacja turnieju")
        if fmt in DE_FORMATS:
            cur_no=int(cur.get("match_no")) if cur else None
            render_de_bracket(t,b,fmt,cur_no)
        else:
            tables=db.standings(tid)
            if tables:
                if "L" in tables:
                    st.markdown("#### 📊 Tabela")
                    st.dataframe(standings_df(tables["L"]),hide_index=True,use_container_width=True)
                else:
                    c1,c2=st.columns(2)
                    with c1:
                        st.markdown("#### Grupa A")
                        st.dataframe(standings_df(tables["A"]),hide_index=True,use_container_width=True)
                    with c2:
                        st.markdown("#### Grupa B")
                        st.dataframe(standings_df(tables["B"]),hide_index=True,use_container_width=True)
            else:
                st.info("Tabela pojawi się po rozegraniu pierwszych spotkań.")
        return

    if tv_mode=="🔄 AUTO" and auto_slide==2:
        st.markdown("### ⚽ Wyniki i strzelcy")
        played=[m for m in schedule if m.get("home_score") is not None]
        if played:
            st.markdown("#### 🕘 Ostatnie wyniki")
            for m in played[-4:]:
                st.markdown(
                    f'<div class="mini-card"><span class="match-no">MECZ {int(m.get("match_no") or 0)} • {esc(stage_name(m))}</span><br>'
                    f'<b>{esc(m.get("home_name"))} — {esc(m.get("away_name"))}</b>'
                    f'<span style="float:right" class="scoreline">{esc(result_text(m))}</span></div>',
                    unsafe_allow_html=True
                )
        else:
            st.caption("Nie ma jeszcze rozegranych spotkań.")
        scorers=db.tournament_live_scorers(tid,5)
        if scorers:
            st.markdown("#### 🥇 Strzelcy tego FIFA Night")
            for idx,x in enumerate(scorers,1):
                st.markdown(f"**{idx}. {esc(x.get('name'))}** — {int(x.get('goals') or 0)}")
        else:
            st.caption("Strzelcy pojawią się po zapisaniu pierwszych bramek.")
        return

    if not cur:
        st.markdown("### ⏳ Czekamy na kolejny mecz")
        st.caption("Para pojawi się automatycznie po rozstrzygnięciu poprzedniego etapu.")
        return
    st.markdown(f"<div style='text-align:center;font-weight:900;color:#22c55e;letter-spacing:.08em;margin-bottom:.35rem'>▶️ TERAZ</div>",unsafe_allow_html=True)
    st.markdown(f'<div class="match-no">MECZ {cur["match_no"]}/{max_matches(fmt)} • {stage_name(cur)}</div>',unsafe_allow_html=True)
    st.markdown(f'<div class="match-card"><div style="display:flex;justify-content:space-between;gap:20px;align-items:center;text-align:center"><div style="flex:1"><div class="player-big">{esc(cur["home_name"])}</div><div class="team-small">{esc(cur["home_team"])}</div></div><div style="font-size:1.7rem;font-weight:900;color:#94a3b8">VS</div><div style="flex:1"><div class="player-big">{esc(cur["away_name"])}</div><div class="team-small">{esc(cur["away_team"])}</div></div></div></div>',unsafe_allow_html=True)
    # Kolejne gotowe spotkania w faktycznej kolejności LIVE.
    later=[m for m in ready if int(m.get("match_no") or 0)!=int(cur.get("match_no") or 0)]
    if later:
        st.markdown(f"### ⏭️ Następny: **{esc(later[0].get('home_name'))} vs {esc(later[0].get('away_name'))}**")
        if len(later)>1:st.caption(f"Potem: {later[1].get('home_name')} vs {later[1].get('away_name')}")
    else:
        st.caption("Kolejny mecz zostanie ustalony po tym spotkaniu.")
    scorers=db.tournament_live_scorers(tid,3)
    if scorers:
        st.markdown("#### ⚽ Strzelcy tego FIFA Night")
        st.caption(" • ".join(f"{x['name']} — {x['goals']}" for x in scorers))
    tables=db.standings(tid)
    if tables:
        st.divider()
        if "L" in tables:
            st.markdown("#### 📊 Tabela")
            st.dataframe(standings_df(tables["L"]),hide_index=True,use_container_width=True)
        else:
            c1,c2=st.columns(2)
            with c1:st.markdown("#### Grupa A");st.dataframe(standings_df(tables["A"]),hide_index=True,use_container_width=True)
            with c2:st.markdown("#### Grupa B");st.dataframe(standings_df(tables["B"]),hide_index=True,use_container_width=True)
    st.caption("📺 LIVE odświeża dane co 5 sekund. W trybie AUTO ekran sam przełącza widoki co około 10 sekund.")

def render_viewer_live(t):
    title="1 vs 1" if t.get("format_key")=="duel1v1" else f"{t['player_count']} graczy"
    hero(f"{title} • {FORMAT_LABELS[t['format_key']]}")
    opts=["📺 LIVE","📅 Terminarz","📊 Statystyki","🏆 AWARDS","⚙️ Ustawienia"]
    view=st.segmented_control("Widok",opts,default=opts[0],key="viewer_view",label_visibility="collapsed") or opts[0]
    if view==opts[0]:render_tv_screen(t["id"])
    elif view==opts[1]:render_schedule(t)
    elif view==opts[2]:render_stats(t,readonly=True)
    elif view==opts[3]:render_awards(readonly=True)
    else:render_access_settings()

def reset_controls(t,loc):
    if t.get("status") in ("completed","abandoned"): return
    st.divider()
    is_official=not int(t.get("is_test") or 0)
    is_tournament=str(t.get("format_key") or "")!="duel1v1"
    if is_official and is_tournament:
        with st.expander("⏹️ Zakończ FIFA Night jako niedokończony"):
            st.caption("Użyj tego, gdy oficjalny turniej kończy się wcześniej i nie będziecie do niego wracać. Rozegrane mecze, gole, strzelcy, H2H i dane do Awards zostają w historii. Nie ma mistrza, podium, tytułu ani rozliczenia tego turnieju.")
            with st.form(f"abandon_{loc}_{t['id']}"):
                yes=st.checkbox("Tak, kończymy ten oficjalny FIFA Night bez rozgrywania pozostałych meczów")
                go=st.form_submit_button("⏹️ ZAKOŃCZ JAKO NIEDOKOŃCZONY",use_container_width=True)
            if go:
                if not yes:st.error("Najpierw zaznacz potwierdzenie.")
                else:
                    try:
                        result=db.abandon_tournament(t["id"])
                        official_player_names_cached.clear();tournament_summary_png_cached.clear()
                        st.success(f"FIFA Night zapisany jako niedokończony. Zachowano {result.get('played',0)} rozegranych meczów.")
                        rr()
                    except ValueError as e:st.error(str(e))
    with st.expander("🔄 Reset bieżącego turnieju"):
        st.caption("Reset usuwa cały bieżący turniej razem z rozegranymi wynikami. Do oficjalnego turnieju, którego statystyki chcesz zachować, użyj opcji powyżej.")
        with st.form(f"reset_{loc}_{t['id']}"):
            yes=st.checkbox("Tak, usuń bieżący turniej");go=st.form_submit_button("Usuń i zacznij od nowa",use_container_width=True)
        if go:
            if not yes:st.error("Najpierw zaznacz potwierdzenie.")
            else:db.reset_current(t["id"]);st.session_state.pop("last_spin",None);rr()


def render_live(t,public_test:bool=False):
    title="1 vs 1" if t.get("format_key")=="duel1v1" else f"{t['player_count']} graczy"
    hero(f"{title} • {FORMAT_LABELS[t['format_key']]}")
    st.markdown(f'<span class="status-chip">{"🧪 TEST" if t["is_test"] else "🏆 OFICJALNY"}</span>',unsafe_allow_html=True)
    render_tournament_status_control(t,"live")
    if not int(t.get("is_test") or 0):render_pending_goal_milestones(compact=True)
    opts=["🏠 Ekran główny","📺 TV","📅 Terminarz","📊 Statystyki","🏆 AWARDS","⚙️ Ustawienia"];view=st.segmented_control("Widok",opts,default=opts[0],key="view",label_visibility="collapsed") or opts[0]
    if view==opts[0]:live(t["id"]);reset_controls(t,"live")
    elif view==opts[1]:render_tv_screen(t["id"])
    elif view==opts[2]:render_schedule(t)
    elif view==opts[3]:render_stats(t,readonly=public_test)
    elif view==opts[4]:render_awards(readonly=public_test)
    else:render_access_settings()


t=db.current_tournament()
# From this version onward every 1 vs 1 is official. If an active duel was
# created by an older hotfix as testowy, normalize only that current event.
if t and t.get("format_key")=="duel1v1" and int(t.get("is_test") or 0):
    db.set_test_mode(t["id"],False)
    t["is_test"]=0
if not controller_access():
    if not t:
        render_public_start()
    elif int(t.get("is_test") or 0):
        if t["phase"]=="draft_order":render_draft_order_stage(t)
        elif t["phase"]=="team_draft":render_team_draft(t)
        elif t["phase"]=="team_draw":render_team_draw(t)
        elif t["phase"]=="structure_draw":render_structure(t)
        else:render_live(t,public_test=True)
    else:
        if t.get("format_key")=="duel1v1":
            render_live(t,public_test=True)
        else:
            render_viewer_live(t)
elif not t:render_start()
elif t["phase"]=="draft_order":render_draft_order_stage(t)
elif t["phase"]=="team_draft":render_team_draft(t)
elif t["phase"]=="team_draw":render_team_draw(t)
elif t["phase"]=="structure_draw":render_structure(t)
else:render_live(t)

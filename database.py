from __future__ import annotations

from collections import defaultdict
from contextlib import contextmanager
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import random
import sqlite3
import uuid

import psycopg
from psycopg.rows import dict_row
import streamlit as st

from logic import (
    BASE_TEAMS, SEVEN_TEAMS, EIGHT_TEAMS, WILDCARD_TEAM_SUGGESTIONS, build_draw, draw_signature, group_members, group_table,
    schedule_for_format, shuffled_assignments, winner_from_result, optimize_opening_order, apply_cross_tournament_bye_priority, weighted_bye_choice,
)
from scorer_seeds import SCORER_SEEDS

DB_API_VERSION = 170
APP_KEY = "flex"
CURRENT_KEY = "flex_current_tournament"
LAST_COUNT_KEY = "flex_last_player_count"


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _database_url() -> str | None:
    value = os.getenv("DATABASE_URL")
    if value: return value
    try:
        value = st.secrets.get("DATABASE_URL")
        return str(value) if value else None
    except Exception:
        return None


class Database:
    def __init__(self) -> None:
        self.url = _database_url()
        self.is_postgres = bool(self.url and self.url.startswith(("postgres://", "postgresql://")))
        if not self.is_postgres:
            d = Path(".local"); d.mkdir(exist_ok=True)
            self.sqlite_path = d / "fifa_night_shared.db"

    @contextmanager
    def connect(self):
        if self.is_postgres:
            conn = psycopg.connect(self.url, row_factory=dict_row, autocommit=False, prepare_threshold=None)
        else:
            conn = sqlite3.connect(self.sqlite_path); conn.row_factory = sqlite3.Row
        try:
            yield conn; conn.commit()
        except Exception:
            conn.rollback(); raise
        finally:
            conn.close()

    def _sql(self, sql: str) -> str:
        return sql.replace("?", "%s") if self.is_postgres else sql

    def _fetchall(self, conn, sql: str, params: tuple = ()) -> list[dict]:
        return [dict(r) for r in conn.execute(self._sql(sql), params).fetchall()]

    def _fetchone(self, conn, sql: str, params: tuple = ()) -> dict | None:
        r = conn.execute(self._sql(sql), params).fetchone(); return dict(r) if r else None

    def init_schema(self) -> None:
        stmts = [
            """CREATE TABLE IF NOT EXISTS players (id TEXT PRIMARY KEY, name TEXT NOT NULL, normalized_name TEXT NOT NULL UNIQUE, created_at TEXT NOT NULL)""",
            """CREATE TABLE IF NOT EXISTS app_settings (key TEXT PRIMARY KEY, value TEXT NOT NULL)""",
            """CREATE TABLE IF NOT EXISTS tournaments (
                id TEXT PRIMARY KEY, status TEXT NOT NULL, phase TEXT NOT NULL,
                is_test INTEGER NOT NULL DEFAULT 0, is_current INTEGER NOT NULL DEFAULT 0,
                groups_revealed INTEGER NOT NULL DEFAULT 0, created_at TEXT NOT NULL,
                completed_at TEXT, champion_player_id TEXT)""",
            """CREATE TABLE IF NOT EXISTS tournament_players (
                tournament_id TEXT NOT NULL, player_id TEXT NOT NULL, team TEXT NOT NULL,
                team_reveal_order INTEGER NOT NULL, team_revealed INTEGER NOT NULL DEFAULT 0,
                group_name TEXT NOT NULL, tie_order INTEGER NOT NULL,
                PRIMARY KEY (tournament_id, player_id))""",
            """CREATE TABLE IF NOT EXISTS matches (
                id TEXT PRIMARY KEY, tournament_id TEXT NOT NULL, match_no INTEGER NOT NULL,
                stage TEXT NOT NULL, group_name TEXT, home_player_id TEXT, away_player_id TEXT,
                home_score INTEGER, away_score INTEGER, home_penalties INTEGER, away_penalties INTEGER,
                winner_player_id TEXT, played_at TEXT, UNIQUE (tournament_id, match_no))""",
            """CREATE TABLE IF NOT EXISTS flex_tournament_meta (
                tournament_id TEXT PRIMARY KEY, player_count INTEGER NOT NULL, format_key TEXT NOT NULL,
                team_pool_json TEXT NOT NULL, draw_json TEXT NOT NULL, extra_json TEXT NOT NULL,
                draw_revealed INTEGER NOT NULL DEFAULT 0, redraw_count INTEGER NOT NULL DEFAULT 0)""",
            """CREATE TABLE IF NOT EXISTS flex_match_sources (
                tournament_id TEXT NOT NULL, match_no INTEGER NOT NULL,
                home_source TEXT NOT NULL, away_source TEXT NOT NULL,
                PRIMARY KEY (tournament_id, match_no))""",
            """CREATE TABLE IF NOT EXISTS team_scorers (
                id TEXT PRIMARY KEY, team_name TEXT NOT NULL, normalized_team TEXT NOT NULL,
                scorer_name TEXT NOT NULL, normalized_scorer TEXT NOT NULL, seed_rank INTEGER NOT NULL DEFAULT 999,
                created_at TEXT NOT NULL, UNIQUE (normalized_team, normalized_scorer))""",
            """CREATE TABLE IF NOT EXISTS match_scorers (
                id TEXT PRIMARY KEY, tournament_id TEXT NOT NULL, match_no INTEGER NOT NULL, side TEXT NOT NULL,
                team_name TEXT NOT NULL, normalized_team TEXT NOT NULL, scorer_name TEXT NOT NULL,
                normalized_scorer TEXT NOT NULL, goals INTEGER NOT NULL,
                UNIQUE (tournament_id, match_no, side, normalized_scorer))""",
        ]
        with self.connect() as conn:
            for s in stmts: conn.execute(s)
            self._seed_scorers_conn(conn)
            self._migrate_double_elim_single_final_conn(conn)

    def _migrate_double_elim_single_final_conn(self, conn) -> None:
        """Migruje tylko aktywne stare DE do jednego finału; historii nie zmienia."""
        rows=self._fetchall(conn,"""
            SELECT t.id,m.format_key
            FROM tournaments t JOIN flex_tournament_meta m ON m.tournament_id=t.id
            WHERE t.status='active' AND m.format_key IN ('double5','double7','double8')
        """)
        finals={"double5":8,"double7":12,"double8":14}
        resets={"double5":9,"double7":13,"double8":15}
        for row in rows:
            tid=row["id"]; fmt=row["format_key"]; final_no=finals[fmt]; reset_no=resets[fmt]
            final=self._fetchone(conn,"SELECT * FROM matches WHERE tournament_id=? AND match_no=?",(tid,final_no))
            conn.execute(self._sql("DELETE FROM flex_match_sources WHERE tournament_id=? AND match_no=?"),(tid,reset_no))
            conn.execute(self._sql("DELETE FROM match_scorers WHERE tournament_id=? AND match_no=?"),(tid,reset_no))
            conn.execute(self._sql("DELETE FROM matches WHERE tournament_id=? AND match_no=?"),(tid,reset_no))
            if final and final.get("winner_player_id"):
                conn.execute(self._sql("UPDATE tournaments SET status='completed',phase='completed',champion_player_id=?,completed_at=COALESCE(completed_at,?) WHERE id=?"),
                             (final["winner_player_id"],final.get("played_at") or now_iso(),tid))

    @staticmethod
    def _norm_scorer_name(value: str) -> str:
        return " ".join(str(value or "").strip().casefold().split())

    def _seed_scorers_conn(self, conn) -> None:
        for team, names in SCORER_SEEDS.items():
            nt=self._norm_team_name(team)
            for rank,name in enumerate(names,1):
                clean=" ".join(str(name or "").strip().split())
                if not clean: continue
                ns=self._norm_scorer_name(clean)
                exists=self._fetchone(conn,"SELECT id FROM team_scorers WHERE normalized_team=? AND normalized_scorer=?",(nt,ns))
                if exists: continue
                conn.execute(self._sql("INSERT INTO team_scorers (id,team_name,normalized_team,scorer_name,normalized_scorer,seed_rank,created_at) VALUES (?,?,?,?,?,?,?)"),
                             (str(uuid.uuid4()),team,nt,clean,ns,rank,now_iso()))

    def wildcard_team_suggestions(self) -> list[str]:
        fixed={self._norm_team_name(x) for x in BASE_TEAMS+SEVEN_TEAMS+EIGHT_TEAMS if "Dowolna drużyna" not in x}
        with self.connect() as conn:
            rows=self._fetchall(conn,"SELECT team,COUNT(*) AS c FROM tournament_players WHERE team<>'' GROUP BY team ORDER BY c DESC,team")
        out=[]; seen=set()
        for name in list(WILDCARD_TEAM_SUGGESTIONS)+[r["team"] for r in rows]:
            clean=" ".join(str(name or "").strip().split()); norm=self._norm_team_name(clean)
            if not clean or "dowolna drużyna" in clean.casefold() or norm in fixed or norm in seen: continue
            seen.add(norm); out.append(clean)
        return out

    def _validate_wildcard_team_conn(self, conn, tid: str, team: str, player_id: str | None = None) -> str:
        clean=" ".join(str(team or "").strip().split())
        if not clean: raise ValueError("Wpisz drużynę dla Wild Card.")
        norm=self._norm_team_name(clean)
        banned={"real","real madrid","real madryt","rma"}
        if norm in banned or "real madrid" in norm or "real madryt" in norm: raise ValueError("Real Madryt jest banned 🚫")
        meta=self._fetchone(conn,"SELECT team_pool_json FROM flex_tournament_meta WHERE tournament_id=?",(tid,))
        pool=json.loads(meta["team_pool_json"]) if meta else []
        fixed={self._norm_team_name(x) for x in pool if "Dowolna drużyna" not in x}
        if norm in fixed: raise ValueError("Ta drużyna jest już osobnym wyborem w puli.")
        rows=self._fetchall(conn,"SELECT player_id,team FROM tournament_players WHERE tournament_id=? AND team<>''",(tid,))
        for r in rows:
            if player_id and r["player_id"]==player_id: continue
            if self._norm_team_name(r["team"])==norm: raise ValueError("Ta drużyna została już wybrana w tym turnieju.")
        return clean

    def _setting_get_conn(self, conn, key: str) -> str | None:
        r = self._fetchone(conn, "SELECT value FROM app_settings WHERE key = ?", (key,)); return r["value"] if r else None

    def _setting_set_conn(self, conn, key: str, value: str) -> None:
        conn.execute(self._sql("INSERT INTO app_settings (key,value) VALUES (?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value"), (key, value))

    def last_player_count(self) -> int:
        with self.connect() as conn:
            raw = self._setting_get_conn(conn, LAST_COUNT_KEY)
            try: return int(raw) if raw else 6
            except ValueError: return 6

    def last_lineup(self, count: int) -> list[str]:
        with self.connect() as conn:
            raw = self._setting_get_conn(conn, f"flex_last_lineup_{count}")
            if not raw: return []
            try:
                vals = json.loads(raw)
                return [str(x) for x in vals][:count] if isinstance(vals, list) else []
            except Exception: return []

    def official_player_names(self) -> list[str]:
        """Nicki graczy, którzy wystąpili w co najmniej jednym zakończonym turnieju nietestowym."""
        with self.connect() as conn:
            rows = self._fetchall(conn, """
                SELECT DISTINCT p.name
                FROM players p
                JOIN tournament_players tp ON tp.player_id = p.id
                JOIN tournaments t ON t.id = tp.tournament_id
                WHERE t.status='completed' AND t.is_test=0
                ORDER BY p.name
            """)
            return [str(r["name"]) for r in rows if r.get("name")]

    def _get_or_create_player_conn(self, conn, name: str) -> str:
        clean = " ".join(name.strip().split()); norm = clean.casefold()
        r = self._fetchone(conn, "SELECT id FROM players WHERE normalized_name = ?", (norm,))
        if r: return r["id"]
        pid = str(uuid.uuid4())
        conn.execute(self._sql("INSERT INTO players (id,name,normalized_name,created_at) VALUES (?,?,?,?)"), (pid, clean, norm, now_iso()))
        return pid

    def _cross_tournament_priority_conn(self, conn, current_names: list[str], current_pids: list[str], is_test: bool) -> dict:
        """Carry only exact-name matches from the immediately previous completed tournament.

        The score is the number of already-played matches that happened after a player's
        final appearance in that previous tournament. This works across different player
        counts and formats because it is player-based, not bracket-based.
        """
        prev=self._fetchone(conn,"""
            SELECT id,completed_at,created_at
            FROM tournaments
            WHERE status='completed' AND is_test=?
            ORDER BY COALESCE(completed_at,created_at) DESC, created_at DESC
            LIMIT 1
        """,(int(is_test),))
        if not prev:
            return {}
        prev_players=self._fetchall(conn,"""
            SELECT tp.player_id,p.name
            FROM tournament_players tp JOIN players p ON p.id=tp.player_id
            WHERE tp.tournament_id=?
        """,(prev["id"],))
        exact_prev={str(r.get("name") or ""):str(r.get("player_id") or "") for r in prev_players}
        played=self._fetchall(conn,"""
            SELECT match_no,played_at,home_player_id,away_player_id
            FROM matches
            WHERE tournament_id=? AND home_score IS NOT NULL
            ORDER BY CASE WHEN played_at IS NULL THEN 1 ELSE 0 END, played_at, match_no
        """,(prev["id"],))
        if not played:
            return {}
        # Fairness must follow the real play sequence, because from v1.7.0 the app may
        # play logical match numbers in a different order. Legacy rows without played_at
        # naturally fall back to match_no through the ORDER BY above.
        last_pos={}
        for pos,m in enumerate(played):
            for pid in (m.get("home_player_id"),m.get("away_player_id")):
                if pid:last_pos[str(pid)]=pos
        wait_by_pid={pid:(len(played)-1-pos) for pid,pos in last_pos.items()}
        max_no=max(int(m["match_no"]) for m in played)

        current_by_name={name:pid for name,pid in zip(current_names,current_pids)}
        matched=[];priority={}
        for name,pid in current_by_name.items():
            prev_pid=exact_prev.get(name)
            if not prev_pid:
                continue
            wait=int(wait_by_pid.get(prev_pid,0))
            priority[pid]=wait
            matched.append({"name":name,"wait_matches":wait})
        if not matched:
            return {}
        matched.sort(key=lambda x:(-int(x["wait_matches"]),x["name"]))
        return {
            "source_tournament_id":prev["id"],
            "exact_name_match":True,
            "priority_by_player_id":priority,
            "matched":matched,
            "source_last_match_no":max_no,
        }

    def _extra_for_format(self, format_key: str, rng: random.Random) -> dict:
        if format_key == "double5":
            return {"d5_opponent_match": None, "d5_draw_ack": False}
        if format_key == "double7":
            return {"d7_wb_draw": None, "d7_wb_draw_ack": False, "d7_lb_bye_match": None, "d7_lb_draw_ack": False, "d7_pairing": None}
        if format_key == "double8":
            return {"d8_wb_draw": None, "d8_wb_draw_ack": False}
        if format_key in ("groups6", "groups6_full", "groups7", "groups7_sf", "groups8_sf", "groups8_barrage"):
            return {"playoff_reveal_ack": False, "playoff_order": None}
        return {}

    def create_tournament(self, player_names: list[str], player_count: int, format_key: str, teams: list[str], is_test: bool) -> str:
        if player_count not in (4,5,6,7,8): raise ValueError("Obsługiwane są turnieje 4–8 osobowe.")
        if len(player_names) != player_count: raise ValueError(f"Turniej wymaga dokładnie {player_count} graczy.")
        clean = [" ".join(str(x or "").strip().split()) for x in player_names]
        if any(not x for x in clean): raise ValueError("Wpisz nick każdego gracza.")
        if len({x.casefold() for x in clean}) != player_count: raise ValueError("Nicki w jednym turnieju muszą być unikalne.")
        if player_count in (4,5):
            if len(teams) < player_count or len(set(teams)) != len(teams): raise ValueError("Pula draftu drużyn jest nieprawidłowa.")
        elif len(teams) != player_count or len(set(teams)) != player_count:
            raise ValueError(f"Turniej wymaga dokładnie {player_count} różnych drużyn/slotów.")
        if player_count == 4 and format_key != "league4_final": raise ValueError("Nieprawidłowy format dla 4 graczy.")
        if player_count == 5 and format_key not in ("double5", "league5_final"): raise ValueError("Nieprawidłowy format dla 5 graczy.")
        if player_count == 6 and format_key not in ("groups6", "groups6_full"): raise ValueError("Nieprawidłowy format dla 6 graczy.")
        if player_count == 7 and format_key not in ("double7", "groups7", "groups7_sf"): raise ValueError("Wybierz format turnieju 7-osobowego.")
        if player_count == 8 and format_key not in ("groups8_sf", "double8", "groups8_barrage"): raise ValueError("Wybierz format turnieju 8-osobowego.")

        tid = str(uuid.uuid4()); rng = random.SystemRandom()
        with self.connect() as conn:
            pids = [self._get_or_create_player_conn(conn, n) for n in clean]
            carry=self._cross_tournament_priority_conn(conn,clean,pids,is_test)
            draft_mode = player_count in (4,5)
            assignments = {} if draft_mode else shuffled_assignments(pids, teams, rng)
            reveal = pids.copy(); rng.shuffle(reveal); reveal_idx = {p:i+1 for i,p in enumerate(reveal)}
            draw = build_draw(pids, format_key, rng); extra = self._extra_for_format(format_key, rng)
            if carry:
                draw=apply_cross_tournament_bye_priority(draw,format_key,carry.get("priority_by_player_id") or {},rng)
                extra["cross_tournament_priority"]=carry
            if draft_mode:
                extra.update({"draft_order_revealed":False,"draft_redraw_count":0})
            self._setting_set_conn(conn, CURRENT_KEY, tid)
            self._setting_set_conn(conn, LAST_COUNT_KEY, str(player_count))
            self._setting_set_conn(conn, f"flex_last_lineup_{player_count}", json.dumps(clean, ensure_ascii=False))
            # is_current intentionally remains 0. The classic 6-player app therefore never mistakes this for its live tournament.
            initial_phase = "draft_order" if draft_mode else "team_draw"
            conn.execute(self._sql("INSERT INTO tournaments (id,status,phase,is_test,is_current,groups_revealed,created_at) VALUES (?,'active',?, ?,0,0,?)"), (tid, initial_phase, int(is_test), now_iso()))
            # Temporary group_name is always non-null for compatibility with the classic schema.
            for p in pids:
                team = "" if draft_mode else assignments[p]
                conn.execute(self._sql("INSERT INTO tournament_players (tournament_id,player_id,team,team_reveal_order,team_revealed,group_name,tie_order) VALUES (?,?,?,?,0,'',?)"), (tid,p,team,reveal_idx[p],reveal_idx[p]))
            conn.execute(self._sql("INSERT INTO flex_tournament_meta (tournament_id,player_count,format_key,team_pool_json,draw_json,extra_json,draw_revealed,redraw_count) VALUES (?,?,?,?,?,?,0,0)"), (tid,player_count,format_key,json.dumps(teams,ensure_ascii=False),json.dumps(draw),json.dumps(extra)))
        return tid

    def set_test_mode(self, tid: str, is_test: bool) -> None:
        """Switch an existing tournament between test and official classification.

        Official statistics are query-time based on tournaments.is_test, so changing this
        flag is enough even after completion. Existing results, bracket and scorer data
        are never touched.
        """
        with self.connect() as conn:
            t=self._fetchone(conn,"SELECT id FROM tournaments WHERE id=?",(tid,))
            if not t: raise ValueError("Nie znaleziono turnieju.")
            conn.execute(self._sql("UPDATE tournaments SET is_test=? WHERE id=?"),(int(bool(is_test)),tid))

    def current_tournament(self) -> dict | None:
        with self.connect() as conn:
            tid = self._setting_get_conn(conn, CURRENT_KEY)
            if not tid: return None
            t = self._fetchone(conn, "SELECT * FROM tournaments WHERE id = ?", (tid,))
            if not t:
                self._setting_set_conn(conn, CURRENT_KEY, "")
                return None
            meta = self._fetchone(conn, "SELECT * FROM flex_tournament_meta WHERE tournament_id = ?", (tid,))
            if not meta: return None
            t.update({"player_count": int(meta["player_count"]), "format_key": meta["format_key"], "draw_revealed": int(meta["draw_revealed"]), "redraw_count": int(meta["redraw_count"])})
            return t

    def tournament_players(self, tid: str) -> list[dict]:
        with self.connect() as conn:
            return self._fetchall(conn, """SELECT tp.*,p.name FROM tournament_players tp JOIN players p ON p.id=tp.player_id WHERE tp.tournament_id=? ORDER BY tp.team_reveal_order""", (tid,))

    def meta(self, tid: str) -> dict:
        with self.connect() as conn:
            r = self._fetchone(conn, "SELECT * FROM flex_tournament_meta WHERE tournament_id=?", (tid,))
            if not r: raise ValueError("Brak konfiguracji turnieju.")
            r["draw"] = json.loads(r["draw_json"]); r["extra"] = json.loads(r["extra_json"]); r["team_pool"] = json.loads(r["team_pool_json"])
            return r

    def _meta_extra_conn(self, conn, tid: str) -> tuple[dict, dict]:
        meta = self._fetchone(conn, "SELECT * FROM flex_tournament_meta WHERE tournament_id=?", (tid,))
        if not meta: raise ValueError("Brak konfiguracji turnieju.")
        extra = json.loads(meta["extra_json"] or "{}")
        return meta, extra

    def reveal_draft_order(self, tid: str) -> None:
        with self.connect() as conn:
            t=self._fetchone(conn,"SELECT phase FROM tournaments WHERE id=?",(tid,))
            if not t or t["phase"]!="draft_order": raise ValueError("Losowanie kolejności nie jest już dostępne.")
            meta,extra=self._meta_extra_conn(conn,tid)
            extra["draft_order_revealed"]=True
            conn.execute(self._sql("UPDATE flex_tournament_meta SET extra_json=? WHERE tournament_id=?"),(json.dumps(extra),tid))

    def reroll_draft_order(self, tid: str) -> None:
        rng=random.SystemRandom()
        with self.connect() as conn:
            t=self._fetchone(conn,"SELECT phase FROM tournaments WHERE id=?",(tid,))
            if not t or t["phase"]!="draft_order": raise ValueError("Kolejność jest już zamknięta.")
            picked=self._fetchone(conn,"SELECT COUNT(*) AS c FROM tournament_players WHERE tournament_id=? AND team_revealed=1",(tid,))
            if picked and int(picked["c"]): raise ValueError("Draft drużyn już się rozpoczął.")
            rows=self._fetchall(conn,"SELECT player_id FROM tournament_players WHERE tournament_id=? ORDER BY team_reveal_order",(tid,))
            pids=[r["player_id"] for r in rows]; old=pids.copy()
            for _ in range(30):
                rng.shuffle(pids)
                if pids!=old: break
            for i,pid in enumerate(pids,1):
                conn.execute(self._sql("UPDATE tournament_players SET team_reveal_order=?,tie_order=? WHERE tournament_id=? AND player_id=?"),(i,i,tid,pid))
            meta,extra=self._meta_extra_conn(conn,tid)
            extra["draft_order_revealed"]=True
            extra["draft_redraw_count"]=int(extra.get("draft_redraw_count",0))+1
            conn.execute(self._sql("UPDATE flex_tournament_meta SET extra_json=? WHERE tournament_id=?"),(json.dumps(extra),tid))

    def confirm_draft_order(self, tid: str) -> None:
        with self.connect() as conn:
            t=self._fetchone(conn,"SELECT phase FROM tournaments WHERE id=?",(tid,))
            if not t or t["phase"]!="draft_order": raise ValueError("Kolejność jest już zatwierdzona.")
            meta,extra=self._meta_extra_conn(conn,tid)
            if not extra.get("draft_order_revealed"): raise ValueError("Najpierw wylosuj kolejność.")
            conn.execute(self._sql("UPDATE tournaments SET phase='team_draft' WHERE id=?"),(tid,))

    @staticmethod
    def _norm_team_name(value: str) -> str:
        return " ".join(str(value or "").strip().casefold().replace("ł","l").split())

    def available_draft_teams(self, tid: str) -> list[str]:
        with self.connect() as conn:
            meta=self._fetchone(conn,"SELECT team_pool_json FROM flex_tournament_meta WHERE tournament_id=?",(tid,))
            if not meta: return []
            pool=json.loads(meta["team_pool_json"]); fixed=[x for x in pool if "Dowolna drużyna" not in x]
            picked=self._fetchall(conn,"SELECT team FROM tournament_players WHERE tournament_id=? AND team_revealed=1",(tid,))
            picked_names=[r["team"] for r in picked]
            fixed_norm={self._norm_team_name(x):x for x in fixed}; used_fixed={self._norm_team_name(x) for x in picked_names if self._norm_team_name(x) in fixed_norm}
            out=[x for x in fixed if self._norm_team_name(x) not in used_fixed]
            wildcard_used=any(self._norm_team_name(x) not in fixed_norm for x in picked_names)
            wildcard=next((x for x in pool if "Dowolna drużyna" in x),None)
            if wildcard and not wildcard_used: out.append(wildcard)
            return out

    def draft_pick(self, tid: str, player_id: str, slot: str, wildcard_name: str = "") -> bool:
        with self.connect() as conn:
            t=self._fetchone(conn,"SELECT phase FROM tournaments WHERE id=?",(tid,))
            if not t or t["phase"]!="team_draft": raise ValueError("Draft drużyn nie jest aktywny.")
            current=self._fetchone(conn,"SELECT player_id FROM tournament_players WHERE tournament_id=? AND team_revealed=0 ORDER BY team_reveal_order LIMIT 1",(tid,))
            if not current: return True
            if current["player_id"]!=player_id: raise ValueError("Teraz wybiera inny gracz.")
            meta=self._fetchone(conn,"SELECT team_pool_json FROM flex_tournament_meta WHERE tournament_id=?",(tid,)); pool=json.loads(meta["team_pool_json"])
            fixed=[x for x in pool if "Dowolna drużyna" not in x]; wildcard=next((x for x in pool if "Dowolna drużyna" in x),None)
            picked=self._fetchall(conn,"SELECT team FROM tournament_players WHERE tournament_id=? AND team_revealed=1",(tid,)); picked_names=[r["team"] for r in picked]
            fixed_norm={self._norm_team_name(x):x for x in fixed}; picked_norm={self._norm_team_name(x) for x in picked_names}
            if slot==wildcard:
                if any(self._norm_team_name(x) not in fixed_norm for x in picked_names): raise ValueError("Wild Card został już wykorzystany.")
                team=self._validate_wildcard_team_conn(conn,tid,wildcard_name,player_id)
            else:
                if slot not in fixed: raise ValueError("Nieprawidłowy wybór drużyny.")
                if self._norm_team_name(slot) in picked_norm: raise ValueError("Ta drużyna została już wybrana.")
                team=slot
            conn.execute(self._sql("UPDATE tournament_players SET team=?,team_revealed=1 WHERE tournament_id=? AND player_id=?"),(team,tid,player_id))
            left=self._fetchone(conn,"SELECT COUNT(*) AS c FROM tournament_players WHERE tournament_id=? AND team_revealed=0",(tid,))
            finished=not left or int(left["c"])==0
            if finished: conn.execute(self._sql("UPDATE tournaments SET phase='structure_draw' WHERE id=?"),(tid,))
            return finished

    def reveal_next_team(self, tid: str) -> dict | None:
        with self.connect() as conn:
            meta,extra=self._meta_extra_conn(conn,tid)
            pending=extra.get("pending_wildcard")
            if pending: return {**pending,"wildcard":True}
            row=self._fetchone(conn,"""SELECT tp.player_id,tp.team,p.name FROM tournament_players tp JOIN players p ON p.id=tp.player_id
                WHERE tp.tournament_id=? AND tp.team_revealed=0 ORDER BY tp.team_reveal_order LIMIT 1""",(tid,))
            if not row: return None
            if "Dowolna drużyna" in str(row.get("team") or ""):
                pending={"player_id":row["player_id"],"name":row["name"],"team":row["team"]}
                extra["pending_wildcard"]=pending
                conn.execute(self._sql("UPDATE flex_tournament_meta SET extra_json=? WHERE tournament_id=?"),(json.dumps(extra),tid))
                return {**pending,"wildcard":True}
            conn.execute(self._sql("UPDATE tournament_players SET team_revealed=1 WHERE tournament_id=? AND player_id=?"),(tid,row["player_id"]))
            return {"player_id":row["player_id"],"name":row["name"],"team":row["team"],"wildcard":False}

    def pending_wildcard(self, tid: str) -> dict | None:
        with self.connect() as conn:
            _meta,extra=self._meta_extra_conn(conn,tid)
            p=extra.get("pending_wildcard")
            return {**p,"wildcard":True} if p else None

    def confirm_wildcard_team(self, tid: str, player_id: str, team_name: str) -> str:
        with self.connect() as conn:
            meta,extra=self._meta_extra_conn(conn,tid); pending=extra.get("pending_wildcard")
            if not pending or pending.get("player_id")!=player_id: raise ValueError("Nie ma aktywnego wyboru Wild Card dla tego gracza.")
            team=self._validate_wildcard_team_conn(conn,tid,team_name,player_id)
            conn.execute(self._sql("UPDATE tournament_players SET team=?,team_revealed=1 WHERE tournament_id=? AND player_id=?"),(team,tid,player_id))
            extra.pop("pending_wildcard",None)
            conn.execute(self._sql("UPDATE flex_tournament_meta SET extra_json=? WHERE tournament_id=?"),(json.dumps(extra),tid))
            return team

    def start_structure_draw(self, tid: str) -> None:
        with self.connect() as conn:
            left = self._fetchone(conn, "SELECT COUNT(*) AS c FROM tournament_players WHERE tournament_id=? AND team_revealed=0", (tid,))
            if left and int(left["c"]) > 0: raise ValueError("Najpierw zakończ losowanie drużyn.")
            conn.execute(self._sql("UPDATE tournaments SET phase='structure_draw' WHERE id=?"), (tid,))

    def _apply_draw_groups_conn(self, conn, tid: str, format_key: str, draw: dict) -> None:
        # Reset group metadata first.
        conn.execute(self._sql("UPDATE tournament_players SET group_name='', tie_order=team_reveal_order WHERE tournament_id=?"), (tid,))
        if format_key in ("groups6", "groups6_full", "groups7", "groups7_sf", "groups8_sf", "groups8_barrage"):
            for g in ("A","B"):
                members = group_members(draw, g)
                for i,pid in enumerate(members,1):
                    conn.execute(self._sql("UPDATE tournament_players SET group_name=?, tie_order=? WHERE tournament_id=? AND player_id=?"), (g,i,tid,pid))
        elif format_key in ("league4_final", "league5_final"):
            for i,pid in enumerate(draw["slots"].values(),1):
                conn.execute(self._sql("UPDATE tournament_players SET group_name='L', tie_order=? WHERE tournament_id=? AND player_id=?"), (i,tid,pid))

    def reveal_structure(self, tid: str) -> None:
        with self.connect() as conn:
            meta = self._fetchone(conn, "SELECT * FROM flex_tournament_meta WHERE tournament_id=?", (tid,))
            draw = json.loads(meta["draw_json"])
            self._apply_draw_groups_conn(conn, tid, meta["format_key"], draw)
            conn.execute(self._sql("UPDATE flex_tournament_meta SET draw_revealed=1 WHERE tournament_id=?"), (tid,))

    def reroll_structure(self, tid: str) -> None:
        rng = random.SystemRandom()
        with self.connect() as conn:
            meta = self._fetchone(conn, "SELECT * FROM flex_tournament_meta WHERE tournament_id=?", (tid,))
            t = self._fetchone(conn, "SELECT is_test FROM tournaments WHERE id=?", (tid,))
            rows = self._fetchall(conn, "SELECT tp.player_id,p.name FROM tournament_players tp JOIN players p ON p.id=tp.player_id WHERE tp.tournament_id=? ORDER BY tp.team_reveal_order", (tid,))
            pids = [r["player_id"] for r in rows]
            names = [r["name"] for r in rows]
            old = json.loads(meta["draw_json"]); new = old
            for _ in range(50):
                cand = build_draw(pids, meta["format_key"], rng)
                if draw_signature(cand) != draw_signature(old): new = cand; break
            # Re-read carry-over fairness using the tournament's current Test/Official
            # status, so correcting a mistaken status before the start also corrects
            # the next reroll's BYE weighting and opening-order context.
            carry=self._cross_tournament_priority_conn(conn,names,pids,bool(int((t or {}).get("is_test") or 0)))
            extra = self._extra_for_format(meta["format_key"], rng)
            if carry:
                new=apply_cross_tournament_bye_priority(new,meta["format_key"],carry.get("priority_by_player_id") or {},rng)
                extra["cross_tournament_priority"]=carry
            conn.execute(self._sql("UPDATE flex_tournament_meta SET draw_json=?,extra_json=?,draw_revealed=1,redraw_count=redraw_count+1 WHERE tournament_id=?"), (json.dumps(new),json.dumps(extra),tid))
            self._apply_draw_groups_conn(conn, tid, meta["format_key"], new)

    def confirm_structure(self, tid: str) -> None:
        rng = random.SystemRandom()
        with self.connect() as conn:
            meta = self._fetchone(conn, "SELECT * FROM flex_tournament_meta WHERE tournament_id=?", (tid,))
            if not int(meta["draw_revealed"]): raise ValueError("Najpierw wykonaj losowanie.")
            draw = json.loads(meta["draw_json"]); extra = json.loads(meta["extra_json"])
            t = self._fetchone(conn, "SELECT is_test FROM tournaments WHERE id=?", (tid,))
            rows = self._fetchall(conn, "SELECT tp.player_id,p.name FROM tournament_players tp JOIN players p ON p.id=tp.player_id WHERE tp.tournament_id=? ORDER BY tp.team_reveal_order", (tid,))
            pids=[r["player_id"] for r in rows]; names=[r["name"] for r in rows]
            carry_info=self._cross_tournament_priority_conn(conn,names,pids,bool(int((t or {}).get("is_test") or 0)))
            if carry_info: extra["cross_tournament_priority"]=carry_info
            else: extra.pop("cross_tournament_priority",None)
            plan = schedule_for_format(draw, meta["format_key"], extra, rng)
            carry=(carry_info.get("priority_by_player_id") or {}) if carry_info else {}
            preferred=optimize_opening_order(plan,carry,rng) if carry else [dict(x) for x in plan]
            extra["match_play_order"]=[int(x["match_no"]) for x in preferred]
            conn.execute(self._sql("UPDATE flex_tournament_meta SET extra_json=? WHERE tournament_id=?"),(json.dumps(extra),tid))
            conn.execute(self._sql("DELETE FROM matches WHERE tournament_id=?"), (tid,))
            conn.execute(self._sql("DELETE FROM flex_match_sources WHERE tournament_id=?"), (tid,))
            for item in plan:
                conn.execute(self._sql("INSERT INTO matches (id,tournament_id,match_no,stage,group_name) VALUES (?,?,?,?,?)"), (str(uuid.uuid4()),tid,item["match_no"],item["stage"],item["group_name"]))
                conn.execute(self._sql("INSERT INTO flex_match_sources (tournament_id,match_no,home_source,away_source) VALUES (?,?,?,?)"), (tid,item["match_no"],item["home"],item["away"]))
            conn.execute(self._sql("UPDATE tournaments SET phase='active' WHERE id=?"), (tid,))
            self._resolve_all_conn(conn, tid, meta["format_key"])

    def _matches_conn(self, conn, tid: str) -> list[dict]:
        return self._fetchall(conn, """SELECT m.*, hp.name home_name, ap.name away_name, htp.team home_team, atp.team away_team
            FROM matches m LEFT JOIN players hp ON hp.id=m.home_player_id LEFT JOIN players ap ON ap.id=m.away_player_id
            LEFT JOIN tournament_players htp ON htp.tournament_id=m.tournament_id AND htp.player_id=m.home_player_id
            LEFT JOIN tournament_players atp ON atp.tournament_id=m.tournament_id AND atp.player_id=m.away_player_id
            WHERE m.tournament_id=? ORDER BY m.match_no""", (tid,))

    def matches(self, tid: str) -> list[dict]:
        with self.connect() as conn: return self._matches_conn(conn,tid)

    def bundle(self, tid: str) -> dict:
        with self.connect() as conn:
            t = self._fetchone(conn, "SELECT * FROM tournaments WHERE id=?", (tid,))
            meta = self._fetchone(conn, "SELECT * FROM flex_tournament_meta WHERE tournament_id=?", (tid,))
            players = self._fetchall(conn, "SELECT tp.*,p.name FROM tournament_players tp JOIN players p ON p.id=tp.player_id WHERE tp.tournament_id=? ORDER BY tp.team_reveal_order", (tid,))
            matches = self._matches_conn(conn,tid)
            if meta:
                meta["draw"] = json.loads(meta["draw_json"]); meta["extra"] = json.loads(meta["extra_json"]); meta["team_pool"] = json.loads(meta["team_pool_json"])
            return {"tournament":t,"meta":meta,"players":players,"matches":matches}

    def _loser_of(self, match: dict | None) -> str | None:
        if not match or not match.get("winner_player_id"): return None
        h,a = match.get("home_player_id"), match.get("away_player_id")
        return a if match["winner_player_id"] == h else h

    def _table_from_conn(self, conn, tid: str, group: str) -> list[dict]:
        players = self._fetchall(conn, "SELECT tp.*,p.name FROM tournament_players tp JOIN players p ON p.id=tp.player_id WHERE tp.tournament_id=? AND tp.group_name=?", (tid,group))
        # Tables must only use their own league/group phase. Knockout matches must never alter an already-finished table.
        matches = [m for m in self._matches_conn(conn,tid) if m.get("group_name") == group]
        ids = [p["player_id"] for p in players]; ties = {p["player_id"]:int(p["tie_order"]) for p in players}; names={p["player_id"]:p["name"] for p in players}; teams={p["player_id"]:p["team"] for p in players}
        rows = group_table(ids,matches,ties)
        for r in rows: r["name"]=names[r["player_id"]]; r["team"]=teams[r["player_id"]]
        return rows

    def _resolve_source_conn(self, conn, tid: str, source: str, match_map: dict[int,dict]) -> str | None:
        kind,*rest = source.split(":")
        if kind == "P": return rest[0]
        if kind == "W":
            m=match_map.get(int(rest[0])); return m.get("winner_player_id") if m else None
        if kind == "L": return self._loser_of(match_map.get(int(rest[0])))
        if kind == "POS":
            group,pos = rest[0],int(rest[1]); table=self._table_from_conn(conn,tid,group)
            return table[pos-1]["player_id"] if len(table)>=pos and all(r["m"]>0 for r in table) else None
        if kind == "D5":
            _,extra=self._meta_extra_conn(conn,tid)
            chosen=extra.get("d5_opponent_match")
            if not chosen: return None
            no=int(chosen) if rest[0]=="E_OPP" else (2 if int(chosen)==1 else 1)
            m=match_map.get(no); return m.get("winner_player_id") if m else None
        if kind in ("D7W","D8W"):
            _,extra=self._meta_extra_conn(conn,tid)
            draw=extra.get("d7_wb_draw" if kind=="D7W" else "d8_wb_draw") or {}
            mapped=draw.get(rest[0])
            return self._resolve_source_conn(conn,tid,mapped,match_map) if mapped else None
        if kind == "D7":
            _,extra=self._meta_extra_conn(conn,tid); bye=extra.get("d7_lb_bye_match")
            if not bye: return None
            bye=int(bye); remaining=[x for x in (1,2,3) if x!=bye]
            key=rest[0]
            if key=="LB1A": return self._loser_of(match_map.get(remaining[0]))
            if key=="LB1B": return self._loser_of(match_map.get(remaining[1]))
            if key=="LB_BYE": return self._loser_of(match_map.get(bye))
            pairing=extra.get("d7_pairing") or {}
            if key=="PAIR_BYE":
                no=pairing.get("bye_vs_sf")
                return self._loser_of(match_map.get(int(no))) if no else None
            if key=="PAIR_W6":
                no=pairing.get("w6_vs_sf")
                return self._loser_of(match_map.get(int(no))) if no else None
        if kind in ("G6","G6F","G7","G7S","G8S","G8B"):
            _,extra=self._meta_extra_conn(conn,tid); mapped=(extra.get("playoff_sources") or {}).get(source)
            return self._resolve_source_conn(conn,tid,mapped,match_map) if mapped else None
        return None

    def _resolve_all_conn(self, conn, tid: str, format_key: str) -> None:
        # Iterate because resolving one match may make later W/L sources available.
        for _ in range(4):
            rows = self._fetchall(conn, "SELECT * FROM matches WHERE tournament_id=? ORDER BY match_no", (tid,)); mm={int(m["match_no"]):m for m in rows}
            srcs = self._fetchall(conn, "SELECT * FROM flex_match_sources WHERE tournament_id=? ORDER BY match_no", (tid,))
            changed=False
            for src in srcs:
                no=int(src["match_no"]); m=mm[no]
                # Conditional reset final is hidden unless the losers-bracket challenger won the first final.
                if m["stage"] == "RESET_FINAL":
                    if format_key not in ("double5", "double7", "double8"):
                        continue
                    first_no = {"double5":8,"double7":12,"double8":14}[format_key]
                    first = mm.get(first_no)
                    if not first or not first.get("winner_player_id") or first.get("winner_player_id") != first.get("away_player_id"):
                        continue
                if m.get("home_score") is not None: continue
                h=self._resolve_source_conn(conn,tid,src["home_source"],mm); a=self._resolve_source_conn(conn,tid,src["away_source"],mm)
                if h and a and (m.get("home_player_id")!=h or m.get("away_player_id")!=a):
                    conn.execute(self._sql("UPDATE matches SET home_player_id=?,away_player_id=? WHERE tournament_id=? AND match_no=?"),(h,a,tid,no)); changed=True
            if not changed: break

    @staticmethod
    def _match_played(match: dict | None) -> bool:
        return bool(match and match.get("home_score") is not None)

    def double5_draw_state(self, tid: str) -> dict | None:
        with self.connect() as conn:
            meta,extra=self._meta_extra_conn(conn,tid)
            if meta["format_key"]!="double5": return None
            mm={int(m["match_no"]):m for m in self._matches_conn(conn,tid)}
            if not (self._match_played(mm.get(1)) and self._match_played(mm.get(2))) or self._match_played(mm.get(3)): return None
            chosen=extra.get("d5_opponent_match")
            players={r["player_id"]:r["name"] for r in self._fetchall(conn,"SELECT tp.player_id,p.name FROM tournament_players tp JOIN players p ON p.id=tp.player_id WHERE tp.tournament_id=?",(tid,))}
            draw=json.loads(meta["draw_json"]); e_id=draw["slots"]["E"]
            candidates=[]
            for no in (1,2):
                m=mm[no]; pid=m.get("winner_player_id")
                if pid: candidates.append({"match_no":no,"player_id":pid,"name":players.get(pid,"?")})
            selected=next((c for c in candidates if chosen and int(c["match_no"])==int(chosen)),None)
            return {"player_id":e_id,"player_name":players.get(e_id,"?"),"candidates":candidates,"selected":selected,"ack":bool(extra.get("d5_draw_ack"))}

    def reveal_double5_opponent(self, tid: str) -> dict:
        rng=random.SystemRandom()
        with self.connect() as conn:
            meta,extra=self._meta_extra_conn(conn,tid)
            if meta["format_key"]!="double5": raise ValueError("To losowanie nie dotyczy tego formatu.")
            mm={int(m["match_no"]):m for m in self._fetchall(conn,"SELECT * FROM matches WHERE tournament_id=? ORDER BY match_no",(tid,))}
            if not (self._match_played(mm.get(1)) and self._match_played(mm.get(2))): raise ValueError("Najpierw rozegraj oba mecze pierwszej rundy.")
            if not extra.get("d5_opponent_match"):
                extra["d5_opponent_match"]=rng.choice([1,2]); extra["d5_draw_ack"]=False
                conn.execute(self._sql("UPDATE flex_tournament_meta SET extra_json=? WHERE tournament_id=?"),(json.dumps(extra),tid))
            self._resolve_all_conn(conn,tid,"double5")
            chosen=int(extra["d5_opponent_match"]); m=mm[chosen]
            pid=m.get("winner_player_id"); name=self._fetchone(conn,"SELECT name FROM players WHERE id=?",(pid,)) if pid else None
            return {"match_no":chosen,"player_id":pid,"name":name["name"] if name else "?"}

    def ack_double5_draw(self, tid: str) -> None:
        with self.connect() as conn:
            meta,extra=self._meta_extra_conn(conn,tid)
            if extra.get("d5_opponent_match"):
                extra["d5_draw_ack"]=True
                conn.execute(self._sql("UPDATE flex_tournament_meta SET extra_json=? WHERE tournament_id=?"),(json.dumps(extra),tid))

    def double_wb_draw_state(self, tid: str) -> dict | None:
        with self.connect() as conn:
            meta,extra=self._meta_extra_conn(conn,tid); fmt=meta["format_key"]
            if fmt not in ("double7","double8"): return None
            mm={int(m["match_no"]):m for m in self._matches_conn(conn,tid)}
            first_nos=(1,2,3) if fmt=="double7" else (1,2,3,4)
            first_next=4 if fmt=="double7" else 5
            if not all(self._match_played(mm.get(i)) for i in first_nos) or self._match_played(mm.get(first_next)): return None
            key="d7_wb_draw" if fmt=="double7" else "d8_wb_draw"; ack_key=key+"_ack"
            draw=extra.get(key)
            if not draw:return {"format_key":fmt,"pairs":[],"ack":False,"selected":False}
            pairs=[]
            for no in ((4,5) if fmt=="double7" else (5,6)):
                m=mm.get(no)
                if m and m.get("home_player_id") and m.get("away_player_id"):
                    pairs.append({"match_no":no,"stage":"WB","home_name":m.get("home_name"),"away_name":m.get("away_name")})
            return {"format_key":fmt,"pairs":pairs,"ack":bool(extra.get(ack_key)),"selected":True}

    def reveal_double_wb_draw(self, tid: str) -> dict:
        rng=random.SystemRandom()
        with self.connect() as conn:
            meta,extra=self._meta_extra_conn(conn,tid); fmt=meta["format_key"]
            if fmt not in ("double7","double8"): raise ValueError("To losowanie nie dotyczy tego formatu.")
            mm={int(m["match_no"]):m for m in self._fetchall(conn,"SELECT * FROM matches WHERE tournament_id=? ORDER BY match_no",(tid,))}
            first_nos=(1,2,3) if fmt=="double7" else (1,2,3,4)
            if not all(self._match_played(mm.get(i)) for i in first_nos): raise ValueError("Najpierw dokończ pierwszą rundę Winners Bracket.")
            key="d7_wb_draw" if fmt=="double7" else "d8_wb_draw"; ack_key=key+"_ack"
            if not extra.get(key):
                sources=[f"W:{i}" for i in first_nos]
                if fmt=="double7":
                    draw=json.loads(meta["draw_json"]); sources.append(f"P:{draw['slots']['G']}")
                rng.shuffle(sources)
                pairs=[sources[:2],sources[2:4]]
                # Zwycięzca ostatniego meczu pierwszej rundy powinien dostać jeden pełny mecz odpoczynku.
                last_source=f"W:{first_nos[-1]}"
                if last_source in pairs[0]: pairs=[pairs[1],pairs[0]]
                if fmt=="double7":
                    mapped={"M4H":pairs[0][0],"M4A":pairs[0][1],"M5H":pairs[1][0],"M5A":pairs[1][1]}
                else:
                    mapped={"M5H":pairs[0][0],"M5A":pairs[0][1],"M6H":pairs[1][0],"M6A":pairs[1][1]}
                extra[key]=mapped; extra[ack_key]=False
                conn.execute(self._sql("UPDATE flex_tournament_meta SET extra_json=? WHERE tournament_id=?"),(json.dumps(extra),tid))
            self._resolve_all_conn(conn,tid,fmt)
            rows=self._matches_conn(conn,tid); by_no={int(m["match_no"]):m for m in rows}
            out=[]
            for no in ((4,5) if fmt=="double7" else (5,6)):
                m=by_no[no];out.append({"match_no":no,"stage":"WB","home_name":m.get("home_name"),"away_name":m.get("away_name")})
            return {"format_key":fmt,"pairs":out}

    def ack_double_wb_draw(self, tid: str) -> None:
        with self.connect() as conn:
            meta,extra=self._meta_extra_conn(conn,tid);fmt=meta["format_key"]
            if fmt not in ("double7","double8"): return
            key="d7_wb_draw" if fmt=="double7" else "d8_wb_draw"; ack_key=key+"_ack"
            if extra.get(key):
                extra[ack_key]=True
                conn.execute(self._sql("UPDATE flex_tournament_meta SET extra_json=? WHERE tournament_id=?"),(json.dumps(extra),tid))

    def double7_lb_draw_state(self, tid: str) -> dict | None:
        with self.connect() as conn:
            meta,extra=self._meta_extra_conn(conn,tid)
            if meta["format_key"]!="double7": return None
            mm={int(m["match_no"]):m for m in self._matches_conn(conn,tid)}
            if not all(self._match_played(mm.get(i)) for i in (1,2,3)) or self._match_played(mm.get(4)): return None
            players={r["player_id"]:r["name"] for r in self._fetchall(conn,"SELECT tp.player_id,p.name FROM tournament_players tp JOIN players p ON p.id=tp.player_id WHERE tp.tournament_id=?",(tid,))}
            candidates=[]
            for no in (1,2,3):
                pid=self._loser_of(mm.get(no))
                if pid: candidates.append({"match_no":no,"player_id":pid,"name":players.get(pid,"?")})
            bye=extra.get("d7_lb_bye_match"); selected=next((c for c in candidates if bye and int(c["match_no"])==int(bye)),None)
            return {"candidates":candidates,"selected":selected,"ack":bool(extra.get("d7_lb_draw_ack"))}

    def reveal_double7_lb_bye(self, tid: str) -> dict:
        rng=random.SystemRandom()
        with self.connect() as conn:
            meta,extra=self._meta_extra_conn(conn,tid)
            if meta["format_key"]!="double7": raise ValueError("To losowanie nie dotyczy tego formatu.")
            mm={int(m["match_no"]):m for m in self._fetchall(conn,"SELECT * FROM matches WHERE tournament_id=? ORDER BY match_no",(tid,))}
            if not all(self._match_played(mm.get(i)) for i in (1,2,3)): raise ValueError("Najpierw rozegraj trzy mecze pierwszej rundy.")
            if not extra.get("d7_lb_bye_match"):
                carry=(extra.get("cross_tournament_priority") or {}).get("priority_by_player_id") or {}
                loser_by_match={no:self._loser_of(mm.get(no)) for no in (1,2,3)}
                chosen_pid=weighted_bye_choice([pid for pid in loser_by_match.values() if pid],carry,rng) if carry else None
                chosen_no=next((no for no,pid in loser_by_match.items() if chosen_pid and pid==chosen_pid),None)
                extra["d7_lb_bye_match"]=int(chosen_no or rng.choice([1,2,3])); extra["d7_lb_draw_ack"]=False; extra["d7_pairing"]=None
                conn.execute(self._sql("UPDATE flex_tournament_meta SET extra_json=? WHERE tournament_id=?"),(json.dumps(extra),tid))
            self._resolve_all_conn(conn,tid,"double7")
            no=int(extra["d7_lb_bye_match"]); pid=self._loser_of(mm.get(no)); name=self._fetchone(conn,"SELECT name FROM players WHERE id=?",(pid,)) if pid else None
            return {"match_no":no,"player_id":pid,"name":name["name"] if name else "?"}

    def ack_double7_lb_draw(self, tid: str) -> None:
        with self.connect() as conn:
            meta,extra=self._meta_extra_conn(conn,tid)
            if extra.get("d7_lb_bye_match"):
                extra["d7_lb_draw_ack"]=True
                conn.execute(self._sql("UPDATE flex_tournament_meta SET extra_json=? WHERE tournament_id=?"),(json.dumps(extra),tid))

    @staticmethod
    def _pair_seen(a: str | None, b: str | None, matches: list[dict]) -> int:
        if not a or not b: return 99
        return sum(1 for m in matches if m.get("home_player_id") and {m.get("home_player_id"),m.get("away_player_id")}=={a,b} and m.get("home_score") is not None)

    def _prepare_double7_pairing_conn(self, conn, tid: str) -> None:
        meta,extra=self._meta_extra_conn(conn,tid)
        if meta["format_key"]!="double7" or extra.get("d7_pairing") or not extra.get("d7_lb_bye_match"): return
        rows=self._fetchall(conn,"SELECT * FROM matches WHERE tournament_id=? ORDER BY match_no",(tid,)); mm={int(m["match_no"]):m for m in rows}
        if not all(self._match_played(mm.get(i)) for i in (4,5,6)): return
        bye_player=self._loser_of(mm[int(extra["d7_lb_bye_match"])])
        w6=mm[6].get("winner_player_id"); l4=self._loser_of(mm[4]); l5=self._loser_of(mm[5])
        first_round=[mm[1],mm[2],mm[3]]
        # Two possible crossings. Minimize rematches; if equally good, make it genuinely random.
        options=[(4,5),(5,4)]
        scored=[]
        for bye_sf,w6_sf in options:
            sf_bye=l4 if bye_sf==4 else l5; sf_w6=l4 if w6_sf==4 else l5
            score=self._pair_seen(bye_player,sf_bye,first_round)+self._pair_seen(w6,sf_w6,first_round)
            scored.append((score,bye_sf,w6_sf))
        best=min(x[0] for x in scored); best_opts=[x for x in scored if x[0]==best]; _,bye_sf,w6_sf=random.SystemRandom().choice(best_opts)
        extra["d7_pairing"]={"bye_vs_sf":bye_sf,"w6_vs_sf":w6_sf}
        conn.execute(self._sql("UPDATE flex_tournament_meta SET extra_json=? WHERE tournament_id=?"),(json.dumps(extra),tid))

    def _prepare_group_playoffs_conn(self, conn, tid: str) -> dict | None:
        meta,extra=self._meta_extra_conn(conn,tid); fmt=meta["format_key"]
        group_formats=("groups6","groups6_full","groups7","groups7_sf","groups8_sf","groups8_barrage")
        if fmt not in group_formats: return None
        if extra.get("playoff_sources"): return extra
        rows=self._fetchall(conn,"SELECT * FROM matches WHERE tournament_id=? ORDER BY match_no",(tid,)); mm={int(m["match_no"]):m for m in rows}
        if fmt in ("groups6","groups6_full"): group_end=6
        elif fmt in ("groups7","groups7_sf"): group_end=9
        else: group_end=12
        if not all(self._match_played(mm.get(i)) for i in range(1,group_end+1)): return None
        ta=self._table_from_conn(conn,tid,"A"); tb=self._table_from_conn(conn,tid,"B")

        def last_play(pid):
            nums=[i for i in range(1,group_end+1) if pid in (mm[i].get("home_player_id"),mm[i].get("away_player_id"))]
            return max(nums) if nums else 0

        last_group={mm[group_end].get("home_player_id"),mm[group_end].get("away_player_id")}
        orders=[[0,1],[1,0]]

        if fmt in ("groups6","groups7_sf","groups8_sf"):
            pairings=[("POS:A:1","POS:B:2"),("POS:B:1","POS:A:2")]
            ids=[(ta[0]["player_id"],tb[1]["player_id"]),(tb[0]["player_id"],ta[1]["player_id"])]
            start_no={"groups6":7,"groups7_sf":10,"groups8_sf":13}[fmt]

            def cost(order):
                waits=[]
                for slot,i in enumerate(order):
                    mno=start_no+slot
                    waits += [mno-last_play(pid)-1 for pid in ids[i]]
                b2b=sum(pid in last_group for pid in ids[order[0]])
                if fmt=="groups8_sf":
                    return (b2b, -min(waits), -sum(waits))
                return (max(waits),b2b,sum(waits))

            order=min(orders,key=cost); p1,p2=[pairings[i] for i in order]
            if fmt=="groups6":
                src={"G6:SF7H":p1[0],"G6:SF7A":p1[1],"G6:SF8H":p2[0],"G6:SF8A":p2[1]}
            elif fmt=="groups7_sf":
                src={"G7S:SF10H":p1[0],"G7S:SF10A":p1[1],"G7S:SF11H":p2[0],"G7S:SF11A":p2[1]}
            else:
                src={"G8S:SF13H":p1[0],"G8S:SF13A":p1[1],"G8S:SF14H":p2[0],"G8S:SF14A":p2[1]}
            display=[p1,p2]

        elif fmt=="groups8_barrage":
            # Ścieżka A: 1A czeka na zwycięzcę 2B–3A. Ścieżka B analogicznie.
            paths=[("POS:B:2","POS:A:3","POS:A:1"),("POS:A:2","POS:B:3","POS:B:1")]
            ids=[(tb[1]["player_id"],ta[2]["player_id"],ta[0]["player_id"]),(ta[1]["player_id"],tb[2]["player_id"],tb[0]["player_id"])]

            def cost(order):
                first=ids[order[0]][:2]
                b2b=sum(pid in last_group for pid in first)
                waits=[]
                for slot,i in enumerate(order):
                    bno=13+slot; sfno=15+slot; bh,ba,direct=ids[i]
                    waits += [bno-last_play(bh)-1,bno-last_play(ba)-1,sfno-last_play(direct)-1]
                return (b2b, -min(waits), -sum(waits))

            order=min(orders,key=cost); p1,p2=[paths[i] for i in order]
            src={
                "G8B:B13H":p1[0],"G8B:B13A":p1[1],"G8B:B14H":p2[0],"G8B:B14A":p2[1],
                "G8B:SF15H":p1[2],"G8B:SF16H":p2[2],
            }
            display=[p1[:2],p2[:2]]

        else:
            pairings=[("POS:A:2","POS:B:3","POS:B:1"),("POS:B:2","POS:A:3","POS:A:1")]
            ids=[(ta[1]["player_id"],tb[2]["player_id"],tb[0]["player_id"]),(tb[1]["player_id"],ta[2]["player_id"],ta[0]["player_id"])]
            qbase,sfbase=(7,9) if fmt=="groups6_full" else (10,12)

            def cost(order):
                waits=[]
                for slot,i in enumerate(order):
                    qno=qbase+slot; sfno=sfbase+slot; qh,qa,direct=ids[i]
                    waits += [qno-last_play(qh)-1,qno-last_play(qa)-1,sfno-last_play(direct)-1]
                b2b=sum(pid in last_group for pid in ids[order[0]][:2])
                return (max(waits),b2b,sum(waits))

            order=min(orders,key=cost); q1,q2=[pairings[i] for i in order]
            if fmt=="groups6_full":
                src={"G6F:QF7H":q1[0],"G6F:QF7A":q1[1],"G6F:QF8H":q2[0],"G6F:QF8A":q2[1],"G6F:SF9H":q1[2],"G6F:SF10H":q2[2]}
            else:
                src={"G7:QF10H":q1[0],"G7:QF10A":q1[1],"G7:QF11H":q2[0],"G7:QF11A":q2[1],"G7:SF12H":q1[2],"G7:SF13H":q2[2]}
            display=[q1[:2],q2[:2]]

        extra["playoff_sources"]=src; extra["playoff_display_sources"]=display
        conn.execute(self._sql("UPDATE flex_tournament_meta SET extra_json=? WHERE tournament_id=?"),(json.dumps(extra),tid))
        self._resolve_all_conn(conn,tid,fmt)
        return extra

    def group_playoff_reveal_state(self, tid: str) -> dict | None:
        with self.connect() as conn:
            extra=self._prepare_group_playoffs_conn(conn,tid)
            if not extra or extra.get("playoff_reveal_ack"): return None
            meta=self._fetchone(conn,"SELECT format_key FROM flex_tournament_meta WHERE tournament_id=?",(tid,)); fmt=meta["format_key"]
            rows=self._matches_conn(conn,tid); mm={int(m["match_no"]):m for m in rows}
            if fmt in ("groups6","groups6_full"): start=7
            elif fmt in ("groups7","groups7_sf"): start=10
            else: start=13
            pairs=[]
            for no in range(start,start+2):
                m=mm[no]
                if m.get("home_player_id") and m.get("away_player_id"):
                    pairs.append({"match_no":no,"stage":m["stage"],"home_name":m.get("home_name"),"away_name":m.get("away_name")})
            tables={"A":self._table_from_conn(conn,tid,"A"),"B":self._table_from_conn(conn,tid,"B")}
            direct=[]
            if fmt in ("groups6_full","groups7","groups8_barrage"):
                direct=[{"group":"A","name":tables["A"][0]["name"]},{"group":"B","name":tables["B"][0]["name"]}]
            return {"format_key":fmt,"pairs":pairs,"direct":direct}

    def ack_group_playoffs(self, tid: str) -> None:
        with self.connect() as conn:
            meta,extra=self._meta_extra_conn(conn,tid); extra=self._prepare_group_playoffs_conn(conn,tid) or extra
            extra["playoff_reveal_ack"]=True
            conn.execute(self._sql("UPDATE flex_tournament_meta SET extra_json=? WHERE tournament_id=?"),(json.dumps(extra),tid))
            self._resolve_all_conn(conn,tid,meta["format_key"])

    def team_scorer_options(self, team_name: str) -> list[dict]:
        nt=self._norm_team_name(team_name)
        with self.connect() as conn:
            rows=self._fetchall(conn,"""SELECT ts.scorer_name,ts.seed_rank,
                    COALESCE(SUM(CASE WHEN t.is_test=0 THEN ms.goals ELSE 0 END),0) AS goals,
                    COUNT(DISTINCT CASE WHEN t.is_test=0 AND ms.goals>0 THEN ms.tournament_id||':'||ms.match_no END) AS scoring_matches
                FROM team_scorers ts
                LEFT JOIN match_scorers ms ON ms.normalized_team=ts.normalized_team AND ms.normalized_scorer=ts.normalized_scorer
                LEFT JOIN tournaments t ON t.id=ms.tournament_id
                WHERE ts.normalized_team=?
                GROUP BY ts.scorer_name,ts.seed_rank
                ORDER BY goals DESC,scoring_matches DESC,ts.seed_rank ASC,ts.scorer_name ASC""",(nt,))
            return [{"name":r["scorer_name"],"goals":int(r.get("goals") or 0),"scoring_matches":int(r.get("scoring_matches") or 0)} for r in rows]

    def scorer_roster_teams(self) -> list[str]:
        """Drużyny dostępne w panelu zarządzania listami strzelców."""
        with self.connect() as conn:
            rows=self._fetchall(conn,"SELECT team_name,COUNT(*) AS c FROM team_scorers GROUP BY team_name ORDER BY c DESC,team_name")
        out=[]; seen=set()
        for team in list(SCORER_SEEDS.keys())+[r["team_name"] for r in rows]:
            clean=" ".join(str(team or "").strip().split()); norm=self._norm_team_name(clean)
            if clean and norm not in seen:
                seen.add(norm); out.append(clean)
        return out

    def add_team_scorers(self, team_name: str, names: list[str]) -> int:
        """Dodaje zawodników do stałej listy podpowiedzi danej drużyny."""
        team=" ".join(str(team_name or "").strip().split())
        if not team: raise ValueError("Wybierz drużynę.")
        nt=self._norm_team_name(team); added=0
        with self.connect() as conn:
            for raw in names:
                clean=" ".join(str(raw or "").strip().split())
                if not clean: continue
                ns=self._norm_scorer_name(clean)
                if not ns: continue
                exists=self._fetchone(conn,"SELECT id FROM team_scorers WHERE normalized_team=? AND normalized_scorer=?",(nt,ns))
                if exists: continue
                conn.execute(self._sql("INSERT INTO team_scorers (id,team_name,normalized_team,scorer_name,normalized_scorer,seed_rank,created_at) VALUES (?,?,?,?,?,999,?)"),
                             (str(uuid.uuid4()),team,nt,clean,ns,now_iso()))
                added+=1
        return added

    def _save_scorers_conn(self, conn, tid: str, match_no: int, hs: int, ass: int, scorers: dict | None) -> None:
        conn.execute(self._sql("DELETE FROM match_scorers WHERE tournament_id=? AND match_no=?"),(tid,match_no))
        if not scorers: return
        cleaned={"home":[],"away":[]}
        for side in ("home","away"):
            team=" ".join(str(scorers.get(side,{}).get("team") or "").strip().split())
            for item in scorers.get(side,{}).get("items",[]):
                name=" ".join(str(item.get("name") or "").strip().split()); goals=int(item.get("goals") or 0)
                if not name or goals<=0: continue
                cleaned[side].append((team,name,goals))
        for side,items in cleaned.items():
            for team,name,goals in items:
                nt=self._norm_team_name(team); ns=self._norm_scorer_name(name)
                exists=self._fetchone(conn,"SELECT id FROM team_scorers WHERE normalized_team=? AND normalized_scorer=?",(nt,ns))
                if not exists:
                    conn.execute(self._sql("INSERT INTO team_scorers (id,team_name,normalized_team,scorer_name,normalized_scorer,seed_rank,created_at) VALUES (?,?,?,?,?,999,?)"),
                                 (str(uuid.uuid4()),team,nt,name,ns,now_iso()))
                conn.execute(self._sql("INSERT INTO match_scorers (id,tournament_id,match_no,side,team_name,normalized_team,scorer_name,normalized_scorer,goals) VALUES (?,?,?,?,?,?,?,?,?)"),
                             (str(uuid.uuid4()),tid,match_no,side,team,nt,name,ns,goals))

    def scorer_stats(self) -> list[dict]:
        with self.connect() as conn:
            rows=self._fetchall(conn,"""SELECT ms.normalized_scorer,MIN(ms.scorer_name) AS scorer_name,SUM(ms.goals) AS goals,
                    COUNT(DISTINCT ms.tournament_id||':'||ms.match_no) AS matches_scored
                FROM match_scorers ms JOIN tournaments t ON t.id=ms.tournament_id
                WHERE t.status='completed' AND t.is_test=0
                GROUP BY ms.normalized_scorer ORDER BY goals DESC,matches_scored DESC,scorer_name""")
            teams=self._fetchall(conn,"""SELECT ms.normalized_scorer,ms.team_name,SUM(ms.goals) AS goals
                FROM match_scorers ms JOIN tournaments t ON t.id=ms.tournament_id
                WHERE t.status='completed' AND t.is_test=0
                GROUP BY ms.normalized_scorer,ms.team_name ORDER BY goals DESC""")
        by=defaultdict(list)
        for r in teams: by[r["normalized_scorer"]].append((r["team_name"],int(r["goals"])))
        return [{"name":r["scorer_name"],"goals":int(r["goals"]),"matches_scored":int(r["matches_scored"]),
                 "teams":", ".join(x[0] for x in by[r["normalized_scorer"]])} for r in rows]

    def _official_matches_conn(self, conn, exclude_tid: str | None = None) -> list[dict]:
        sql="""SELECT m.*,t.completed_at,t.created_at,hp.name home_name,ap.name away_name,htp.team home_team,atp.team away_team
            FROM matches m JOIN tournaments t ON t.id=m.tournament_id
            LEFT JOIN players hp ON hp.id=m.home_player_id LEFT JOIN players ap ON ap.id=m.away_player_id
            LEFT JOIN tournament_players htp ON htp.tournament_id=m.tournament_id AND htp.player_id=m.home_player_id
            LEFT JOIN tournament_players atp ON atp.tournament_id=m.tournament_id AND atp.player_id=m.away_player_id
            WHERE t.status='completed' AND t.is_test=0 AND m.home_score IS NOT NULL"""
        params=()
        if exclude_tid:
            sql += " AND m.tournament_id<>?"; params=(exclude_tid,)
        sql += " ORDER BY COALESCE(m.played_at,t.completed_at,t.created_at),m.tournament_id,m.match_no"
        return self._fetchall(conn,sql,params)

    @staticmethod
    def _result_for_player(m: dict, pid: str) -> str:
        if m.get("winner_player_id"): return "W" if m["winner_player_id"]==pid else "L"
        hs,ass=int(m["home_score"]),int(m["away_score"])
        if hs==ass:return "D"
        winner=m["home_player_id"] if hs>ass else m["away_player_id"]
        return "W" if winner==pid else "L"

    def match_context(self, home_pid: str, away_pid: str) -> dict:
        with self.connect() as conn:
            matches=self._official_matches_conn(conn)
        pair=[m for m in matches if {m.get("home_player_id"),m.get("away_player_id")}=={home_pid,away_pid}]
        hw=sum(self._result_for_player(m,home_pid)=="W" for m in pair); aw=sum(self._result_for_player(m,away_pid)=="W" for m in pair)
        draws=sum(self._result_for_player(m,home_pid)=="D" for m in pair)
        def form(pid):
            own=[m for m in matches if pid in (m.get("home_player_id"),m.get("away_player_id"))]
            return [self._result_for_player(m,pid) for m in own[-5:]]
        last=pair[-1] if pair else None
        total=len(pair)
        return {"meetings":total,"home_wins":hw,"away_wins":aw,"draws":draws,"home_form":form(home_pid),"away_form":form(away_pid),
                "rivalry": total>=5 and abs(hw-aw)<=2,"derby":total>=10,"last":last}

    def recent_forms(self) -> list[dict]:
        with self.connect() as conn:
            matches=self._official_matches_conn(conn)
            names={r["id"]:r["name"] for r in self._fetchall(conn,"SELECT id,name FROM players")}
        seq=defaultdict(list)
        for m in matches:
            for pid in (m.get("home_player_id"),m.get("away_player_id")):
                if pid: seq[pid].append(self._result_for_player(m,pid))
        out=[]
        for pid,vals in seq.items():
            last=vals[-5:]; w=last.count("W");d=last.count("D");l=last.count("L")
            out.append({"player_id":pid,"name":names.get(pid,"?"),"form":last,"w":w,"d":d,"l":l,"points":w*3+d})
        out.sort(key=lambda x:(x["points"],x["w"],-x["l"]),reverse=True)
        return out

    def h2h(self, pid1: str, pid2: str) -> dict:
        with self.connect() as conn:
            matches=self._official_matches_conn(conn)
            names={r["id"]:r["name"] for r in self._fetchall(conn,"SELECT id,name FROM players WHERE id IN (?,?)",(pid1,pid2))}
        pair=[m for m in matches if {m.get("home_player_id"),m.get("away_player_id")}=={pid1,pid2}]
        w1=sum(self._result_for_player(m,pid1)=="W" for m in pair); w2=sum(self._result_for_player(m,pid2)=="W" for m in pair); d=len(pair)-w1-w2
        gf1=gf2=0
        recent=[]
        for m in pair:
            if m["home_player_id"]==pid1: gf1+=int(m["home_score"]);gf2+=int(m["away_score"])
            else: gf1+=int(m["away_score"]);gf2+=int(m["home_score"])
            recent.append({"home":m.get("home_name"),"away":m.get("away_name"),"score":f"{m['home_score']}:{m['away_score']}","played_at":m.get("played_at")})
        return {"name1":names.get(pid1,"?"),"name2":names.get(pid2,"?"),"meetings":len(pair),"wins1":w1,"wins2":w2,"draws":d,"gf1":gf1,"gf2":gf2,"recent":recent[-5:][::-1]}

    def _records_from_conn(self, conn, exclude_tid: str | None = None) -> dict:
        matches=self._official_matches_conn(conn,exclude_tid)
        if not matches:return {}
        tids=sorted({m["tournament_id"] for m in matches})
        qmarks=','.join('?' for _ in tids)
        trs=self._fetchall(conn,f"SELECT id,champion_player_id,completed_at,created_at FROM tournaments WHERE id IN ({qmarks}) ORDER BY COALESCE(completed_at,created_at)",tuple(tids))
        tps=self._fetchall(conn,f"SELECT tournament_id,player_id FROM tournament_players WHERE tournament_id IN ({qmarks})",tuple(tids))
        players={r["id"]:r["name"] for r in self._fetchall(conn,"SELECT id,name FROM players")}
        finals=[m for m in matches if m["stage"]=="FINAL"]
        ps=defaultdict(lambda:{"tournaments":0,"titles":0,"finals":0,"w":0,"d":0,"l":0,"gf":0,"ga":0})
        for tp in tps: ps[tp["player_id"]]["tournaments"]+=1
        for t in trs:
            if t.get("champion_player_id"): ps[t["champion_player_id"]]["titles"]+=1
        for m in finals:
            for pid in (m.get("home_player_id"),m.get("away_player_id")):
                if pid: ps[pid]["finals"]+=1
        per_t=defaultdict(lambda:defaultdict(int)); pair=defaultdict(lambda:{"a":None,"b":None,"aw":0,"bw":0,"d":0,"n":0})
        sequence=defaultdict(list)
        for m in matches:
            h,a=m.get("home_player_id"),m.get("away_player_id");
            if not h or not a:continue
            hs,ass=int(m["home_score"]),int(m["away_score"]); ps[h]["gf"]+=hs;ps[h]["ga"]+=ass;ps[a]["gf"]+=ass;ps[a]["ga"]+=hs
            per_t[m["tournament_id"]][h]+=hs;per_t[m["tournament_id"]][a]+=ass
            rh=self._result_for_player(m,h); ra=self._result_for_player(m,a); sequence[h].append(rh);sequence[a].append(ra)
            if rh=="W":ps[h]["w"]+=1;ps[a]["l"]+=1
            elif ra=="W":ps[a]["w"]+=1;ps[h]["l"]+=1
            else:ps[h]["d"]+=1;ps[a]["d"]+=1
            k=tuple(sorted((h,a))); rec=pair[k]; rec["a"],rec["b"]=k;rec["n"]+=1
            rr=self._result_for_player(m,k[0]);
            if rr=="W":rec["aw"]+=1
            elif rr=="L":rec["bw"]+=1
            else:rec["d"]+=1
        def best_player(key, eligible=lambda pid,v:True, reverse=True):
            vals=[(pid,v) for pid,v in ps.items() if eligible(pid,v)]
            if not vals:return None
            pid,v=(max(vals,key=lambda x:key(x[0],x[1])) if reverse else min(vals,key=lambda x:key(x[0],x[1])))
            return {"player_id":pid,"name":players.get(pid,"?"),**v}
        def longest(seq, allowed):
            best=cur=0
            for r in seq:
                if r in allowed:cur+=1;best=max(best,cur)
                else:cur=0
            return best
        win_streak=max(((longest(seq,{"W"}),pid) for pid,seq in sequence.items()),default=(0,None))
        unbeaten=max(((longest(seq,{"W","D"}),pid) for pid,seq in sequence.items()),default=(0,None))
        winless=max(((longest(seq,{"D","L"}),pid) for pid,seq in sequence.items()),default=(0,None))
        biggest=max(matches,key=lambda m:abs(int(m["home_score"])-int(m["away_score"])))
        goals_match=max(matches,key=lambda m:int(m["home_score"])+int(m["away_score"]))
        one_t=max(((g,pid,tid) for tid,d in per_t.items() for pid,g in d.items()),default=(0,None,None))
        # consecutive championship streak across chronological official tournaments
        title_best=(0,None); cur_pid=None;cur=0
        for t in trs:
            pid=t.get("champion_player_id")
            if pid and pid==cur_pid:cur+=1
            elif pid:cur_pid=pid;cur=1
            else:cur_pid=None;cur=0
            if cur>title_best[0]:title_best=(cur,pid)
        pair_vals=list(pair.values())
        frequent=max(pair_vals,key=lambda r:r["n"],default=None)
        balanced=min((r for r in pair_vals if r["n"]>=5),key=lambda r:(abs(r["aw"]-r["bw"]),-r["n"]),default=None)
        dominance=max((r for r in pair_vals if r["n"]>=3),key=lambda r:(abs(r["aw"]-r["bw"]),r["n"]),default=None)
        def pair_desc(r):
            if not r:return None
            return {**r,"name_a":players.get(r["a"],"?"),"name_b":players.get(r["b"],"?")}
        most_titles=best_player(lambda pid,v:(v["titles"],v["finals"],v["w"]))
        most_finals=best_player(lambda pid,v:(v["finals"],v["titles"],v["w"]))
        most_wins=best_player(lambda pid,v:(v["w"],v["titles"]))
        most_goals=best_player(lambda pid,v:(v["gf"],v["w"]))
        best_pct=best_player(lambda pid,v:(v["w"]/(v["w"]+v["d"]+v["l"]),v["w"]),lambda pid,v:(v["w"]+v["d"]+v["l"])>=10)
        best_avg=best_player(lambda pid,v:(v["gf"]/(v["w"]+v["d"]+v["l"]),v["gf"]),lambda pid,v:(v["w"]+v["d"]+v["l"])>=5)
        best_def=best_player(lambda pid,v:-(v["ga"]/(v["w"]+v["d"]+v["l"])),lambda pid,v:(v["w"]+v["d"]+v["l"])>=5)
        lost_final=best_player(lambda pid,v:(v["finals"]-v["titles"],v["finals"]))
        return {
            "most_titles":most_titles,"most_finals":most_finals,"most_wins":most_wins,"most_goals":most_goals,
            "best_win_pct":best_pct,"best_goal_avg":best_avg,"best_defense":best_def,"most_lost_finals":lost_final,
            "win_streak":{"name":players.get(win_streak[1],"?"),"value":win_streak[0]},
            "unbeaten_streak":{"name":players.get(unbeaten[1],"?"),"value":unbeaten[0]},
            "winless_streak":{"name":players.get(winless[1],"?"),"value":winless[0]},
            "biggest_win":{"home":biggest.get("home_name"),"away":biggest.get("away_name"),"score":f"{biggest['home_score']}:{biggest['away_score']}","margin":abs(int(biggest["home_score"])-int(biggest["away_score"]))},
            "highest_scoring":{"home":goals_match.get("home_name"),"away":goals_match.get("away_name"),"score":f"{goals_match['home_score']}:{goals_match['away_score']}","goals":int(goals_match["home_score"])+int(goals_match["away_score"])},
            "goals_one_tournament":{"name":players.get(one_t[1],"?"),"value":one_t[0]},
            "consecutive_titles":{"name":players.get(title_best[1],"?"),"value":title_best[0]},
            "most_frequent_h2h":pair_desc(frequent),"balanced_rivalry":pair_desc(balanced),"h2h_dominance":pair_desc(dominance),
        }

    def all_time_records(self) -> dict:
        with self.connect() as conn:return self._records_from_conn(conn)

    def tournament_summary(self, tid: str) -> dict:
        with self.connect() as conn:
            t=self._fetchone(conn,"SELECT * FROM tournaments WHERE id=?",(tid,)); matches=self._matches_conn(conn,tid)
            meta=self._fetchone(conn,"SELECT * FROM flex_tournament_meta WHERE tournament_id=?",(tid,))
            players={p["player_id"]:p for p in self._fetchall(conn,"SELECT tp.*,p.name FROM tournament_players tp JOIN players p ON p.id=tp.player_id WHERE tp.tournament_id=?",(tid,))}
            scorer_rows=self._fetchall(conn,"SELECT scorer_name,SUM(goals) AS goals FROM match_scorers WHERE tournament_id=? GROUP BY scorer_name ORDER BY goals DESC,scorer_name",(tid,))
            previous=self._records_from_conn(conn,exclude_tid=tid) if t and not int(t.get("is_test") or 0) else {}
            prior_matches=self._official_matches_conn(conn,exclude_tid=tid) if t and not int(t.get("is_test") or 0) else []
        played=[m for m in matches if m.get("home_score") is not None]
        ps=defaultdict(lambda:{"w":0,"d":0,"l":0,"gf":0,"ga":0})
        for m in played:
            h,a=m["home_player_id"],m["away_player_id"];hs,ass=int(m["home_score"]),int(m["away_score"])
            ps[h]["gf"]+=hs;ps[h]["ga"]+=ass;ps[a]["gf"]+=ass;ps[a]["ga"]+=hs
            rh=self._result_for_player(m,h)
            if rh=="W":ps[h]["w"]+=1;ps[a]["l"]+=1
            elif rh=="L":ps[a]["w"]+=1;ps[h]["l"]+=1
            else:ps[h]["d"]+=1;ps[a]["d"]+=1
        champ=t.get("champion_player_id") if t else None
        fmt=(meta or {}).get("format_key")
        finals=[m for m in played if m["stage"] in ("FINAL","RESET_FINAL")]
        last_final=finals[-1] if finals else None
        runner=None
        if last_final and champ: runner=last_final["away_player_id"] if last_final["home_player_id"]==champ else last_final["home_player_id"]
        top=max(ps.items(),key=lambda x:(x[1]["gf"],x[1]["w"]),default=(None,{})); defense=min(ps.items(),key=lambda x:(x[1]["ga"]/(sum(x[1][k] for k in ("w","d","l")) or 1),x[1]["ga"]),default=(None,{})); form=max(ps.items(),key=lambda x:(x[1]["w"],x[1]["gf"]-x[1]["ga"]),default=(None,{}))
        biggest=max(played,key=lambda m:abs(int(m["home_score"])-int(m["away_score"])),default=None); high=max(played,key=lambda m:int(m["home_score"])+int(m["away_score"]),default=None)
        stage_weight={"FINAL":8,"RESET_FINAL":8,"SF":6,"WB_FINAL":6,"LB_FINAL":6,"QF":4,"BARRAGE":4,"WB":2,"LB":2,"LEAGUE":0,"GROUP":0}
        def match_fun_score(m):
            hs,ass=int(m["home_score"]),int(m["away_score"]); total=hs+ass; margin=abs(hs-ass)
            pens=8 if m.get("home_penalties") is not None and m.get("away_penalties") is not None else 0
            close=5 if margin<=1 else (2 if margin==2 else 0)
            return total*2+pens+close+stage_weight.get(m.get("stage"),1)
        match_of_tournament=max(played,key=match_fun_score,default=None)
        pair_hist=defaultdict(lambda:{"n":0,"wins":defaultdict(int)})
        for pm in prior_matches:
            a,b=pm.get("home_player_id"),pm.get("away_player_id")
            if not a or not b:continue
            k=tuple(sorted((a,b)));pair_hist[k]["n"]+=1
            if pm.get("winner_player_id"):pair_hist[k]["wins"][pm["winner_player_id"]]+=1
        rivalry=None
        candidates=[]
        for m in played:
            a,b=m.get("home_player_id"),m.get("away_player_id");k=tuple(sorted((a,b))) if a and b else None
            if not k:continue
            h=pair_hist.get(k);
            if not h:continue
            wa=h["wins"].get(a,0);wb=h["wins"].get(b,0)
            if h["n"]>=5 and abs(wa-wb)<=2:candidates.append((h["n"],m))
        if candidates:
            _n,rm=max(candidates,key=lambda x:x[0]);rivalry={"home":rm.get("home_name"),"away":rm.get("away_name"),"score":f"{rm['home_score']}:{rm['away_score']}"}
        new_records=[]
        if not int(t.get("is_test") or 0) and previous:
            prev_margin=(previous.get("biggest_win") or {}).get("margin",-1)
            if biggest and abs(int(biggest["home_score"])-int(biggest["away_score"]))>prev_margin:new_records.append(f"Największe zwycięstwo: {biggest['home_name']} {biggest['home_score']}:{biggest['away_score']} {biggest['away_name']}")
            prev_goals=(previous.get("goals_one_tournament") or {}).get("value",-1)
            if top[0] and top[1].get("gf",0)>prev_goals:new_records.append(f"Gole jednego gracza w turnieju: {players[top[0]]['name']} — {top[1]['gf']}")

        by_no={int(m["match_no"]):m for m in played}
        def place_payload(pid):
            if not pid: return None
            row=ps.get(pid,{})
            return {
                "name": players.get(pid,{}).get("name"),
                "team": players.get(pid,{}).get("team"),
                "w": int(row.get("w",0)), "d": int(row.get("d",0)), "l": int(row.get("l",0)),
                "gf": int(row.get("gf",0)), "ga": int(row.get("ga",0)), "gd": int(row.get("gf",0))-int(row.get("ga",0)),
            }
        def rank_same_stage(pids):
            clean=[pid for pid in pids if pid]
            clean=sorted(set(clean), key=lambda pid:(ps[pid]["w"], ps[pid]["gf"]-ps[pid]["ga"], ps[pid]["gf"], -ps[pid]["ga"]), reverse=True)
            return clean

        third_pid=fourth_pid=None
        if fmt in ("league4_final","league5_final"):
            ids=list(players.keys());ties={pid:int(players[pid].get("tie_order") or 9999) for pid in ids}
            league_matches=[m for m in played if m.get("stage")=="LEAGUE"]
            table=group_table(ids,league_matches,ties)
            if len(table)>=3:third_pid=table[2]["player_id"]
            if len(table)>=4:fourth_pid=table[3]["player_id"]
        elif fmt in ("groups6","groups6_full","groups7","groups7_sf","groups8_sf","groups8_barrage"):
            sf_losers=rank_same_stage([self._loser_of(m) for m in played if m.get("stage")=="SF"])
            if sf_losers: third_pid=sf_losers[0]
            if len(sf_losers)>1: fourth_pid=sf_losers[1]
        elif fmt=="double5":
            third_pid=self._loser_of(by_no.get(7)); fourth_pid=self._loser_of(by_no.get(6))
        elif fmt=="double7":
            third_pid=self._loser_of(by_no.get(11)); fourth_pid=self._loser_of(by_no.get(10))
        elif fmt=="double8":
            third_pid=self._loser_of(by_no.get(13)); fourth_pid=self._loser_of(by_no.get(12))

        return {"champion":players.get(champ,{}).get("name"),"runner_up":players.get(runner,{}).get("name"),
                "champion_record": ({"w":int(ps[champ]["w"]),"d":int(ps[champ]["d"]),"l":int(ps[champ]["l"]),"gf":int(ps[champ]["gf"]),"ga":int(ps[champ]["ga"])} if champ else {"w":0,"d":0,"l":0,"gf":0,"ga":0}),
                "top_goals":{"name":players.get(top[0],{}).get("name"),"value":top[1].get("gf",0)},
                "best_defense":{"name":players.get(defense[0],{}).get("name"),"value":defense[1].get("ga",0)},
                "best_form":{"name":players.get(form[0],{}).get("name"),"wins":form[1].get("w",0)},
                "biggest":({"home":biggest.get("home_name"),"away":biggest.get("away_name"),"score":f"{biggest['home_score']}:{biggest['away_score']}"} if biggest else None),
                "highest":({"home":high.get("home_name"),"away":high.get("away_name"),"score":f"{high['home_score']}:{high['away_score']}"} if high else None),
                "real_top_scorer":({"name":scorer_rows[0]["scorer_name"],"goals":int(scorer_rows[0]["goals"])} if scorer_rows else None),
                "match_of_tournament":({"home":match_of_tournament.get("home_name"),"away":match_of_tournament.get("away_name"),
                    "score":f"{match_of_tournament['home_score']}:{match_of_tournament['away_score']}","stage":match_of_tournament.get("stage"),"group_name":match_of_tournament.get("group_name"),
                    "home_penalties":match_of_tournament.get("home_penalties"),"away_penalties":match_of_tournament.get("away_penalties")} if match_of_tournament else None),
                "third_place": place_payload(third_pid),
                "fourth_place": place_payload(fourth_pid),
                "rivalry_match":rivalry,"new_records":new_records}

    def tournament_export_meta(self, tid: str) -> dict:
        with self.connect() as conn:
            t=self._fetchone(conn,"SELECT * FROM tournaments WHERE id=?",(tid,))
            meta=self._fetchone(conn,"SELECT player_count,format_key FROM flex_tournament_meta WHERE tournament_id=?",(tid,))
            if not t: return {}
            official_no=None
            if not int(t.get("is_test") or 0):
                rows=self._fetchall(conn,"""
                    SELECT id FROM tournaments
                    WHERE status='completed' AND is_test=0
                    ORDER BY COALESCE(completed_at,created_at), created_at, id
                """)
                for i,row in enumerate(rows,1):
                    if row.get("id")==tid:
                        official_no=i
                        break
            return {
                "official_no": official_no,
                "is_test": int(t.get("is_test") or 0),
                "created_at": t.get("created_at"),
                "completed_at": t.get("completed_at"),
                "player_count": int(meta.get("player_count") or 0) if meta else 0,
                "format_key": meta.get("format_key") if meta else None,
            }

    def current_match_from(self, matches: list[dict], extra: dict | None = None) -> dict | None:
        order=[int(x) for x in ((extra or {}).get("match_play_order") or [])]
        rank={no:i for i,no in enumerate(order)}
        ordered=sorted(matches,key=lambda m:(rank.get(int(m.get("match_no") or 0),10_000+int(m.get("match_no") or 0)),int(m.get("match_no") or 0)))
        for m in ordered:
            if m.get("home_player_id") and m.get("away_player_id") and m.get("home_score") is None:
                return m
        return None

    def next_ready_match_from(self, matches: list[dict], current_no: int, extra: dict | None = None) -> dict | None:
        order=[int(x) for x in ((extra or {}).get("match_play_order") or [])]
        rank={no:i for i,no in enumerate(order)}
        current_rank=rank.get(int(current_no),-1)
        ordered=sorted(matches,key=lambda m:(rank.get(int(m.get("match_no") or 0),10_000+int(m.get("match_no") or 0)),int(m.get("match_no") or 0)))
        later=[m for m in ordered if rank.get(int(m.get("match_no") or 0),10_000+int(m.get("match_no") or 0))>current_rank]
        for m in later:
            if m.get("home_player_id") and m.get("away_player_id") and m.get("home_score") is None:
                return m
        return None

    def save_result(self, tid: str, match_no: int, hs: int, ass: int, hp: int | None = None, ap: int | None = None, scorers: dict | None = None) -> None:
        with self.connect() as conn:
            m=self._fetchone(conn,"SELECT * FROM matches WHERE tournament_id=? AND match_no=?",(tid,match_no))
            if not m or not m.get("home_player_id") or not m.get("away_player_id"): raise ValueError("Ten mecz nie ma jeszcze ustalonych graczy.")
            if hs<0 or ass<0: raise ValueError("Wynik nie może być ujemny.")
            meta=self._fetchone(conn,"SELECT format_key FROM flex_tournament_meta WHERE tournament_id=?",(tid,)); fmt=meta["format_key"]
            if fmt in ("double5","double7","double8") and m["stage"]=="FINAL" and hs<1:
                raise ValueError("Zwycięzca Winners Bracket zaczyna finał od 1:0.")
            knockout = m["stage"] not in ("GROUP","LEAGUE")
            if knockout and hs==ass and (hp is None or ap is None or hp==ap): raise ValueError("W fazie pucharowej remis wymaga karnych.")
            winner=winner_from_result(hs,ass,m["home_player_id"],m["away_player_id"],hp,ap)
            self._save_scorers_conn(conn,tid,match_no,hs,ass,scorers)
            conn.execute(self._sql("UPDATE matches SET home_score=?,away_score=?,home_penalties=?,away_penalties=?,winner_player_id=?,played_at=? WHERE tournament_id=? AND match_no=?"),(hs,ass,hp,ap,winner,now_iso(),tid,match_no))
            if fmt=="double7": self._prepare_double7_pairing_conn(conn,tid)
            if fmt in ("groups6","groups6_full","groups7","groups7_sf","groups8_sf","groups8_barrage"): self._prepare_group_playoffs_conn(conn,tid)
            self._resolve_all_conn(conn,tid,fmt)
            self._maybe_finish_conn(conn,tid,fmt)

    def _maybe_finish_conn(self, conn, tid: str, fmt: str) -> None:
        rows=self._fetchall(conn,"SELECT * FROM matches WHERE tournament_id=? ORDER BY match_no",(tid,)); mm={int(m["match_no"]):m for m in rows}
        champion=None
        if fmt=="league4_final": champion=mm[7].get("winner_player_id")
        elif fmt=="league5_final": champion=mm[11].get("winner_player_id")
        elif fmt=="groups6": champion=mm[9].get("winner_player_id")
        elif fmt=="groups6_full": champion=mm[11].get("winner_player_id")
        elif fmt=="groups7": champion=mm[14].get("winner_player_id")
        elif fmt=="groups7_sf": champion=mm[12].get("winner_player_id")
        elif fmt=="groups8_sf": champion=mm[15].get("winner_player_id")
        elif fmt=="groups8_barrage": champion=mm[17].get("winner_player_id")
        elif fmt=="double5": champion=mm[8].get("winner_player_id")
        elif fmt=="double7": champion=mm[12].get("winner_player_id")
        elif fmt=="double8": champion=mm[14].get("winner_player_id")
        if champion:
            conn.execute(self._sql("UPDATE tournaments SET status='completed',phase='completed',champion_player_id=?,completed_at=? WHERE id=?"),(champion,now_iso(),tid))

    def undo_last_result(self, tid: str) -> int | None:
        # Undo the match actually played last, not the numerically highest match.
        # This is required because cross-tournament fairness may change play order.
        with self.connect() as conn:
            last=self._fetchone(conn,"SELECT * FROM matches WHERE tournament_id=? AND home_score IS NOT NULL ORDER BY played_at DESC,match_no DESC LIMIT 1",(tid,))
            if not last:return None
            no=int(last["match_no"])
            conn.execute(self._sql("DELETE FROM match_scorers WHERE tournament_id=? AND match_no=?"),(tid,no))
            conn.execute(self._sql("UPDATE matches SET home_score=NULL,away_score=NULL,home_penalties=NULL,away_penalties=NULL,winner_player_id=NULL,played_at=NULL WHERE tournament_id=? AND match_no=?"),(tid,no))
            # Rebuild participants only for unplayed games. Earlier played games are left untouched,
            # even when their logical match number is higher than the match being undone.
            conn.execute(self._sql("UPDATE matches SET home_player_id=NULL,away_player_id=NULL WHERE tournament_id=? AND home_score IS NULL"),(tid,))
            conn.execute(self._sql("UPDATE tournaments SET status='active',phase='active',champion_player_id=NULL,completed_at=NULL WHERE id=?"),(tid,))
            meta,extra=self._meta_extra_conn(conn,tid);fmt=meta["format_key"]
            if fmt=="double5" and no<=2:
                extra["d5_opponent_match"]=None;extra["d5_draw_ack"]=False
            if fmt=="double7":
                if no<=3:
                    extra["d7_wb_draw"]=None;extra["d7_wb_draw_ack"]=False
                    extra["d7_lb_bye_match"]=None;extra["d7_lb_draw_ack"]=False;extra["d7_pairing"]=None
                elif no<=6:
                    extra["d7_pairing"]=None
            if fmt=="double8" and no<=4:
                extra["d8_wb_draw"]=None;extra["d8_wb_draw_ack"]=False
            group_end=6 if fmt in ("groups6","groups6_full") else (9 if fmt in ("groups7","groups7_sf") else (12 if fmt in ("groups8_sf","groups8_barrage") else 0))
            if group_end and no<=group_end:
                extra.pop("playoff_sources",None);extra.pop("playoff_display_sources",None);extra["playoff_reveal_ack"]=False
            conn.execute(self._sql("UPDATE flex_tournament_meta SET extra_json=? WHERE tournament_id=?"),(json.dumps(extra),tid))
            if fmt=="double7":self._prepare_double7_pairing_conn(conn,tid)
            if fmt in ("groups6","groups6_full","groups7","groups7_sf","groups8_sf","groups8_barrage"):self._prepare_group_playoffs_conn(conn,tid)
            self._resolve_all_conn(conn,tid,fmt)
            return no

    def standings(self, tid: str) -> dict[str,list[dict]]:
        with self.connect() as conn:
            meta=self._fetchone(conn,"SELECT format_key FROM flex_tournament_meta WHERE tournament_id=?",(tid,)); fmt=meta["format_key"]
            if fmt in ("league4_final", "league5_final"): return {"L":self._table_from_conn(conn,tid,"L")}
            if fmt in ("groups6", "groups6_full", "groups7", "groups7_sf", "groups8_sf", "groups8_barrage"): return {"A":self._table_from_conn(conn,tid,"A"),"B":self._table_from_conn(conn,tid,"B")}
            return {}

    def reset_current(self, tid: str) -> None:
        with self.connect() as conn:
            conn.execute(self._sql("DELETE FROM flex_match_sources WHERE tournament_id=?"),(tid,)); conn.execute(self._sql("DELETE FROM match_scorers WHERE tournament_id=?"),(tid,)); conn.execute(self._sql("DELETE FROM matches WHERE tournament_id=?"),(tid,)); conn.execute(self._sql("DELETE FROM tournament_players WHERE tournament_id=?"),(tid,)); conn.execute(self._sql("DELETE FROM flex_tournament_meta WHERE tournament_id=?"),(tid,)); conn.execute(self._sql("DELETE FROM tournaments WHERE id=?"),(tid,)); self._setting_set_conn(conn,CURRENT_KEY,"")

    def start_new(self) -> None:
        with self.connect() as conn: self._setting_set_conn(conn,CURRENT_KEY,"")

    def clear_flex_history(self) -> None:
        with self.connect() as conn:
            ids=[r["tournament_id"] for r in self._fetchall(conn,"SELECT tournament_id FROM flex_tournament_meta")]
            for tid in ids:
                conn.execute(self._sql("DELETE FROM flex_match_sources WHERE tournament_id=?"),(tid,)); conn.execute(self._sql("DELETE FROM match_scorers WHERE tournament_id=?"),(tid,)); conn.execute(self._sql("DELETE FROM matches WHERE tournament_id=?"),(tid,)); conn.execute(self._sql("DELETE FROM tournament_players WHERE tournament_id=?"),(tid,)); conn.execute(self._sql("DELETE FROM tournaments WHERE id=?"),(tid,))
            conn.execute("DELETE FROM flex_tournament_meta")
            self._setting_set_conn(conn,CURRENT_KEY,"")

    def history_locked(self) -> bool:
        with self.connect() as conn:
            return self._setting_get_conn(conn,"fifa_history_locked")=="1"

    def set_history_locked(self, locked: bool) -> None:
        with self.connect() as conn:
            self._setting_set_conn(conn,"fifa_history_locked","1" if locked else "0")

    def last_completed_tournament(self) -> dict | None:
        with self.connect() as conn:
            t=self._fetchone(conn,"""SELECT t.id,t.created_at,t.completed_at,t.champion_player_id,p.name champion_name
                FROM tournaments t LEFT JOIN players p ON p.id=t.champion_player_id
                WHERE t.status='completed' AND t.is_test=0
                ORDER BY COALESCE(t.completed_at,t.created_at) DESC LIMIT 1""")
            if not t: return None
            meta=self._fetchone(conn,"SELECT player_count,format_key FROM flex_tournament_meta WHERE tournament_id=?",(t["id"],))
            if meta:
                t["player_count"]=int(meta["player_count"]); t["format_key"]=meta["format_key"]
            else:
                cnt=self._fetchone(conn,"SELECT COUNT(*) AS c FROM tournament_players WHERE tournament_id=?",(t["id"],))
                t["player_count"]=int(cnt["c"]) if cnt else 0; t["format_key"]="classic6"
            return t

    def _delete_tournament_conn(self, conn, tid: str) -> None:
        conn.execute(self._sql("DELETE FROM flex_match_sources WHERE tournament_id=?"),(tid,))
        conn.execute(self._sql("DELETE FROM match_scorers WHERE tournament_id=?"),(tid,))
        conn.execute(self._sql("DELETE FROM flex_tournament_meta WHERE tournament_id=?"),(tid,))
        conn.execute(self._sql("DELETE FROM matches WHERE tournament_id=?"),(tid,))
        conn.execute(self._sql("DELETE FROM tournament_players WHERE tournament_id=?"),(tid,))
        conn.execute(self._sql("DELETE FROM tournaments WHERE id=?"),(tid,))
        if self._setting_get_conn(conn,CURRENT_KEY)==tid: self._setting_set_conn(conn,CURRENT_KEY,"")

    def delete_last_completed_tournament(self) -> dict | None:
        with self.connect() as conn:
            if self._setting_get_conn(conn,"fifa_history_locked")=="1": raise ValueError("Historia jest zablokowana.")
            t=self._fetchone(conn,"""SELECT t.id,t.created_at,t.completed_at,t.champion_player_id,p.name champion_name
                FROM tournaments t LEFT JOIN players p ON p.id=t.champion_player_id
                WHERE t.status='completed' AND t.is_test=0
                ORDER BY COALESCE(t.completed_at,t.created_at) DESC LIMIT 1""")
            if not t: return None
            cnt=self._fetchone(conn,"SELECT COUNT(*) AS c FROM tournament_players WHERE tournament_id=?",(t["id"],)); t["player_count"]=int(cnt["c"]) if cnt else 0
            self._delete_tournament_conn(conn,t["id"]); return t

    def clear_all_history(self) -> None:
        with self.connect() as conn:
            if self._setting_get_conn(conn,"fifa_history_locked")=="1": raise ValueError("Historia jest zablokowana.")
            conn.execute("DELETE FROM flex_match_sources")
            conn.execute("DELETE FROM match_scorers")
            conn.execute("DELETE FROM flex_tournament_meta")
            conn.execute("DELETE FROM matches")
            conn.execute("DELETE FROM tournament_players")
            conn.execute("DELETE FROM tournaments")
            # Keep players and remembered lineups. Only live tournament pointers are cleared.
            self._setting_set_conn(conn,CURRENT_KEY,"")

    def team_stats(self) -> list[dict]:
        """Statystyki klubów z zakończonych turniejów oficjalnych (Classic + Flex)."""
        with self.connect() as conn:
            matches=self._official_matches_conn(conn)
            champions=self._fetchall(conn,"""SELECT tp.team,tp.player_id,p.name
                FROM tournaments t
                JOIN tournament_players tp ON tp.tournament_id=t.id AND tp.player_id=t.champion_player_id
                JOIN players p ON p.id=tp.player_id
                WHERE t.status='completed' AND t.is_test=0 AND tp.team<>''""")
        agg=defaultdict(lambda:{"display":None,"matches":0,"w":0,"d":0,"l":0,"gf":0,"ga":0,"titles":0,"players":set()})
        by_player=defaultdict(lambda:{"display":None,"player_name":None,"matches":0,"w":0,"d":0,"l":0,"gf":0,"ga":0})
        for m in matches:
            for side in ("home","away"):
                pid=m.get(f"{side}_player_id"); team=" ".join(str(m.get(f"{side}_team") or "").strip().split())
                if not pid or not team: continue
                nt=self._norm_team_name(team); rec=agg[nt]; rec["display"]=rec["display"] or team; rec["matches"]+=1; rec["players"].add(pid)
                hs,ass=int(m["home_score"]),int(m["away_score"])
                gf,ga=(hs,ass) if side=="home" else (ass,hs)
                rec["gf"]+=gf; rec["ga"]+=ga
                result=self._result_for_player(m,pid)
                rec[{"W":"w","D":"d","L":"l"}[result]]+=1
                pr=by_player[(nt,pid)]; pr["display"]=pr["display"] or team; pr["player_name"]=m.get(f"{side}_name") or "?"; pr["matches"]+=1; pr["gf"]+=gf; pr["ga"]+=ga; pr[{"W":"w","D":"d","L":"l"}[result]]+=1
        for c in champions:
            team=" ".join(str(c.get("team") or "").strip().split())
            if team:
                nt=self._norm_team_name(team); agg[nt]["display"]=agg[nt]["display"] or team; agg[nt]["titles"]+=1; agg[nt]["players"].add(c["player_id"])
        best_by_team={}
        for (nt,pid),v in by_player.items():
            played=v["matches"] or 1; score=(v["w"],v["w"]/played,v["gf"]-v["ga"],v["gf"])
            old=best_by_team.get(nt)
            if not old or score>old[0]: best_by_team[nt]=(score,v)
        out=[]
        for nt,v in agg.items():
            if not v["matches"]: continue
            bp=(best_by_team.get(nt) or (None,{}))[1]
            out.append({"team":v["display"] or nt,"matches":v["matches"],"w":v["w"],"d":v["d"],"l":v["l"],"gf":v["gf"],"ga":v["ga"],
                        "gd":v["gf"]-v["ga"],"titles":v["titles"],"players":len(v["players"]),"win_pct":round(v["w"]/v["matches"]*100,1),
                        "goals_per_match":round(v["gf"]/v["matches"],2),"best_player":bp.get("player_name") or "—","best_player_wins":bp.get("w",0)})
        out.sort(key=lambda x:(x["titles"],x["w"],x["win_pct"],x["gd"]),reverse=True)
        return out

    def player_profile(self, pid: str) -> dict | None:
        """Profil gracza i historia jego oficjalnych meczów."""
        base=next((x for x in self.all_time_stats() if x["player_id"]==pid),None)
        if not base:return None
        with self.connect() as conn:
            matches=self._official_matches_conn(conn)
        own=[m for m in matches if pid in (m.get("home_player_id"),m.get("away_player_id"))]
        teams=defaultdict(lambda:{"matches":0,"w":0,"d":0,"l":0,"gf":0,"ga":0,"display":None})
        opponents=defaultdict(lambda:{"name":None,"meetings":0,"w":0,"d":0,"l":0,"gf":0,"ga":0})
        history=[]
        for m in own:
            home=m.get("home_player_id")==pid
            team_raw=m.get("home_team") if home else m.get("away_team")
            team=" ".join(str(team_raw or "").strip().split())
            opp=m.get("away_player_id") if home else m.get("home_player_id"); opp_name=m.get("away_name") if home else m.get("home_name")
            hs,ass=int(m["home_score"]),int(m["away_score"]); gf,ga=(hs,ass) if home else (ass,hs)
            result=self._result_for_player(m,pid)
            if team:
                nt=self._norm_team_name(team); tr=teams[nt];tr["display"]=tr["display"] or team;tr["matches"]+=1;tr["gf"]+=gf;tr["ga"]+=ga;tr[{"W":"w","D":"d","L":"l"}[result]]+=1
            if opp:
                orc=opponents[opp];orc["name"]=opp_name or "?";orc["meetings"]+=1;orc["gf"]+=gf;orc["ga"]+=ga;orc[{"W":"w","D":"d","L":"l"}[result]]+=1
            score=f"{m['home_score']}:{m['away_score']}"
            if m.get("home_penalties") is not None and m.get("away_penalties") is not None:
                score+=f" (k. {m['home_penalties']}:{m['away_penalties']})"
            history.append({"result":result,"played_at":m.get("played_at") or m.get("completed_at") or m.get("created_at"),"stage":m.get("stage"),
                            "opponent":opp_name or "?","team":team or "—","opponent_team":m.get("away_team") if home else m.get("home_team"),"score":score})
        team_rows=[]
        for v in teams.values():
            team_rows.append({"team":v["display"],"matches":v["matches"],"w":v["w"],"d":v["d"],"l":v["l"],"gf":v["gf"],"ga":v["ga"],"gd":v["gf"]-v["ga"],"win_pct":round(v["w"]/v["matches"]*100,1)})
        team_rows.sort(key=lambda x:(x["matches"],x["w"],x["win_pct"]),reverse=True)
        opp_rows=[{"player_id":opid,**v} for opid,v in opponents.items()]
        frequent=max(opp_rows,key=lambda x:(x["meetings"],x["w"]+x["l"]),default=None)
        nemesis=max((x for x in opp_rows if x["l"]>0),key=lambda x:(x["l"]-x["w"],x["l"],x["meetings"]),default=None)
        favorite=max((x for x in opp_rows if x["w"]>0),key=lambda x:(x["w"]-x["l"],x["w"],x["meetings"]),default=None)
        last_results=[self._result_for_player(m,pid) for m in own[-5:]]
        return {**base,"form":last_results,"teams":team_rows,"most_frequent":frequent,"nemesis":nemesis,"favorite":favorite,"history":history[-10:][::-1]}

    def all_time_stats(self) -> list[dict]:
        # Intentionally the same source tables as the classic app: stats are shared across both links.
        with self.connect() as conn:
            trs=self._fetchall(conn,"SELECT id,champion_player_id FROM tournaments WHERE status='completed' AND is_test=0")
            if not trs: return []
            tids={r["id"] for r in trs}; players={r["id"]:r["name"] for r in self._fetchall(conn,"SELECT id,name FROM players")}
            tps=self._fetchall(conn,"SELECT tournament_id,player_id FROM tournament_players")
            matches=self._fetchall(conn,"SELECT * FROM matches WHERE home_score IS NOT NULL ORDER BY tournament_id,match_no")
        finals=[m for m in matches if m["stage"]=="FINAL" and m["tournament_id"] in tids]
        stats=defaultdict(lambda:{"tournaments":0,"titles":0,"finals":0,"w":0,"d":0,"l":0,"gf":0,"ga":0,"pen_wins":0})
        for tp in tps:
            if tp["tournament_id"] in tids: stats[tp["player_id"]]["tournaments"]+=1
        for t in trs:
            if t["champion_player_id"]: stats[t["champion_player_id"]]["titles"]+=1
        for m in finals:
            if m.get("home_player_id"): stats[m["home_player_id"]]["finals"]+=1
            if m.get("away_player_id"): stats[m["away_player_id"]]["finals"]+=1
        for m in matches:
            if m["tournament_id"] not in tids: continue
            h,a=m["home_player_id"],m["away_player_id"]; hs,ass=int(m["home_score"]),int(m["away_score"])
            if not h or not a: continue
            stats[h]["gf"]+=hs; stats[h]["ga"]+=ass; stats[a]["gf"]+=ass; stats[a]["ga"]+=hs
            if hs>ass: stats[h]["w"]+=1; stats[a]["l"]+=1
            elif ass>hs: stats[a]["w"]+=1; stats[h]["l"]+=1
            else:
                stats[h]["d"]+=1; stats[a]["d"]+=1
                if m.get("winner_player_id"): stats[m["winner_player_id"]]["pen_wins"]+=1
        out=[]
        for pid,v in stats.items():
            if not v["tournaments"]: continue
            played=v["w"]+v["d"]+v["l"]
            out.append({"player_id":pid,"name":players.get(pid,"?"),**v,"gd":v["gf"]-v["ga"],"matches":played,"win_pct":round(v["w"]/played*100,1) if played else 0.0})
        out.sort(key=lambda x:(x["titles"],x["w"],x["gd"],x["gf"]),reverse=True); return out

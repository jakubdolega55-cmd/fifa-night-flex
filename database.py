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
    BASE_TEAMS, SEVEN_TEAMS, build_draw, draw_signature, group_members, group_table,
    schedule_for_format, shuffled_assignments, winner_from_result,
)

DB_API_VERSION = 140
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
        ]
        with self.connect() as conn:
            for s in stmts: conn.execute(s)

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

    def _get_or_create_player_conn(self, conn, name: str) -> str:
        clean = " ".join(name.strip().split()); norm = clean.casefold()
        r = self._fetchone(conn, "SELECT id FROM players WHERE normalized_name = ?", (norm,))
        if r: return r["id"]
        pid = str(uuid.uuid4())
        conn.execute(self._sql("INSERT INTO players (id,name,normalized_name,created_at) VALUES (?,?,?,?)"), (pid, clean, norm, now_iso()))
        return pid

    def _extra_for_format(self, format_key: str, rng: random.Random) -> dict:
        if format_key == "double5":
            return {"d5_opponent_match": None, "d5_draw_ack": False}
        if format_key == "double7":
            return {"d7_lb_bye_match": None, "d7_lb_draw_ack": False, "d7_pairing": None}
        if format_key in ("groups6", "groups6_full", "groups7", "groups7_sf"):
            return {"playoff_reveal_ack": False, "playoff_order": None}
        return {}

    def create_tournament(self, player_names: list[str], player_count: int, format_key: str, teams: list[str], is_test: bool) -> str:
        if player_count not in (4,5,6,7): raise ValueError("Obsługiwane są turnieje 4–7 osobowe.")
        if len(player_names) != player_count: raise ValueError(f"Turniej wymaga dokładnie {player_count} graczy.")
        clean = [" ".join(x.strip().split()) for x in player_names]
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

        tid = str(uuid.uuid4()); rng = random.SystemRandom()
        with self.connect() as conn:
            pids = [self._get_or_create_player_conn(conn, n) for n in clean]
            draft_mode = player_count in (4,5)
            assignments = {} if draft_mode else shuffled_assignments(pids, teams, rng)
            reveal = pids.copy(); rng.shuffle(reveal); reveal_idx = {p:i+1 for i,p in enumerate(reveal)}
            draw = build_draw(pids, format_key, rng); extra = self._extra_for_format(format_key, rng)
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
                team=" ".join(str(wildcard_name or "").strip().split())
                if not team: raise ValueError("Wpisz drużynę dla Wild Card.")
                norm=self._norm_team_name(team)
                banned={"real","real madrid","real madryt","rma"}
                if norm in banned or "real madrid" in norm or "real madryt" in norm: raise ValueError("Real Madryt jest banned 🚫")
                if norm in fixed_norm: raise ValueError("Ta drużyna jest już osobnym wyborem w puli.")
                if norm in picked_norm: raise ValueError("Ta drużyna została już wybrana.")
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
            row = self._fetchone(conn, """SELECT tp.player_id,tp.team,p.name FROM tournament_players tp JOIN players p ON p.id=tp.player_id WHERE tp.tournament_id=? AND tp.team_revealed=0 ORDER BY tp.team_reveal_order LIMIT 1""", (tid,))
            if not row: return None
            conn.execute(self._sql("UPDATE tournament_players SET team_revealed=1 WHERE tournament_id=? AND player_id=?"), (tid,row["player_id"]))
            return {"player_id":row["player_id"],"name":row["name"],"team":row["team"]}

    def start_structure_draw(self, tid: str) -> None:
        with self.connect() as conn:
            left = self._fetchone(conn, "SELECT COUNT(*) AS c FROM tournament_players WHERE tournament_id=? AND team_revealed=0", (tid,))
            if left and int(left["c"]) > 0: raise ValueError("Najpierw zakończ losowanie drużyn.")
            conn.execute(self._sql("UPDATE tournaments SET phase='structure_draw' WHERE id=?"), (tid,))

    def _apply_draw_groups_conn(self, conn, tid: str, format_key: str, draw: dict) -> None:
        # Reset group metadata first.
        conn.execute(self._sql("UPDATE tournament_players SET group_name='', tie_order=team_reveal_order WHERE tournament_id=?"), (tid,))
        if format_key in ("groups6", "groups6_full", "groups7", "groups7_sf"):
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
            pids = [r["player_id"] for r in self._fetchall(conn, "SELECT player_id FROM tournament_players WHERE tournament_id=? ORDER BY team_reveal_order", (tid,))]
            old = json.loads(meta["draw_json"]); new = old
            for _ in range(50):
                cand = build_draw(pids, meta["format_key"], rng)
                if draw_signature(cand) != draw_signature(old): new = cand; break
            extra = self._extra_for_format(meta["format_key"], rng)
            conn.execute(self._sql("UPDATE flex_tournament_meta SET draw_json=?,extra_json=?,draw_revealed=1,redraw_count=redraw_count+1 WHERE tournament_id=?"), (json.dumps(new),json.dumps(extra),tid))
            self._apply_draw_groups_conn(conn, tid, meta["format_key"], new)

    def confirm_structure(self, tid: str) -> None:
        rng = random.SystemRandom()
        with self.connect() as conn:
            meta = self._fetchone(conn, "SELECT * FROM flex_tournament_meta WHERE tournament_id=?", (tid,))
            if not int(meta["draw_revealed"]): raise ValueError("Najpierw wykonaj losowanie.")
            draw = json.loads(meta["draw_json"]); extra = json.loads(meta["extra_json"])
            plan = schedule_for_format(draw, meta["format_key"], extra, rng)
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
        if kind in ("G6","G6F","G7","G7S"):
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
                    if format_key not in ("double5", "double7"):
                        continue
                    first_no = 8 if format_key == "double5" else 12
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
                extra["d7_lb_bye_match"]=rng.choice([1,2,3]); extra["d7_lb_draw_ack"]=False; extra["d7_pairing"]=None
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
        if fmt not in ("groups6","groups6_full","groups7","groups7_sf"): return None
        if extra.get("playoff_sources"): return extra
        rows=self._fetchall(conn,"SELECT * FROM matches WHERE tournament_id=? ORDER BY match_no",(tid,)); mm={int(m["match_no"]):m for m in rows}
        group_end=6 if fmt in ("groups6","groups6_full") else 9
        if not all(self._match_played(mm.get(i)) for i in range(1,group_end+1)): return None
        ta=self._table_from_conn(conn,tid,"A"); tb=self._table_from_conn(conn,tid,"B")

        def last_play(pid):
            nums=[i for i in range(1,group_end+1) if pid in (mm[i].get("home_player_id"),mm[i].get("away_player_id"))]
            return max(nums) if nums else 0

        last_group={mm[group_end].get("home_player_id"),mm[group_end].get("away_player_id")}
        orders=[[0,1],[1,0]]

        if fmt in ("groups6","groups7_sf"):
            pairings=[("POS:A:1","POS:B:2"),("POS:B:1","POS:A:2")]
            ids=[(ta[0]["player_id"],tb[1]["player_id"]),(tb[0]["player_id"],ta[1]["player_id"])]
            start_no=7 if fmt=="groups6" else 10

            def cost(order):
                waits=[]
                for slot,i in enumerate(order):
                    mno=start_no+slot
                    waits += [mno-last_play(pid)-1 for pid in ids[i]]
                b2b=sum(pid in last_group for pid in ids[order[0]])
                return (max(waits),b2b,sum(waits))

            order=min(orders,key=cost); p1,p2=[pairings[i] for i in order]
            if fmt=="groups6":
                src={"G6:SF7H":p1[0],"G6:SF7A":p1[1],"G6:SF8H":p2[0],"G6:SF8A":p2[1]}
            else:
                src={"G7S:SF10H":p1[0],"G7S:SF10A":p1[1],"G7S:SF11H":p2[0],"G7S:SF11A":p2[1]}
            display=[p1,p2]
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
            start=7 if fmt in ("groups6","groups6_full") else 10
            pairs=[]
            for no in range(start,start+2):
                m=mm[no]
                if m.get("home_player_id") and m.get("away_player_id"):
                    pairs.append({"match_no":no,"stage":m["stage"],"home_name":m.get("home_name"),"away_name":m.get("away_name")})
            tables={"A":self._table_from_conn(conn,tid,"A"),"B":self._table_from_conn(conn,tid,"B")}
            direct=[]
            if fmt in ("groups6_full","groups7"):
                direct=[{"group":"A","name":tables["A"][0]["name"]},{"group":"B","name":tables["B"][0]["name"]}]
            return {"format_key":fmt,"pairs":pairs,"direct":direct}

    def ack_group_playoffs(self, tid: str) -> None:
        with self.connect() as conn:
            meta,extra=self._meta_extra_conn(conn,tid); extra=self._prepare_group_playoffs_conn(conn,tid) or extra
            extra["playoff_reveal_ack"]=True
            conn.execute(self._sql("UPDATE flex_tournament_meta SET extra_json=? WHERE tournament_id=?"),(json.dumps(extra),tid))
            self._resolve_all_conn(conn,tid,meta["format_key"])

    def current_match_from(self, matches: list[dict]) -> dict | None:
        for m in matches:
            if m.get("home_player_id") and m.get("away_player_id") and m.get("home_score") is None: return m
        return None

    def save_result(self, tid: str, match_no: int, hs: int, ass: int, hp: int | None = None, ap: int | None = None) -> None:
        with self.connect() as conn:
            m=self._fetchone(conn,"SELECT * FROM matches WHERE tournament_id=? AND match_no=?",(tid,match_no))
            if not m or not m.get("home_player_id") or not m.get("away_player_id"): raise ValueError("Ten mecz nie ma jeszcze ustalonych graczy.")
            if hs<0 or ass<0: raise ValueError("Wynik nie może być ujemny.")
            knockout = m["stage"] not in ("GROUP","LEAGUE")
            if knockout and hs==ass and (hp is None or ap is None or hp==ap): raise ValueError("W fazie pucharowej remis wymaga karnych.")
            winner=winner_from_result(hs,ass,m["home_player_id"],m["away_player_id"],hp,ap)
            conn.execute(self._sql("UPDATE matches SET home_score=?,away_score=?,home_penalties=?,away_penalties=?,winner_player_id=?,played_at=? WHERE tournament_id=? AND match_no=?"),(hs,ass,hp,ap,winner,now_iso(),tid,match_no))
            meta=self._fetchone(conn,"SELECT format_key FROM flex_tournament_meta WHERE tournament_id=?",(tid,)); fmt=meta["format_key"]
            if fmt=="double7": self._prepare_double7_pairing_conn(conn,tid)
            if fmt in ("groups6","groups6_full","groups7","groups7_sf"): self._prepare_group_playoffs_conn(conn,tid)
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
        elif fmt=="double5":
            final=mm[8]
            if final.get("winner_player_id"):
                if final["winner_player_id"]==final["home_player_id"]: champion=final["winner_player_id"]
                elif mm[9].get("winner_player_id"): champion=mm[9]["winner_player_id"]
        elif fmt=="double7":
            final=mm[12]
            if final.get("winner_player_id"):
                if final["winner_player_id"]==final["home_player_id"]: champion=final["winner_player_id"]
                elif mm[13].get("winner_player_id"): champion=mm[13]["winner_player_id"]
        if champion:
            conn.execute(self._sql("UPDATE tournaments SET status='completed',phase='completed',champion_player_id=?,completed_at=? WHERE id=?"),(champion,now_iso(),tid))

    def undo_last_result(self, tid: str) -> int | None:
        # Safe approach: clear the latest played result and every later dynamic result/participant,
        # then resolve the bracket again from the remaining valid history.
        with self.connect() as conn:
            last=self._fetchone(conn,"SELECT * FROM matches WHERE tournament_id=? AND home_score IS NOT NULL ORDER BY match_no DESC LIMIT 1",(tid,))
            if not last: return None
            no=int(last["match_no"])
            conn.execute(self._sql("UPDATE matches SET home_score=NULL,away_score=NULL,home_penalties=NULL,away_penalties=NULL,winner_player_id=NULL,played_at=NULL WHERE tournament_id=? AND match_no=?"),(tid,no))
            # Clear all later matches completely; their participants can depend on the undone result.
            conn.execute(self._sql("UPDATE matches SET home_player_id=NULL,away_player_id=NULL,home_score=NULL,away_score=NULL,home_penalties=NULL,away_penalties=NULL,winner_player_id=NULL,played_at=NULL WHERE tournament_id=? AND match_no>?"),(tid,no))
            conn.execute(self._sql("UPDATE tournaments SET status='active',phase='active',champion_player_id=NULL,completed_at=NULL WHERE id=?"),(tid,))
            meta,extra=self._meta_extra_conn(conn,tid); fmt=meta["format_key"]
            if fmt=="double5" and no<=2:
                extra["d5_opponent_match"]=None; extra["d5_draw_ack"]=False
            if fmt=="double7":
                if no<=3:
                    extra["d7_lb_bye_match"]=None; extra["d7_lb_draw_ack"]=False; extra["d7_pairing"]=None
                elif no<=6:
                    extra["d7_pairing"]=None
            group_end=6 if fmt in ("groups6","groups6_full") else (9 if fmt in ("groups7","groups7_sf") else 0)
            if group_end and no<=group_end:
                extra.pop("playoff_sources",None); extra.pop("playoff_display_sources",None); extra["playoff_reveal_ack"]=False
            conn.execute(self._sql("UPDATE flex_tournament_meta SET extra_json=? WHERE tournament_id=?"),(json.dumps(extra),tid))
            if fmt=="double7": self._prepare_double7_pairing_conn(conn,tid)
            if fmt in ("groups6","groups6_full","groups7","groups7_sf"): self._prepare_group_playoffs_conn(conn,tid)
            self._resolve_all_conn(conn,tid,fmt)
            return no

    def standings(self, tid: str) -> dict[str,list[dict]]:
        with self.connect() as conn:
            meta=self._fetchone(conn,"SELECT format_key FROM flex_tournament_meta WHERE tournament_id=?",(tid,)); fmt=meta["format_key"]
            if fmt in ("league4_final", "league5_final"): return {"L":self._table_from_conn(conn,tid,"L")}
            if fmt in ("groups6", "groups6_full", "groups7", "groups7_sf"): return {"A":self._table_from_conn(conn,tid,"A"),"B":self._table_from_conn(conn,tid,"B")}
            return {}

    def reset_current(self, tid: str) -> None:
        with self.connect() as conn:
            conn.execute(self._sql("DELETE FROM flex_match_sources WHERE tournament_id=?"),(tid,)); conn.execute(self._sql("DELETE FROM matches WHERE tournament_id=?"),(tid,)); conn.execute(self._sql("DELETE FROM tournament_players WHERE tournament_id=?"),(tid,)); conn.execute(self._sql("DELETE FROM flex_tournament_meta WHERE tournament_id=?"),(tid,)); conn.execute(self._sql("DELETE FROM tournaments WHERE id=?"),(tid,)); self._setting_set_conn(conn,CURRENT_KEY,"")

    def start_new(self) -> None:
        with self.connect() as conn: self._setting_set_conn(conn,CURRENT_KEY,"")

    def clear_flex_history(self) -> None:
        with self.connect() as conn:
            ids=[r["tournament_id"] for r in self._fetchall(conn,"SELECT tournament_id FROM flex_tournament_meta")]
            for tid in ids:
                conn.execute(self._sql("DELETE FROM flex_match_sources WHERE tournament_id=?"),(tid,)); conn.execute(self._sql("DELETE FROM matches WHERE tournament_id=?"),(tid,)); conn.execute(self._sql("DELETE FROM tournament_players WHERE tournament_id=?"),(tid,)); conn.execute(self._sql("DELETE FROM tournaments WHERE id=?"),(tid,))
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
            conn.execute("DELETE FROM flex_tournament_meta")
            conn.execute("DELETE FROM matches")
            conn.execute("DELETE FROM tournament_players")
            conn.execute("DELETE FROM tournaments")
            # Keep players and remembered lineups. Only live tournament pointers are cleared.
            self._setting_set_conn(conn,CURRENT_KEY,"")

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

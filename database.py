from __future__ import annotations

from collections import defaultdict
from contextlib import contextmanager
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
import json
import os
from pathlib import Path
import random
import sqlite3
import uuid

import psycopg
from psycopg.rows import dict_row
try:
    from psycopg_pool import ConnectionPool
except ImportError:  # Safe fallback if an old Streamlit build has not installed the pool extra yet.
    ConnectionPool = None
import streamlit as st

from logic import (
    BASE_TEAMS, SIX_TEAMS, SEVEN_TEAMS, EIGHT_TEAMS, FIXED_TEAMS, WILDCARD_TEAM_SUGGESTIONS, build_draw, draw_signature, group_members, group_table,
    schedule_for_format, shuffled_assignments, weighted_team_assignments, weighted_draft_order, reveal_order_with_previous_finalists, winner_from_result, optimize_opening_order, apply_cross_tournament_bye_priority, weighted_bye_choice,
)
from scorer_seeds import SCORER_SEEDS

DB_API_VERSION = 1802
APP_KEY = "flex"
CURRENT_KEY = "flex_current_tournament"
LAST_COUNT_KEY = "flex_last_player_count"
LAST_STAKE_KEY = "flex_last_stake_pln"


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


@st.cache_resource(show_spinner=False)
def _postgres_pool(url: str):
    """Keep warm Neon connections between Streamlit reruns.

    The setup/draw screens make several short DB calls. Reusing connections removes
    most of the TLS/connection handshake delay without caching live tournament data.
    """
    if ConnectionPool is None:
        return None
    pool = ConnectionPool(
        conninfo=url,
        min_size=1,
        max_size=4,
        max_idle=300,
        max_lifetime=1800,
        kwargs={
            "row_factory": dict_row,
            "autocommit": False,
            "prepare_threshold": None,
        },
        # Neon/Streamlit may leave an idle TCP socket in the pool after the
        # database or app has slept. Validate a connection on checkout so a
        # stale socket is discarded and replaced before application code sees it.
        check=ConnectionPool.check_connection,
        open=True,
    )
    return pool


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
            # Pool is cached by Streamlit, so ordinary reruns reuse an already-open
            # Neon connection instead of paying for a new handshake every click.
            pool = _postgres_pool(self.url)
            if pool is not None:
                # pool.connection() already applies the normal psycopg
                # transaction behaviour: commit on success, rollback on error,
                # and replacement of broken connections. Do not rollback a
                # broken socket manually: doing so can mask the original error.
                with pool.connection() as conn:
                    yield conn
                return
            # Compatibility fallback: app still works if the pool dependency was not
            # installed yet; it simply uses the old per-call connection behaviour.
            conn = psycopg.connect(self.url, row_factory=dict_row, autocommit=False, prepare_threshold=None)
            try:
                yield conn; conn.commit()
            except Exception:
                conn.rollback(); raise
            finally:
                conn.close()
            return

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
            """CREATE TABLE IF NOT EXISTS match_events (
                id TEXT PRIMARY KEY, tournament_id TEXT NOT NULL, match_no INTEGER NOT NULL,
                event_order INTEGER NOT NULL, event_type TEXT NOT NULL,
                minute INTEGER, stoppage INTEGER, minute_label TEXT,
                actor_player_id TEXT, credited_player_id TEXT,
                actor_team_name TEXT, credited_team_name TEXT,
                footballer_name TEXT, normalized_footballer TEXT, related_footballer_name TEXT,
                synthetic_de INTEGER NOT NULL DEFAULT 0, confidence TEXT, source_images_json TEXT NOT NULL DEFAULT '[]',
                created_at TEXT NOT NULL)""",
            """CREATE TABLE IF NOT EXISTS tournament_absences (
                id TEXT PRIMARY KEY, tournament_id TEXT NOT NULL, player_id TEXT NOT NULL,
                footballer_name TEXT NOT NULL, normalized_footballer TEXT NOT NULL, reason TEXT NOT NULL,
                source_match_no INTEGER NOT NULL, served_match_no INTEGER,
                created_at TEXT NOT NULL, served_at TEXT,
                UNIQUE (tournament_id, player_id, normalized_footballer, reason, source_match_no))""",
        ]
        with self.connect() as conn:
            for s in stmts: conn.execute(s)
            self._ensure_match_status_column_conn(conn)
            self._seed_scorers_conn(conn)
            self._migrate_double_elim_single_final_conn(conn)

    def _ensure_match_status_column_conn(self, conn) -> None:
        """Add a lightweight terminal status for skipped matches without breaking old databases."""
        if self.is_postgres:
            exists=self._fetchone(conn,
                "SELECT 1 AS ok FROM information_schema.columns WHERE table_name='matches' AND column_name='match_status' LIMIT 1")
            if not exists:
                conn.execute("ALTER TABLE matches ADD COLUMN match_status TEXT NOT NULL DEFAULT 'pending'")
        else:
            cols=[dict(r) for r in conn.execute("PRAGMA table_info(matches)").fetchall()]
            if not any(str(c.get("name"))=="match_status" for c in cols):
                conn.execute("ALTER TABLE matches ADD COLUMN match_status TEXT NOT NULL DEFAULT 'pending'")
        # Backfill old played rows. Pending rows remain pending.
        conn.execute(self._sql("UPDATE matches SET match_status='played' WHERE home_score IS NOT NULL AND COALESCE(match_status,'pending')<>'played'"))

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
            conn.execute(self._sql("DELETE FROM tournament_absences WHERE tournament_id=? AND source_match_no=?"),(tid,reset_no))
            conn.execute(self._sql("UPDATE tournament_absences SET served_match_no=NULL,served_at=NULL WHERE tournament_id=? AND served_match_no=?"),(tid,reset_no))
            conn.execute(self._sql("DELETE FROM match_events WHERE tournament_id=? AND match_no=?"),(tid,reset_no))
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
        fixed={self._norm_team_name(x) for x in BASE_TEAMS+SIX_TEAMS+SEVEN_TEAMS+EIGHT_TEAMS if "Dowolna drużyna" not in x}
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

    @staticmethod
    def _stake_cents(value) -> int:
        try:
            dec = Decimal(str(value or 0)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        except Exception:
            raise ValueError("Nieprawidłowa stawka.")
        if dec < 0:
            raise ValueError("Stawka nie może być ujemna.")
        if dec > Decimal("100000"):
            raise ValueError("Stawka jest zbyt wysoka.")
        return int(dec * 100)

    def last_stake(self) -> float:
        with self.connect() as conn:
            raw = self._setting_get_conn(conn, LAST_STAKE_KEY)
            try:
                return self._stake_cents(raw) / 100 if raw is not None else 0.0
            except ValueError:
                return 0.0

    def set_tournament_finance(self, tid: str, stake_per_player: float, settled: bool | None = None) -> None:
        """Update the stake and, optionally, the cash-settlement status of a completed official Flex tournament."""
        cents = self._stake_cents(stake_per_player)
        with self.connect() as conn:
            t = self._fetchone(conn, "SELECT status,is_test FROM tournaments WHERE id=?", (tid,))
            if not t or t.get("status") != "completed" or int(t.get("is_test") or 0) != 0:
                raise ValueError("Rozliczenia można edytować tylko dla zakończonych oficjalnych turniejów.")
            meta, extra = self._meta_extra_conn(conn, tid)
            extra["stake_per_player"] = cents / 100
            if settled is not None:
                extra["cash_settled"] = bool(settled)
                if settled:
                    extra["cash_settled_at"] = now_iso()
                else:
                    extra.pop("cash_settled_at", None)
            conn.execute(self._sql("UPDATE flex_tournament_meta SET extra_json=? WHERE tournament_id=?"), (json.dumps(extra, ensure_ascii=False), tid))

    def set_tournament_stake(self, tid: str, stake_per_player: float) -> None:
        self.set_tournament_finance(tid, stake_per_player, None)

    def set_tournament_settled(self, tid: str, settled: bool) -> None:
        with self.connect() as conn:
            t = self._fetchone(conn, "SELECT status,is_test FROM tournaments WHERE id=?", (tid,))
            if not t or t.get("status") != "completed" or int(t.get("is_test") or 0) != 0:
                raise ValueError("Rozliczenia można zmieniać tylko dla zakończonych oficjalnych turniejów.")
            meta, extra = self._meta_extra_conn(conn, tid)
            extra["cash_settled"] = bool(settled)
            if settled:
                extra["cash_settled_at"] = now_iso()
            else:
                extra.pop("cash_settled_at", None)
            conn.execute(self._sql("UPDATE flex_tournament_meta SET extra_json=? WHERE tournament_id=?"), (json.dumps(extra, ensure_ascii=False), tid))

    def set_tournaments_settled(self, tournament_ids: list[str], settled: bool) -> int:
        tids = list(dict.fromkeys(str(x) for x in (tournament_ids or []) if x))
        if not tids:
            return 0
        changed = 0
        with self.connect() as conn:
            for tid in tids:
                t = self._fetchone(conn, "SELECT status,is_test FROM tournaments WHERE id=?", (tid,))
                if not t or t.get("status") != "completed" or int(t.get("is_test") or 0) != 0:
                    continue
                meta, extra = self._meta_extra_conn(conn, tid)
                extra["cash_settled"] = bool(settled)
                if settled:
                    extra["cash_settled_at"] = now_iso()
                else:
                    extra.pop("cash_settled_at", None)
                conn.execute(self._sql("UPDATE flex_tournament_meta SET extra_json=? WHERE tournament_id=?"), (json.dumps(extra, ensure_ascii=False), tid))
                changed += 1
        return changed

    def official_player_names(self) -> list[str]:
        """Nicki graczy z co najmniej jednej zamkniętej oficjalnej rozgrywki.

        Obejmuje także rozegrane części oficjalnych turniejów zamkniętych jako
        niedokończone; testy pozostają wykluczone.
        """
        with self.connect() as conn:
            rows = self._fetchall(conn, """
                SELECT DISTINCT p.name
                FROM players p
                JOIN tournament_players tp ON tp.player_id = p.id
                JOIN tournaments t ON t.id = tp.tournament_id
                WHERE t.status IN ('completed','abandoned') AND t.is_test=0
                ORDER BY p.name
            """)
            return [str(r["name"]) for r in rows if r.get("name")]

    def admin_players(self) -> list[dict]:
        """All known player identities for password-protected administrative edits."""
        with self.connect() as conn:
            return self._fetchall(conn, "SELECT id,name,created_at FROM players ORDER BY name")

    def rename_player(self, player_id: str, new_name: str) -> dict:
        """Rename one player identity everywhere, including historical views.

        Matches/tournaments store player IDs, so changing the canonical row updates the
        whole statistical history automatically. We additionally refresh convenience
        snapshots kept in JSON settings/meta so old nick text does not survive in the UI.
        This is a rename only: merging two existing player identities is deliberately
        rejected because it would change historical ownership of results.
        """
        pid=str(player_id or "").strip()
        clean=" ".join(str(new_name or "").strip().split())
        if not pid: raise ValueError("Wybierz gracza.")
        if not clean: raise ValueError("Nowa nazwa nie może być pusta.")
        if len(clean)>60: raise ValueError("Nazwa gracza jest zbyt długa.")
        norm=clean.casefold()
        with self.connect() as conn:
            current=self._fetchone(conn,"SELECT id,name,normalized_name FROM players WHERE id=?",(pid,))
            if not current: raise ValueError("Nie znaleziono gracza.")
            old_name=str(current.get("name") or "")
            collision=self._fetchone(conn,"SELECT id,name FROM players WHERE normalized_name=? AND id<>?",(norm,pid))
            if collision:
                raise ValueError(f"Gracz o nazwie „{collision.get('name')}” już istnieje. Zmiana nazwy nie łączy dwóch profili.")
            if old_name==clean:
                return {"id":pid,"old_name":old_name,"new_name":clean,"changed":False}

            conn.execute(self._sql("UPDATE players SET name=?, normalized_name=? WHERE id=?"),(clean,norm,pid))

            # Historical cash-name snapshots. IDs remain the source of truth.
            metas=self._fetchall(conn,"SELECT tournament_id,extra_json FROM flex_tournament_meta")
            for row in metas:
                try: extra=json.loads(row.get("extra_json") or "{}")
                except Exception: continue
                ids=[str(x) for x in (extra.get("cash_player_ids") or [])]
                names=list(extra.get("cash_player_names") or [])
                changed=False
                for i,x in enumerate(ids):
                    if x==pid and i<len(names) and names[i]!=clean:
                        names[i]=clean; changed=True
                if changed:
                    extra["cash_player_names"]=names
                    conn.execute(self._sql("UPDATE flex_tournament_meta SET extra_json=? WHERE tournament_id=?"),(json.dumps(extra,ensure_ascii=False),row["tournament_id"]))

            # Remembered line-ups are text snapshots used only as start-screen defaults.
            settings=self._fetchall(conn,"SELECT key,value FROM app_settings WHERE key LIKE ?",("flex_last_lineup_%",))
            for row in settings:
                try: values=json.loads(row.get("value") or "[]")
                except Exception: continue
                if not isinstance(values,list): continue
                replaced=[clean if str(v).strip().casefold()==old_name.strip().casefold() else v for v in values]
                if replaced!=values:
                    self._setting_set_conn(conn,row["key"],json.dumps(replaced,ensure_ascii=False))

            # Organizer-selected award names are stored as display snapshots. Refresh the
            # categories where a participant name is embedded in that snapshot.
            award_rows=self._fetchall(conn,"SELECT key,value FROM app_settings WHERE key LIKE ?",("flex_award_selections_%",))
            direct_keys={"player_year","offensive","defense","clutch","penalties","wildcards","progress","regular","debut","outsider","universal","finance","duel"}
            for row in award_rows:
                try: data=json.loads(row.get("value") or "{}")
                except Exception: continue
                if not isinstance(data,dict): continue
                dirty=False
                for cat_key,sel in data.items():
                    if not isinstance(sel,dict): continue
                    sid=str(sel.get("id") or "")
                    if cat_key in direct_keys and sid==pid:
                        if sel.get("name")!=clean: sel["name"]=clean; dirty=True
                    elif cat_key=="player_scorers" and sid.startswith(pid+"|"):
                        scorer=str(sel.get("name") or "").split(" — ",1)[0].strip()
                        new_display=f"{scorer} — {clean}" if scorer else clean
                        if sel.get("name")!=new_display: sel["name"]=new_display; dirty=True
                    elif cat_key=="rivalry" and pid in sid.split("|"):
                        pair_ids=sid.split("|")
                        if len(pair_ids)==2:
                            names2=[]
                            for pair_pid in pair_ids:
                                pr=self._fetchone(conn,"SELECT name FROM players WHERE id=?",(pair_pid,))
                                names2.append(str((pr or {}).get("name") or "?"))
                            new_display=f"{names2[0]} vs {names2[1]}"
                            if sel.get("name")!=new_display: sel["name"]=new_display; dirty=True
                    elif cat_key=="match_year" and ":" in sid:
                        tid,no=sid.rsplit(":",1)
                        try: no_i=int(no)
                        except Exception: no_i=None
                        if no_i is not None:
                            m=self._fetchone(conn,"""SELECT m.home_score,m.away_score,hp.name home_name,ap.name away_name
                                FROM matches m LEFT JOIN players hp ON hp.id=m.home_player_id LEFT JOIN players ap ON ap.id=m.away_player_id
                                WHERE m.tournament_id=? AND m.match_no=?""",(tid,no_i))
                            if m:
                                new_display=f"{m.get('home_name')} {m.get('home_score')}:{m.get('away_score')} {m.get('away_name')}"
                                if sel.get("name")!=new_display: sel["name"]=new_display; dirty=True
                if dirty:
                    self._setting_set_conn(conn,row["key"],json.dumps(data,ensure_ascii=False))

            # Historical scorer selections for global goal milestones also keep a display snapshot.
            milestone_raw=self._setting_get_conn(conn,"flex_global_goal_milestone_scorers")
            if milestone_raw:
                try: milestone_data=json.loads(milestone_raw)
                except Exception: milestone_data={}
                milestone_dirty=False
                if isinstance(milestone_data,dict):
                    for value in milestone_data.values():
                        if isinstance(value,dict) and str(value.get("player_id") or "")==pid and value.get("player_name")!=clean:
                            value["player_name"]=clean;milestone_dirty=True
                if milestone_dirty:self._setting_set_conn(conn,"flex_global_goal_milestone_scorers",json.dumps(milestone_data,ensure_ascii=False))

        return {"id":pid,"old_name":old_name,"new_name":clean,"changed":True}

    def _get_or_create_player_conn(self, conn, name: str) -> str:
        clean = " ".join(name.strip().split()); norm = clean.casefold()
        r = self._fetchone(conn, "SELECT id FROM players WHERE normalized_name = ?", (norm,))
        if r: return r["id"]
        pid = str(uuid.uuid4())
        conn.execute(self._sql("INSERT INTO players (id,name,normalized_name,created_at) VALUES (?,?,?,?)"), (pid, clean, norm, now_iso()))
        return pid

    def _placement_order_conn(self, conn, tid: str) -> list[str]:
        """Best-effort full final classification for any Flex format.

        Knockout depth decides first; players eliminated in the same round are ordered
        by their whole-tournament record (wins, goal difference, goals scored).
        """
        t=self._fetchone(conn,"SELECT champion_player_id FROM tournaments WHERE id=?",(tid,))
        meta=self._fetchone(conn,"SELECT format_key FROM flex_tournament_meta WHERE tournament_id=?",(tid,))
        if not t or not meta:
            return []
        fmt=str(meta.get("format_key") or "")
        matches=[m for m in self._matches_conn(conn,tid) if m.get("home_score") is not None]
        if not matches:
            return []
        mm={int(m["match_no"]):m for m in matches}
        player_rows=self._fetchall(conn,"SELECT player_id FROM tournament_players WHERE tournament_id=?",(tid,))
        all_pids=[str(r["player_id"]) for r in player_rows]
        stats=defaultdict(lambda:{"w":0,"d":0,"l":0,"gf":0,"ga":0})
        for m in matches:
            h,a=str(m.get("home_player_id") or ""),str(m.get("away_player_id") or "")
            if not h or not a: continue
            hs,ass=int(m.get("home_score") or 0),int(m.get("away_score") or 0)
            stats[h]["gf"]+=hs; stats[h]["ga"]+=ass; stats[a]["gf"]+=ass; stats[a]["ga"]+=hs
            rh=self._result_for_player(m,h)
            if rh=="W": stats[h]["w"]+=1; stats[a]["l"]+=1
            elif rh=="L": stats[a]["w"]+=1; stats[h]["l"]+=1
            else: stats[h]["d"]+=1; stats[a]["d"]+=1
        def loser(no:int):
            m=mm.get(no)
            return str(self._loser_of(m) or "") if m else ""
        def rank_group(pids):
            vals=[str(pid) for pid in pids if pid]
            return sorted(dict.fromkeys(vals),key=lambda pid:(stats[pid]["w"],stats[pid]["gf"]-stats[pid]["ga"],stats[pid]["gf"],-stats[pid]["ga"]),reverse=True)
        champ=str(t.get("champion_player_id") or "")
        finals=[m for m in matches if m.get("stage") in ("FINAL","RESET_FINAL")]
        final=finals[-1] if finals else None
        runner=str(self._loser_of(final) or "") if final else ""
        order=[]
        def add(pid):
            pid=str(pid or "")
            if pid and pid not in order: order.append(pid)
        add(champ); add(runner)

        if fmt in ("league3_final","league4_final","league5_final"):
            table=self._table_from_conn(conn,tid,"L")
            for row in table: add(row.get("player_id"))
        elif fmt=="double4":
            for no in (5,3): add(loser(no))
        elif fmt=="double5":
            for no in (7,6,4): add(loser(no))
        elif fmt=="double6":
            for no in (9,8,6,5): add(loser(no))
        elif fmt=="double7":
            for no in (11,10,8,7,6): add(loser(no))
        elif fmt=="double8":
            add(loser(13)); add(loser(12))
            for pid in rank_group([loser(9),loser(10)]): add(pid)
            for pid in rank_group([loser(7),loser(8)]): add(pid)
        elif fmt in ("groups6","groups6_full","groups7","groups7_sf","groups8_sf","groups8_barrage"):
            sf_losers=[self._loser_of(m) for m in matches if m.get("stage")=="SF"]
            for pid in rank_group(sf_losers): add(pid)
            q_losers=[self._loser_of(m) for m in matches if m.get("stage") in ("QF","BARRAGE")]
            for pid in rank_group(q_losers): add(pid)
            for pid in rank_group([pid for pid in all_pids if pid not in order]): add(pid)
        else:
            for pid in rank_group([pid for pid in all_pids if pid not in order]): add(pid)
        for pid in rank_group([pid for pid in all_pids if pid not in order]): add(pid)
        return order

    def _cross_tournament_priority_conn(self, conn, current_names: list[str], current_pids: list[str], is_test: bool) -> dict:
        """Fairness context from the immediately previous completed tournament.

        Exact-name matches receive their real wait (number of matches played after their
        last appearance). A player absent from the immediately previous tournament is
        treated as a newcomer/returning-after-a-break player and receives the strongest
        opening priority, but only when at least one current player actually played in
        that previous tournament. This keeps an all-new lineup fully random.
        """
        prev=self._fetchone(conn,"""
            SELECT t.id,t.completed_at,t.created_at
            FROM tournaments t JOIN flex_tournament_meta fm ON fm.tournament_id=t.id
            WHERE t.status='completed' AND t.is_test=? AND fm.format_key<>'duel1v1'
            ORDER BY COALESCE(t.completed_at,t.created_at) DESC, t.created_at DESC
            LIMIT 1
        """,(int(is_test),))
        if not prev:
            return {}
        prev_players=self._fetchall(conn,"""
            SELECT tp.player_id,p.name,tp.team
            FROM tournament_players tp JOIN players p ON p.id=tp.player_id
            WHERE tp.tournament_id=?
        """,(prev["id"],))
        placement_order=self._placement_order_conn(conn,prev["id"])
        placement_prev={str(pid):i+1 for i,pid in enumerate(placement_order)}
        exact_prev={str(r.get("name") or ""):str(r.get("player_id") or "") for r in prev_players}
        prev_team_by_pid={str(r.get("player_id") or ""):str(r.get("team") or "") for r in prev_players}
        played=self._fetchall(conn,"""
            SELECT match_no,played_at,home_player_id,away_player_id
            FROM matches
            WHERE tournament_id=? AND home_score IS NOT NULL
            ORDER BY CASE WHEN played_at IS NULL THEN 1 ELSE 0 END, played_at, match_no
        """,(prev["id"],))
        if not played:
            return {}
        last_pos={}
        for pos,m in enumerate(played):
            for pid in (m.get("home_player_id"),m.get("away_player_id")):
                if pid:last_pos[str(pid)]=pos
        wait_by_pid={pid:(len(played)-1-pos) for pid,pos in last_pos.items()}
        max_no=max(int(m["match_no"]) for m in played)

        current_by_name={name:pid for name,pid in zip(current_names,current_pids)}
        matched=[];priority={};placements={};previous_teams={};newcomers=[]
        for name,pid in current_by_name.items():
            prev_pid=exact_prev.get(name)
            if not prev_pid:
                newcomers.append({"name":name,"player_id":pid})
                continue
            wait=int(wait_by_pid.get(prev_pid,0))
            priority[pid]=wait
            if prev_pid in placement_prev: placements[pid]=int(placement_prev[prev_pid])
            if prev_team_by_pid.get(prev_pid): previous_teams[pid]=prev_team_by_pid[prev_pid]
            matched.append({"name":name,"wait_matches":wait,"place":placements.get(pid),"previous_team":previous_teams.get(pid)})

        # If nobody from the previous tournament is here, everybody is equally fresh.
        # Don't manufacture a priority between a completely new lineup.
        if not matched:
            return {}

        # New/returning-after-a-break players waited longer than anyone who just played
        # the previous tournament. The value only ranks opening order; it is not shown.
        newcomer_priority=len(played)+2
        for item in newcomers:
            priority[str(item["player_id"])]=newcomer_priority
            item["wait_matches"]=newcomer_priority
            item["place"]=None

        matched.sort(key=lambda x:(-int(x["wait_matches"]),x["name"]))
        newcomers.sort(key=lambda x:x["name"])
        return {
            "source_tournament_id":prev["id"],
            "exact_name_match":True,
            "priority_by_player_id":priority,
            "placement_by_player_id":placements,
            "previous_team_by_player_id":previous_teams,
            "source_player_count":len(prev_players),
            "matched":matched,
            "newcomers":newcomers,
            "new_player_ids":[str(x["player_id"]) for x in newcomers],
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

    def _live_team_ratings_conn(self, conn) -> dict[str,float]:
        """Shrink noisy team results toward 50 and update automatically with history.

        Result component uses W=1/D=.5/L=0 with eight neutral pseudo-matches. Goal
        difference per match contributes only a small bounded correction, so a short hot
        streak never permanently brands a club as overpowered.
        """
        rows=self._fetchall(conn,"""
            SELECT htp.team AS home_team,atp.team AS away_team,m.home_score,m.away_score
            FROM matches m JOIN tournaments t ON t.id=m.tournament_id
            LEFT JOIN tournament_players htp ON htp.tournament_id=m.tournament_id AND htp.player_id=m.home_player_id
            LEFT JOIN tournament_players atp ON atp.tournament_id=m.tournament_id AND atp.player_id=m.away_player_id
            WHERE t.status IN ('completed','abandoned') AND t.is_test=0 AND m.home_score IS NOT NULL
        """)
        stats=defaultdict(lambda:{"m":0,"points":0.0,"gf":0,"ga":0})
        for r in rows:
            ht=str(r.get("home_team") or "").strip(); at=str(r.get("away_team") or "").strip()
            if not ht or not at: continue
            hs=int(r.get("home_score") or 0); ass=int(r.get("away_score") or 0)
            stats[ht]["m"]+=1;stats[at]["m"]+=1
            stats[ht]["gf"]+=hs;stats[ht]["ga"]+=ass;stats[at]["gf"]+=ass;stats[at]["ga"]+=hs
            if hs>ass: stats[ht]["points"]+=1.0
            elif hs<ass: stats[at]["points"]+=1.0
            else: stats[ht]["points"]+=0.5;stats[at]["points"]+=0.5
        out={}
        for team,v in stats.items():
            m=int(v["m"]); result=(float(v["points"])+4.0)/(m+8.0)
            gdpm=((int(v["gf"])-int(v["ga"]))/m) if m else 0.0
            gdpm=max(-2.0,min(2.0,gdpm))
            rating=50.0+(result-0.5)*60.0+gdpm*5.0
            out[team]=round(max(20.0,min(80.0,rating)),2)
        return out

    def live_team_ratings(self) -> list[dict]:
        with self.connect() as conn:
            ratings=self._live_team_ratings_conn(conn)
            stats=self.team_stats() if False else None
            rows=self._fetchall(conn,"""
                SELECT htp.team AS home_team,atp.team AS away_team,m.home_score,m.away_score
                FROM matches m JOIN tournaments t ON t.id=m.tournament_id
                LEFT JOIN tournament_players htp ON htp.tournament_id=m.tournament_id AND htp.player_id=m.home_player_id
                LEFT JOIN tournament_players atp ON atp.tournament_id=m.tournament_id AND atp.player_id=m.away_player_id
                WHERE t.status IN ('completed','abandoned') AND t.is_test=0 AND m.home_score IS NOT NULL
            """)
        agg=defaultdict(lambda:{"m":0,"w":0,"d":0,"l":0,"gf":0,"ga":0})
        for r in rows:
            ht=str(r.get("home_team") or "").strip();at=str(r.get("away_team") or "").strip()
            if not ht or not at: continue
            hs=int(r.get("home_score") or 0);ass=int(r.get("away_score") or 0)
            for team,gf,ga in ((ht,hs,ass),(at,ass,hs)):
                agg[team]["m"]+=1;agg[team]["gf"]+=gf;agg[team]["ga"]+=ga
            if hs>ass:agg[ht]["w"]+=1;agg[at]["l"]+=1
            elif hs<ass:agg[at]["w"]+=1;agg[ht]["l"]+=1
            else:agg[ht]["d"]+=1;agg[at]["d"]+=1
        out=[]
        for team,v in agg.items():
            out.append({"team":team,"rating":float(ratings.get(team,50.0)),**v,"matches":int(v["m"]),"gd":int(v["gf"])-int(v["ga"]),"win_pct":round(v["w"]/v["m"]*100,1) if v["m"] else 0.0})
        out.sort(key=lambda x:(x["rating"],x["m"]),reverse=True)
        return out

    def create_tournament(self, player_names: list[str], player_count: int, format_key: str, teams: list[str], is_test: bool,
                          stake_per_player: float = 0.0, cash_flags: list[bool] | None = None) -> str:
        if player_count not in (3,4,5,6,7,8): raise ValueError("Obsługiwane są turnieje 3–8 osobowe.")
        if len(player_names) != player_count: raise ValueError(f"Turniej wymaga dokładnie {player_count} graczy.")
        clean = [" ".join(str(x or "").strip().split()) for x in player_names]
        if any(not x for x in clean): raise ValueError("Wpisz nick każdego gracza.")
        if len({x.casefold() for x in clean}) != player_count: raise ValueError("Nicki w jednym turnieju muszą być unikalne.")
        draft_mode = player_count in (3,4)
        if draft_mode:
            if len(teams) < player_count or len(set(teams)) != len(teams): raise ValueError("Pula draftu drużyn jest nieprawidłowa.")
        elif len(teams) != player_count or len(set(teams)) != player_count:
            raise ValueError(f"Turniej wymaga dokładnie {player_count} różnych drużyn/slotów.")
        allowed={
            3:("league3_final",),
            4:("league4_final","double4"),
            5:("double5","league5_final"),
            6:("groups6","groups6_full","double6"),
            7:("double7","groups7","groups7_sf"),
            8:("groups8_sf","double8","groups8_barrage"),
        }
        if format_key not in allowed[player_count]: raise ValueError(f"Nieprawidłowy format dla {player_count} graczy.")

        stake_cents=self._stake_cents(stake_per_player); stake_value=stake_cents/100
        flags=list(cash_flags) if cash_flags is not None else [True]*player_count
        if len(flags)!=player_count: flags=[True]*player_count
        flags=[bool(x) for x in flags]
        if stake_cents>0 and sum(flags)<2:
            raise ValueError("Przy dodatniej stawce co najmniej 2 graczy musi grać za kasę.")

        tid = str(uuid.uuid4()); rng = random.SystemRandom()
        with self.connect() as conn:
            pids = [self._get_or_create_player_conn(conn, n) for n in clean]
            cash_pids=[pid for pid,flag in zip(pids,flags) if flag]
            carry=self._cross_tournament_priority_conn(conn,clean,pids,is_test)
            placements=(carry or {}).get("placement_by_player_id") or {}
            ratings=self._live_team_ratings_conn(conn)
            previous_teams=(carry or {}).get("previous_team_by_player_id") or {}
            assignments = {} if draft_mode else weighted_team_assignments(pids, teams, placements, rng, ratings, previous_teams)
            if draft_mode:
                reveal=weighted_draft_order(pids,placements,(carry or {}).get("source_player_count"),player_count,rng)
            else:
                reveal=reveal_order_with_previous_finalists(pids,placements,rng)
            reveal_idx = {p:i+1 for i,p in enumerate(reveal)}
            draw = build_draw(pids, format_key, rng); extra = self._extra_for_format(format_key, rng)
            extra["stake_per_player"]=stake_value
            extra["cash_player_ids"]=cash_pids
            extra["cash_player_names"]=[name for name,flag in zip(clean,flags) if flag]
            extra["team_rating_snapshot"]={k:float(v) for k,v in ratings.items()}
            if carry:
                draw=apply_cross_tournament_bye_priority(draw,format_key,carry.get("priority_by_player_id") or {},rng,carry.get("new_player_ids") or [])
                extra["cross_tournament_priority"]=carry
            if draft_mode:
                extra.update({"draft_order_revealed":False,"draft_redraw_count":0})
            self._setting_set_conn(conn, CURRENT_KEY, tid)
            self._setting_set_conn(conn, LAST_COUNT_KEY, str(player_count))
            self._setting_set_conn(conn, f"flex_last_lineup_{player_count}", json.dumps(clean, ensure_ascii=False))
            self._setting_set_conn(conn, LAST_STAKE_KEY, f"{stake_value:.2f}")
            initial_phase = "draft_order" if draft_mode else "team_draw"
            conn.execute(self._sql("INSERT INTO tournaments (id,status,phase,is_test,is_current,groups_revealed,created_at) VALUES (?,'active',?, ?,0,0,?)"), (tid, initial_phase, int(is_test), now_iso()))
            for p in pids:
                team = "" if draft_mode else assignments[p]
                conn.execute(self._sql("INSERT INTO tournament_players (tournament_id,player_id,team,team_reveal_order,team_revealed,group_name,tie_order) VALUES (?,?,?,?,0,'',?)"), (tid,p,team,reveal_idx[p],reveal_idx[p]))
            conn.execute(self._sql("INSERT INTO flex_tournament_meta (tournament_id,player_count,format_key,team_pool_json,draw_json,extra_json,draw_revealed,redraw_count) VALUES (?,?,?,?,?,?,0,0)"), (tid,player_count,format_key,json.dumps(teams,ensure_ascii=False),json.dumps(draw),json.dumps(extra,ensure_ascii=False)))
        return tid

    def create_duel(self, player_names: list[str], team_names: list[str], is_test: bool = False, stake_per_player: float = 0.0,
                    cash_flags: list[bool] | None = None) -> str:
        # 1 vs 1 is always an official match. Keep the is_test argument only for
        # backwards compatibility with older callers/API payloads.
        is_test=False
        clean=[" ".join(str(x or "").strip().split()) for x in player_names]
        if len(clean)!=2 or any(not x for x in clean): raise ValueError("Wybierz dwóch graczy.")
        if clean[0].casefold()==clean[1].casefold(): raise ValueError("Wybierz dwóch różnych graczy.")
        teams=[" ".join(str(x or "").strip().split()) for x in team_names]
        if len(teams)!=2 or any(not x for x in teams): raise ValueError("Wybierz drużynę dla obu graczy.")
        norms=[self._norm_team_name(x) for x in teams]
        if any(x in {"real","real madrid","real madryt","rma"} or "real madrid" in x or "real madryt" in x for x in norms):
            raise ValueError("Real Madryt jest banned 🚫")
        if norms[0]==norms[1]: raise ValueError("W meczu 1 vs 1 wybierz dwie różne drużyny.")
        flags=list(cash_flags) if cash_flags is not None else [True,True]
        if len(flags)!=2: flags=[True,True]
        # If either player opts out, the duel is automatically free. No one-sided stake.
        effective_stake=float(stake_per_player or 0) if all(bool(x) for x in flags) else 0.0
        tid=str(uuid.uuid4());rng=random.SystemRandom()
        with self.connect() as conn:
            pids=[self._get_or_create_player_conn(conn,n) for n in clean]
            draw={"slots":{"A":pids[0],"B":pids[1]}}
            extra={"stake_per_player":self._stake_cents(effective_stake)/100,"cash_player_ids":pids if effective_stake>0 else [],
                   "cash_player_names":clean if effective_stake>0 else [],"is_duel":True}
            self._setting_set_conn(conn,CURRENT_KEY,tid); self._setting_set_conn(conn,LAST_STAKE_KEY,f"{extra['stake_per_player']:.2f}")
            conn.execute(self._sql("INSERT INTO tournaments (id,status,phase,is_test,is_current,groups_revealed,created_at) VALUES (?,'active','active',?,0,0,?)"),(tid,int(is_test),now_iso()))
            for i,(pid,team) in enumerate(zip(pids,teams),1):
                conn.execute(self._sql("INSERT INTO tournament_players (tournament_id,player_id,team,team_reveal_order,team_revealed,group_name,tie_order) VALUES (?,?,?,?,1,'',?)"),(tid,pid,team,i,i))
            conn.execute(self._sql("INSERT INTO flex_tournament_meta (tournament_id,player_count,format_key,team_pool_json,draw_json,extra_json,draw_revealed,redraw_count) VALUES (?,?,?,?,?,?,1,0)"),(tid,2,'duel1v1',json.dumps(teams,ensure_ascii=False),json.dumps(draw),json.dumps(extra,ensure_ascii=False)))
            plan=schedule_for_format(draw,'duel1v1',extra,rng)
            for item in plan:
                conn.execute(self._sql("INSERT INTO matches (id,tournament_id,match_no,stage,group_name) VALUES (?,?,?,?,?)"),(str(uuid.uuid4()),tid,item['match_no'],item['stage'],item['group_name']))
                conn.execute(self._sql("INSERT INTO flex_match_sources (tournament_id,match_no,home_source,away_source) VALUES (?,?,?,?)"),(tid,item['match_no'],item['home'],item['away']))
            self._resolve_all_conn(conn,tid,'duel1v1')
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
            extra=json.loads(meta.get("extra_json") or "{}")
            t.update({"player_count": int(meta["player_count"]), "format_key": meta["format_key"], "draw_revealed": int(meta["draw_revealed"]), "redraw_count": int(meta["redraw_count"]), "stake_per_player": float(extra.get("stake_per_player") or 0)})
            return t

    def tournament_players(self, tid: str) -> list[dict]:
        with self.connect() as conn:
            return self._fetchall(conn, """SELECT tp.*,p.name FROM tournament_players tp JOIN players p ON p.id=tp.player_id WHERE tp.tournament_id=? ORDER BY tp.team_reveal_order""", (tid,))

    def tournament_live_scorers(self, tid: str, limit: int = 3) -> list[dict]:
        """Top entered scorers for the currently viewed event."""
        with self.connect() as conn:
            rows=self._fetchall(conn,"""SELECT scorer_name,SUM(goals) AS goals
                FROM match_scorers WHERE tournament_id=?
                GROUP BY scorer_name ORDER BY SUM(goals) DESC,scorer_name""",(tid,))
        return [{"name":str(r.get("scorer_name") or "?"),"goals":int(r.get("goals") or 0)} for r in rows[:max(1,int(limit or 3))]]

    def tournament_live_dashboard(self, tid: str) -> dict:
        """Compact live counters for the TV AUTO dashboard of one tournament.

        Score-based counters work for every played match. Event counters use only
        detailed EA FC match_events, so older/manual-only matches are never guessed.
        The technical +1 Winners Bracket advantage in a DE Grand Final is excluded
        from the real-goal total and from the highest-scoring-match calculation.
        """
        with self.connect() as conn:
            meta=self._fetchone(conn,"SELECT format_key FROM flex_tournament_meta WHERE tournament_id=?",(tid,)) or {}
            fmt=str(meta.get("format_key") or "")
            matches=self._fetchall(conn,"""SELECT m.match_no,m.stage,m.home_score,m.away_score,m.match_status,
                       hp.name AS home_name,ap.name AS away_name
                FROM matches m
                LEFT JOIN players hp ON hp.id=m.home_player_id
                LEFT JOIN players ap ON ap.id=m.away_player_id
                WHERE m.tournament_id=? AND m.home_score IS NOT NULL
                ORDER BY m.match_no""",(tid,))
            events=self._fetchall(conn,"""SELECT me.match_no,me.event_type,me.synthetic_de,me.minute
                FROM match_events me
                JOIN matches m ON m.tournament_id=me.tournament_id AND m.match_no=me.match_no
                WHERE me.tournament_id=? AND m.home_score IS NOT NULL
                ORDER BY me.match_no,me.event_order,me.id""",(tid,))

        def real_score(m: dict) -> tuple[int,int]:
            hs=int(m.get("home_score") or 0); ass=int(m.get("away_score") or 0)
            if fmt.startswith("double") and str(m.get("stage") or "")=="FINAL":
                hs=max(0,hs-1)
            return hs,ass

        played=len(matches)
        total_goals=0
        highest=None
        for m in matches:
            hs,ass=real_score(m); total=hs+ass; total_goals+=total
            candidate={
                "match_no":int(m.get("match_no") or 0),
                "home_name":str(m.get("home_name") or "?"),
                "away_name":str(m.get("away_name") or "?"),
                "home_score":hs,"away_score":ass,"goals":total,
            }
            if highest is None or (total,int(m.get("match_no") or 0))>(highest["goals"],highest["match_no"]):
                highest=candidate

        counters={"penalties_awarded":0,"yellow_cards":0,"red_cards":0,"own_goals":0,"extra_time_goals":0}
        detailed_match_nos=set()
        for e in events:
            detailed_match_nos.add(int(e.get("match_no") or 0))
            et=str(e.get("event_type") or "")
            synthetic=bool(int(e.get("synthetic_de") or 0))
            if et in {"penalty_goal","penalty_miss"}: counters["penalties_awarded"]+=1
            if et=="yellow_card": counters["yellow_cards"]+=1
            if et=="red_card": counters["red_cards"]+=1
            if et=="own_goal" and not synthetic: counters["own_goals"]+=1
            try: minute=int(e.get("minute") or 0)
            except Exception: minute=0
            if et in {"normal_goal","penalty_goal","own_goal"} and not synthetic and minute>90:
                counters["extra_time_goals"]+=1

        return {
            "matches_played":played,
            "goals":total_goals,
            "goals_per_match":round(total_goals/played,2) if played else 0.0,
            "detailed_matches":len(detailed_match_nos),
            "highest_scoring_match":highest,
            **counters,
        }

    def match_scorers(self, tid: str, match_no: int) -> list[dict]:
        """Entered scorers for one match, grouped by side for schedule/history details."""
        with self.connect() as conn:
            rows=self._fetchall(conn,"""SELECT side,team_name,scorer_name,goals
                FROM match_scorers WHERE tournament_id=? AND match_no=?
                ORDER BY CASE WHEN side='home' THEN 0 ELSE 1 END,goals DESC,scorer_name""",(tid,int(match_no)))
        return [{"side":str(r.get("side") or ""),"team_name":str(r.get("team_name") or ""),
                 "scorer_name":str(r.get("scorer_name") or "?"),"goals":int(r.get("goals") or 0)} for r in rows]

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
            meta,extra=self._meta_extra_conn(conn,tid)
            carry=extra.get("cross_tournament_priority") or {}
            placements=carry.get("placement_by_player_id") or {}
            current_count=len(pids)
            for _ in range(30):
                pids=weighted_draft_order(old,placements,carry.get("source_player_count"),current_count,rng)
                if pids!=old: break
            for i,pid in enumerate(pids,1):
                conn.execute(self._sql("UPDATE tournament_players SET team_reveal_order=?,tie_order=? WHERE tournament_id=? AND player_id=?"),(i,i,tid,pid))
            meta,extra=self._meta_extra_conn(conn,tid)
            extra["draft_order_revealed"]=True
            extra["draft_redraw_count"]=int(extra.get("draft_redraw_count",0))+1
            conn.execute(self._sql("UPDATE flex_tournament_meta SET extra_json=? WHERE tournament_id=?"),(json.dumps(extra),tid))
            players=self._fetchall(conn,"SELECT tp.*,p.name FROM tournament_players tp JOIN players p ON p.id=tp.player_id WHERE tp.tournament_id=? ORDER BY tp.team_reveal_order",(tid,))
            return {"players":players,"redraw_count":int(extra["draft_redraw_count"])}

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

    def available_wildcard_suggestions(self, tid: str) -> list[str]:
        """Unused concrete Wild Card clubs for this tournament, ordered by global popularity."""
        suggestions=self.wildcard_team_suggestions()
        with self.connect() as conn:
            picked=self._fetchall(conn,"SELECT team FROM tournament_players WHERE tournament_id=? AND team<>''",(tid,))
        used={self._norm_team_name(r.get("team") or "") for r in picked}
        return [x for x in suggestions if self._norm_team_name(x) not in used]

    def available_draft_teams(self, tid: str) -> list[str]:
        with self.connect() as conn:
            meta=self._fetchone(conn,"SELECT team_pool_json FROM flex_tournament_meta WHERE tournament_id=?",(tid,))
            if not meta: return []
            pool=json.loads(meta["team_pool_json"]); fixed=[x for x in pool if "Dowolna drużyna" not in x]
            picked=self._fetchall(conn,"SELECT team FROM tournament_players WHERE tournament_id=? AND team_revealed=1",(tid,))
            picked_names=[r["team"] for r in picked]
            fixed_norm={self._norm_team_name(x):x for x in fixed}; used_fixed={self._norm_team_name(x) for x in picked_names if self._norm_team_name(x) in fixed_norm}
            out=[x for x in fixed if self._norm_team_name(x) not in used_fixed]
            # Wild Card is deliberately reusable in 3–5 player drafts. The concrete
            # chosen club must still be unique and then disappears from suggestions.
            out.append("🃏 Wild Card")
            return out

    def draft_pick(self, tid: str, player_id: str, slot: str, wildcard_name: str = "") -> bool:
        with self.connect() as conn:
            t=self._fetchone(conn,"SELECT phase FROM tournaments WHERE id=?",(tid,))
            if not t or t["phase"]!="team_draft": raise ValueError("Draft drużyn nie jest aktywny.")
            current=self._fetchone(conn,"SELECT player_id FROM tournament_players WHERE tournament_id=? AND team_revealed=0 ORDER BY team_reveal_order LIMIT 1",(tid,))
            if not current: return True
            if current["player_id"]!=player_id: raise ValueError("Teraz wybiera inny gracz.")
            meta=self._fetchone(conn,"SELECT team_pool_json FROM flex_tournament_meta WHERE tournament_id=?",(tid,)); pool=json.loads(meta["team_pool_json"])
            fixed=[x for x in pool if "Dowolna drużyna" not in x]
            picked=self._fetchall(conn,"SELECT team FROM tournament_players WHERE tournament_id=? AND team_revealed=1",(tid,)); picked_names=[r["team"] for r in picked]
            picked_norm={self._norm_team_name(x) for x in picked_names}
            is_wild=(str(slot)=="🃏 Wild Card" or "Dowolna drużyna" in str(slot))
            if is_wild:
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
            # One state query instead of separate meta + player queries. This path is
            # hit on every wheel click, so keeping it short matters for perceived speed.
            row=self._fetchone(conn,"""SELECT tp.player_id,tp.team,p.name,fm.extra_json
                FROM tournament_players tp
                JOIN players p ON p.id=tp.player_id
                JOIN flex_tournament_meta fm ON fm.tournament_id=tp.tournament_id
                WHERE tp.tournament_id=? AND tp.team_revealed=0
                ORDER BY tp.team_reveal_order LIMIT 1""",(tid,))
            if not row: return None
            extra=json.loads(row.get("extra_json") or "{}")
            pending=extra.get("pending_wildcard")
            if pending: return {**pending,"wildcard":True}
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
        elif format_key in ("league3_final", "league4_final", "league5_final"):
            for i,pid in enumerate(draw["slots"].values(),1):
                conn.execute(self._sql("UPDATE tournament_players SET group_name='L', tie_order=? WHERE tournament_id=? AND player_id=?"), (i,tid,pid))

    def reveal_structure(self, tid: str) -> None:
        # Fast reveal path: the animation already has draw_json in memory. Group/table
        # metadata is only needed once the structure is accepted, so don't perform
        # 6–8 remote UPDATEs before the reveal animation can start.
        with self.connect() as conn:
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
            previous_extra=json.loads(meta.get("extra_json") or "{}")
            extra = self._extra_for_format(meta["format_key"], rng)
            for key in ("stake_per_player","cash_player_ids","cash_player_names","team_rating_snapshot","cash_settled","cash_settled_at"):
                if key in previous_extra: extra[key]=previous_extra.get(key)
            extra["stake_per_player"]=float(previous_extra.get("stake_per_player") or 0)
            if carry:
                new=apply_cross_tournament_bye_priority(new,meta["format_key"],carry.get("priority_by_player_id") or {},rng,carry.get("new_player_ids") or [])
                extra["cross_tournament_priority"]=carry
            conn.execute(self._sql("UPDATE flex_tournament_meta SET draw_json=?,extra_json=?,draw_revealed=1,redraw_count=redraw_count+1 WHERE tournament_id=?"), (json.dumps(new),json.dumps(extra),tid))
            # As above, defer group metadata writes until the draw is accepted.
            return {"draw":new,"redraw_count":int(meta.get("redraw_count") or 0)+1,"format_key":meta["format_key"]}

    def confirm_structure(self, tid: str) -> None:
        rng = random.SystemRandom()
        with self.connect() as conn:
            meta = self._fetchone(conn, "SELECT * FROM flex_tournament_meta WHERE tournament_id=?", (tid,))
            if not int(meta["draw_revealed"]): raise ValueError("Najpierw wykonaj losowanie.")
            draw = json.loads(meta["draw_json"]); extra = json.loads(meta["extra_json"])
            # Persist group/league membership only now, after the user accepts the draw.
            self._apply_draw_groups_conn(conn, tid, meta["format_key"], draw)
            t = self._fetchone(conn, "SELECT is_test FROM tournaments WHERE id=?", (tid,))
            rows = self._fetchall(conn, "SELECT tp.player_id,p.name FROM tournament_players tp JOIN players p ON p.id=tp.player_id WHERE tp.tournament_id=? ORDER BY tp.team_reveal_order", (tid,))
            pids=[r["player_id"] for r in rows]; names=[r["name"] for r in rows]
            carry_info=self._cross_tournament_priority_conn(conn,names,pids,bool(int((t or {}).get("is_test") or 0)))
            if carry_info: extra["cross_tournament_priority"]=carry_info
            else: extra.pop("cross_tournament_priority",None)
            plan = schedule_for_format(draw, meta["format_key"], extra, rng)
            carry=(carry_info.get("priority_by_player_id") or {}) if carry_info else {}
            preferred=optimize_opening_order(plan,carry,rng,(carry_info.get("new_player_ids") or []) if carry_info else []) if carry else [dict(x) for x in plan]
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

    def setup_bundle(self, tid: str) -> dict:
        """Lightweight state for pre-tournament draw screens (no matches query)."""
        with self.connect() as conn:
            t = self._fetchone(conn, "SELECT * FROM tournaments WHERE id=?", (tid,))
            meta = self._fetchone(conn, "SELECT * FROM flex_tournament_meta WHERE tournament_id=?", (tid,))
            players = self._fetchall(conn, "SELECT tp.*,p.name FROM tournament_players tp JOIN players p ON p.id=tp.player_id WHERE tp.tournament_id=? ORDER BY tp.team_reveal_order", (tid,))
            if meta:
                meta["draw"] = json.loads(meta["draw_json"]); meta["extra"] = json.loads(meta["extra_json"]); meta["team_pool"] = json.loads(meta["team_pool_json"])
            return {"tournament":t,"meta":meta,"players":players}

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
            group,pos = rest[0],int(rest[1])
            # Pozycja w tabeli może zasilić fazę pucharową dopiero po zamknięciu
            # wszystkich meczów tej ligi/grupy. Sam warunek „każdy zagrał choć raz”
            # był zbyt słaby: po awaryjnym przesunięciu meczu mógł przedwcześnie
            # odblokować finał ligi, mimo że jeden mecz ligowy nadal czekał.
            group_matches=[m for m in match_map.values() if str(m.get("group_name") or "")==group and str(m.get("stage") or "") in ("GROUP","LEAGUE")]
            group_closed=bool(group_matches) and all(m.get("home_score") is not None or str(m.get("match_status") or "pending")=="skipped" for m in group_matches)
            if not group_closed:return None
            table=self._table_from_conn(conn,tid,group)
            return table[pos-1]["player_id"] if len(table)>=pos else None
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

    def double7_combined_draw_state(self, tid: str) -> dict | None:
        """One combined post-R1 draw for DE7: Winners pairs + Losers lucky pass."""
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
            bye=extra.get("d7_lb_bye_match")
            selected_lucky=next((c for c in candidates if bye and int(c["match_no"])==int(bye)),None)
            pairs=[]
            if extra.get("d7_wb_draw"):
                for no in (4,5):
                    m=mm.get(no)
                    if m and m.get("home_player_id") and m.get("away_player_id"):
                        pairs.append({"match_no":no,"stage":"WB","home_name":m.get("home_name"),"away_name":m.get("away_name")})
            selected=bool(extra.get("d7_wb_draw") and extra.get("d7_lb_bye_match"))
            ack=bool(extra.get("d7_wb_draw_ack") and extra.get("d7_lb_draw_ack"))
            return {"pairs":pairs,"candidates":candidates,"selected_lucky":selected_lucky,"selected":selected,"ack":ack}

    def reveal_double7_combined_draw(self, tid: str) -> dict:
        """Atomically reveal Winners pairings and the first Losers lucky pass for DE7."""
        rng=random.SystemRandom()
        with self.connect() as conn:
            meta,extra=self._meta_extra_conn(conn,tid)
            if meta["format_key"]!="double7": raise ValueError("To losowanie nie dotyczy tego formatu.")
            mm={int(m["match_no"]):m for m in self._fetchall(conn,"SELECT * FROM matches WHERE tournament_id=? ORDER BY match_no",(tid,))}
            if not all(self._match_played(mm.get(i)) for i in (1,2,3)):
                raise ValueError("Najpierw dokończ pierwszą rundę Winners Bracket.")

            if not extra.get("d7_wb_draw"):
                sources=["W:1","W:2","W:3"]
                draw=json.loads(meta["draw_json"]); sources.append(f"P:{draw['slots']['G']}")
                rng.shuffle(sources)
                pairs=[sources[:2],sources[2:4]]
                # Pair composition stays random; only their play order may be swapped for rest.
                if "W:3" in pairs[0]: pairs=[pairs[1],pairs[0]]
                extra["d7_wb_draw"]={"M4H":pairs[0][0],"M4A":pairs[0][1],"M5H":pairs[1][0],"M5A":pairs[1][1]}
            extra["d7_wb_draw_ack"]=False

            if not extra.get("d7_lb_bye_match"):
                carry=(extra.get("cross_tournament_priority") or {}).get("priority_by_player_id") or {}
                loser_by_match={no:self._loser_of(mm.get(no)) for no in (1,2,3)}
                new_ids=(extra.get("cross_tournament_priority") or {}).get("new_player_ids") or []
                chosen_pid=weighted_bye_choice([pid for pid in loser_by_match.values() if pid],carry,rng,new_ids) if carry else None
                chosen_no=next((no for no,pid in loser_by_match.items() if chosen_pid and pid==chosen_pid),None)
                extra["d7_lb_bye_match"]=int(chosen_no or rng.choice([1,2,3]))
                extra["d7_pairing"]=None
            extra["d7_lb_draw_ack"]=False

            conn.execute(self._sql("UPDATE flex_tournament_meta SET extra_json=? WHERE tournament_id=?"),(json.dumps(extra),tid))
            self._resolve_all_conn(conn,tid,"double7")

            rows=self._matches_conn(conn,tid); by_no={int(m["match_no"]):m for m in rows}
            pairs=[]
            for no in (4,5):
                m=by_no[no]; pairs.append({"match_no":no,"stage":"WB","home_name":m.get("home_name"),"away_name":m.get("away_name")})
            players={r["player_id"]:r["name"] for r in self._fetchall(conn,"SELECT tp.player_id,p.name FROM tournament_players tp JOIN players p ON p.id=tp.player_id WHERE tp.tournament_id=?",(tid,))}
            candidates=[]
            for no in (1,2,3):
                pid=self._loser_of(mm.get(no))
                if pid: candidates.append({"match_no":no,"player_id":pid,"name":players.get(pid,"?")})
            lucky_no=int(extra["d7_lb_bye_match"]); lucky=next((c for c in candidates if int(c["match_no"])==lucky_no),None)
            return {"pairs":pairs,"candidates":candidates,"selected_lucky":lucky}

    def ack_double7_combined_draw(self, tid: str) -> None:
        with self.connect() as conn:
            meta,extra=self._meta_extra_conn(conn,tid)
            if meta["format_key"]!="double7": return
            if extra.get("d7_wb_draw") and extra.get("d7_lb_bye_match"):
                extra["d7_wb_draw_ack"]=True
                extra["d7_lb_draw_ack"]=True
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
                new_ids=(extra.get("cross_tournament_priority") or {}).get("new_player_ids") or []
                chosen_pid=weighted_bye_choice([pid for pid in loser_by_match.values() if pid],carry,rng,new_ids) if carry else None
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

    def match_ai_context(self, tid: str, match_no: int) -> dict:
        """Authoritative FIFA Night context for a vision scan.

        The physical EA FC screen may place either club on the left/right.  The app
        therefore identifies participants by the club assigned in tournament_players,
        not by UI side.  home/away is kept only as an internal bracket slot needed by
        the existing result engine.
        """
        with self.connect() as conn:
            row=self._fetchone(conn,"""
                SELECT m.*,fm.format_key,
                       hp.name AS home_player_name,ap.name AS away_player_name,
                       htp.team AS home_team,atp.team AS away_team
                FROM matches m
                JOIN flex_tournament_meta fm ON fm.tournament_id=m.tournament_id
                LEFT JOIN players hp ON hp.id=m.home_player_id
                LEFT JOIN players ap ON ap.id=m.away_player_id
                LEFT JOIN tournament_players htp ON htp.tournament_id=m.tournament_id AND htp.player_id=m.home_player_id
                LEFT JOIN tournament_players atp ON atp.tournament_id=m.tournament_id AND atp.player_id=m.away_player_id
                WHERE m.tournament_id=? AND m.match_no=?
            """,(tid,int(match_no)))
        if not row:
            raise ValueError("Nie znaleziono meczu.")
        if not row.get("home_player_id") or not row.get("away_player_id"):
            raise ValueError("Ten mecz nie ma jeszcze ustalonych graczy.")
        fmt=str(row.get("format_key") or "")
        stage=str(row.get("stage") or "")
        is_de_final=fmt.startswith("double") and stage=="FINAL"
        participants=[
            {"slot":"home","player_id":str(row.get("home_player_id") or ""),"player_name":str(row.get("home_player_name") or ""),"team":str(row.get("home_team") or "")},
            {"slot":"away","player_id":str(row.get("away_player_id") or ""),"player_name":str(row.get("away_player_name") or ""),"team":str(row.get("away_team") or "")},
        ]
        return {
            "tournament_id":str(tid),"match_no":int(match_no),"stage":stage,"format_key":fmt,
            "participants":participants,
            # Existing DE logic stores the Winners Bracket +1 on the internal home slot.
            "de_wb_advantage_player_id":str(row.get("home_player_id") or "") if is_de_final else None,
            "de_wb_advantage_team":str(row.get("home_team") or "") if is_de_final else None,
            "de_wb_bonus":1 if is_de_final else 0,
        }

    def match_events(self, tid: str, match_no: int) -> list[dict]:
        """Detailed event timeline available for new scanned/confirmed matches."""
        with self.connect() as conn:
            rows=self._fetchall(conn,"""
                SELECT * FROM match_events
                WHERE tournament_id=? AND match_no=?
                ORDER BY event_order,id
            """,(tid,int(match_no)))
        for r in rows:
            try:r["source_images"]=json.loads(r.get("source_images_json") or "[]")
            except Exception:r["source_images"]=[]
            r["synthetic_de"]=bool(int(r.get("synthetic_de") or 0))
        return rows

    def _save_match_events_conn(self, conn, tid: str, match_no: int, events: list[dict] | None) -> None:
        """Replace the detailed timeline for one match.

        Events are already mapped by the backend from the club shown on the EA FC
        screen to the FIFA Night participant who owns that assigned club.
        """
        conn.execute(self._sql("DELETE FROM match_events WHERE tournament_id=? AND match_no=?"),(tid,int(match_no)))
        if not events:return
        allowed={"normal_goal","penalty_goal","own_goal","penalty_miss","yellow_card","red_card","injury","substitution"}
        for idx,raw in enumerate(events,1):
            et=str(raw.get("event_type") or "").strip()
            if et not in allowed:continue
            minute=raw.get("minute");stoppage=raw.get("stoppage")
            try: minute=int(minute) if minute is not None else None
            except Exception: minute=None
            try: stoppage=int(stoppage) if stoppage is not None else None
            except Exception: stoppage=None
            footballer=" ".join(str(raw.get("footballer_name") or "").strip().split())
            related=" ".join(str(raw.get("related_footballer_name") or "").strip().split())
            actor_team=" ".join(str(raw.get("actor_team_name") or "").strip().split())
            credited_team=" ".join(str(raw.get("credited_team_name") or "").strip().split())
            order=raw.get("event_order")
            try:order=int(order)
            except Exception:order=idx
            sources=raw.get("source_images") or []
            sources=[int(x) for x in sources if str(x).isdigit()]
            conn.execute(self._sql("""
                INSERT INTO match_events (
                    id,tournament_id,match_no,event_order,event_type,minute,stoppage,minute_label,
                    actor_player_id,credited_player_id,actor_team_name,credited_team_name,
                    footballer_name,normalized_footballer,related_footballer_name,
                    synthetic_de,confidence,source_images_json,created_at
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """),(
                str(uuid.uuid4()),tid,int(match_no),order,et,minute,stoppage,str(raw.get("minute_label") or ""),
                str(raw.get("actor_player_id") or "") or None,str(raw.get("credited_player_id") or "") or None,
                actor_team,credited_team,footballer,self._norm_scorer_name(footballer),related,
                1 if raw.get("synthetic_de") else 0,str(raw.get("confidence") or ""),json.dumps(sources),now_iso()
            ))

    def _serve_active_absences_conn(self, conn, tid: str, match_no: int, player_ids: list[str]) -> None:
        """Serve existing one-match absences when a player actually plays their next match.

        The scheduler may defer matches, so match number is irrelevant. Whichever match is
        actually saved next for the FIFA Night player consumes every active absence that
        originated in an earlier match. New absences from the match being saved are added
        only afterwards and therefore remain active for the following match.
        """
        for pid in {str(x or "") for x in player_ids if str(x or "")}:
            conn.execute(self._sql("""
                UPDATE tournament_absences
                SET served_match_no=?, served_at=?
                WHERE tournament_id=? AND player_id=? AND served_match_no IS NULL AND source_match_no<>?
            """),(int(match_no),now_iso(),tid,pid,int(match_no)))

    def _sync_absences_from_events_conn(self, conn, tid: str, match_no: int, events: list[dict] | None) -> None:
        """Create next-match absences from red cards and injuries detected in this match."""
        # Re-saving/replacing a scan for the same match must not duplicate sanctions.
        conn.execute(self._sql("DELETE FROM tournament_absences WHERE tournament_id=? AND source_match_no=?"),(tid,int(match_no)))
        seen=set()
        for e in events or []:
            et=str(e.get("event_type") or "")
            if et not in {"red_card","injury"}:
                continue
            pid=str(e.get("actor_player_id") or "").strip()
            footballer=" ".join(str(e.get("footballer_name") or "").strip().split())
            if not pid or not footballer:
                continue
            norm=self._norm_scorer_name(footballer)
            reason="red_card" if et=="red_card" else "injury"
            key=(pid,norm,reason)
            if key in seen:
                continue
            seen.add(key)
            conn.execute(self._sql("""
                INSERT INTO tournament_absences (
                    id,tournament_id,player_id,footballer_name,normalized_footballer,reason,
                    source_match_no,served_match_no,created_at,served_at
                ) VALUES (?,?,?,?,?,?,?,?,?,?)
            """),(str(uuid.uuid4()),tid,pid,footballer,norm,reason,int(match_no),None,now_iso(),None))

    def active_absences(self, tid: str) -> list[dict]:
        """Unserved tournament-only absences, enriched with FIFA Night player/team."""
        with self.connect() as conn:
            return self._fetchall(conn,"""
                SELECT a.*, p.name AS player_name, tp.team AS team_name
                FROM tournament_absences a
                JOIN players p ON p.id=a.player_id
                LEFT JOIN tournament_players tp ON tp.tournament_id=a.tournament_id AND tp.player_id=a.player_id
                WHERE a.tournament_id=? AND a.served_match_no IS NULL
                ORDER BY a.created_at,a.footballer_name
            """,(tid,))

    def tournament_absences(self, tid: str, include_served: bool = False) -> list[dict]:
        with self.connect() as conn:
            where="" if include_served else " AND a.served_match_no IS NULL"
            return self._fetchall(conn,f"""
                SELECT a.*, p.name AS player_name, tp.team AS team_name
                FROM tournament_absences a
                JOIN players p ON p.id=a.player_id
                LEFT JOIN tournament_players tp ON tp.tournament_id=a.tournament_id AND tp.player_id=a.player_id
                WHERE a.tournament_id=?{where}
                ORDER BY a.created_at,a.footballer_name
            """,(tid,))

    def _aggregate_scorers_from_events(self, events: list[dict] | None, home_pid: str, away_pid: str,
                                       home_team: str, away_team: str) -> dict:
        """Convert detailed goal events back to the legacy match_scorers payload.

        Penalty goals count for the footballer. Own goals (including the technical DE
        bonus) never do. This keeps all existing scorer/Awards code working unchanged.
        """
        totals={"home":defaultdict(int),"away":defaultdict(int)}
        for e in events or []:
            if str(e.get("event_type") or "") not in {"normal_goal","penalty_goal"}:continue
            if e.get("synthetic_de"):continue
            name=" ".join(str(e.get("footballer_name") or "").strip().split())
            if not name:continue
            credited=str(e.get("credited_player_id") or "")
            if credited==str(home_pid):totals["home"][name]+=1
            elif credited==str(away_pid):totals["away"][name]+=1
        return {
            "home":{"team":home_team,"items":[{"name":n,"goals":g} for n,g in totals["home"].items()]},
            "away":{"team":away_team,"items":[{"name":n,"goals":g} for n,g in totals["away"].items()]},
        }

    def player_event_stats(self) -> list[dict]:
        """Raw new-era discipline/penalty counters for FIFA Night players.

        Used later by Statistics/Awards. Penalties awarded include both scored and
        missed penalties. Shoot-out kicks are never written to match_events.
        """
        with self.connect() as conn:
            rows=self._fetchall(conn,"""
                SELECT p.id AS player_id,p.name AS player_name,
                       SUM(CASE WHEN me.event_type='yellow_card' THEN 1 ELSE 0 END) AS yellows,
                       SUM(CASE WHEN me.event_type='red_card' THEN 1 ELSE 0 END) AS reds,
                       SUM(CASE WHEN me.event_type IN ('penalty_goal','penalty_miss') THEN 1 ELSE 0 END) AS penalties_awarded,
                       SUM(CASE WHEN me.event_type='penalty_goal' THEN 1 ELSE 0 END) AS penalties_scored,
                       SUM(CASE WHEN me.event_type='penalty_miss' THEN 1 ELSE 0 END) AS penalties_missed,
                       SUM(CASE WHEN me.event_type='own_goal' AND COALESCE(me.synthetic_de,0)=0 THEN 1 ELSE 0 END) AS own_goals
                FROM players p
                JOIN match_events me ON me.actor_player_id=p.id
                JOIN tournaments t ON t.id=me.tournament_id
                WHERE t.status IN ('completed','abandoned') AND t.is_test=0
                GROUP BY p.id,p.name ORDER BY p.name
            """)
        return [{**r,**{k:int(r.get(k) or 0) for k in ("yellows","reds","penalties_awarded","penalties_scored","penalties_missed","own_goals")}} for r in rows]

    def player_detailed_event_stats(self, pid: str) -> dict:
        """Detailed new-era event counters for one FIFA Night player.

        These statistics intentionally use only official, non-test matches for which
        match_events exist. Older matches remain valid in the legacy statistics but
        cannot contribute to cards, penalties or minute-based records.
        """
        pid=str(pid or "")
        empty={
            "coverage_matches":0,"yellow_cards":0,"red_cards":0,"cards_total":0,
            "penalties_awarded":0,"penalties_scored":0,"penalties_missed":0,
            "own_goals":0,"detailed_goals":0,"goals_90_plus":0,"extra_time_goals":0,
            "fastest_goal":None,"latest_goal":None,
        }
        if not pid:return empty
        with self.connect() as conn:
            coverage=self._fetchone(conn,"""
                SELECT COUNT(*) AS c FROM (
                    SELECT DISTINCT m.tournament_id,m.match_no
                    FROM matches m
                    JOIN tournaments t ON t.id=m.tournament_id
                    JOIN match_events me ON me.tournament_id=m.tournament_id AND me.match_no=m.match_no
                    WHERE t.is_test=0 AND t.status IN ('completed','abandoned')
                      AND (m.home_player_id=? OR m.away_player_id=?)
                ) x
            """,(pid,pid))
            actor=self._fetchone(conn,"""
                SELECT
                    SUM(CASE WHEN me.event_type='yellow_card' THEN 1 ELSE 0 END) AS yellow_cards,
                    SUM(CASE WHEN me.event_type='red_card' THEN 1 ELSE 0 END) AS red_cards,
                    SUM(CASE WHEN me.event_type IN ('penalty_goal','penalty_miss') THEN 1 ELSE 0 END) AS penalties_awarded,
                    SUM(CASE WHEN me.event_type='penalty_goal' THEN 1 ELSE 0 END) AS penalties_scored,
                    SUM(CASE WHEN me.event_type='penalty_miss' THEN 1 ELSE 0 END) AS penalties_missed,
                    SUM(CASE WHEN me.event_type='own_goal' AND COALESCE(me.synthetic_de,0)=0 THEN 1 ELSE 0 END) AS own_goals
                FROM match_events me
                JOIN tournaments t ON t.id=me.tournament_id
                WHERE t.is_test=0 AND t.status IN ('completed','abandoned') AND me.actor_player_id=?
            """,(pid,)) or {}
            goals=self._fetchall(conn,"""
                SELECT me.minute,me.stoppage,me.minute_label,me.footballer_name,me.credited_team_name,
                       me.event_type,me.created_at
                FROM match_events me
                JOIN tournaments t ON t.id=me.tournament_id
                WHERE t.is_test=0 AND t.status IN ('completed','abandoned')
                  AND me.credited_player_id=?
                  AND me.event_type IN ('normal_goal','penalty_goal')
                  AND COALESCE(me.synthetic_de,0)=0
            """,(pid,))
        def minute_value(g):
            try:m=int(g.get("minute"))
            except Exception:return None
            try:s=int(g.get("stoppage") or 0)
            except Exception:s=0
            return m*100+s
        timed=[g for g in goals if minute_value(g) is not None]
        fastest=min(timed,key=minute_value) if timed else None
        latest=max(timed,key=minute_value) if timed else None
        def goal_desc(g):
            if not g:return None
            # Keep API data punctuation-free; individual UIs add their own minute mark.
            # Some scan/manual clients historically stored labels such as ``10'``.
            label=str(g.get("minute_label") or "").strip().replace("′","").replace("'","")
            if not label:
                try:
                    m=int(g.get("minute"));stp=int(g.get("stoppage") or 0);label=f"{m}+{stp}" if stp else str(m)
                except Exception:label="?"
            return {
                "minute_label":label,
                "footballer_name":str(g.get("footballer_name") or "?"),
                "team_name":str(g.get("credited_team_name") or ""),
                "event_type":str(g.get("event_type") or "normal_goal"),
            }
        out={**empty}
        out.update({
            "coverage_matches":int((coverage or {}).get("c") or 0),
            "yellow_cards":int(actor.get("yellow_cards") or 0),
            "red_cards":int(actor.get("red_cards") or 0),
            "penalties_awarded":int(actor.get("penalties_awarded") or 0),
            "penalties_scored":int(actor.get("penalties_scored") or 0),
            "penalties_missed":int(actor.get("penalties_missed") or 0),
            "own_goals":int(actor.get("own_goals") or 0),
            "detailed_goals":len(goals),
            "goals_90_plus":sum(1 for g in goals if int(g.get("minute") or 0)==90 and int(g.get("stoppage") or 0)>0),
            "extra_time_goals":sum(1 for g in goals if int(g.get("minute") or 0)>90),
            "fastest_goal":goal_desc(fastest),
            "latest_goal":goal_desc(latest),
        })
        out["cards_total"]=out["yellow_cards"]+out["red_cards"]
        return out

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
                WHERE t.status IN ('completed','abandoned') AND t.is_test=0
                GROUP BY ms.normalized_scorer ORDER BY goals DESC,matches_scored DESC,scorer_name""")
            teams=self._fetchall(conn,"""SELECT ms.normalized_scorer,ms.team_name,SUM(ms.goals) AS goals
                FROM match_scorers ms JOIN tournaments t ON t.id=ms.tournament_id
                WHERE t.status IN ('completed','abandoned') AND t.is_test=0
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
            WHERE t.status IN ('completed','abandoned') AND t.is_test=0 AND m.home_score IS NOT NULL"""
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
        trs=self._fetchall(conn,f"""SELECT t.id,t.status,t.champion_player_id,t.completed_at,t.created_at,fm.format_key
            FROM tournaments t LEFT JOIN flex_tournament_meta fm ON fm.tournament_id=t.id
            WHERE t.id IN ({qmarks}) ORDER BY COALESCE(t.completed_at,t.created_at)""",tuple(tids))
        tournament_ids={str(r["id"]) for r in trs if str(r.get("format_key") or "")!='duel1v1'}
        completed_tournament_ids={str(r["id"]) for r in trs if str(r.get("format_key") or "")!='duel1v1' and str(r.get("status") or "")=="completed"}
        tps=self._fetchall(conn,f"SELECT tournament_id,player_id FROM tournament_players WHERE tournament_id IN ({qmarks})",tuple(tids))
        players={r["id"]:r["name"] for r in self._fetchall(conn,"SELECT id,name FROM players")}
        finals=[m for m in matches if m["stage"]=="FINAL" and str(m["tournament_id"]) in completed_tournament_ids]
        ps=defaultdict(lambda:{"tournaments":0,"titles":0,"finals":0,"w":0,"d":0,"l":0,"gf":0,"ga":0})
        for tp in tps:
            if str(tp["tournament_id"]) in tournament_ids: ps[tp["player_id"]]["tournaments"]+=1
        for t in trs:
            if str(t["id"]) in completed_tournament_ids and t.get("champion_player_id"): ps[t["champion_player_id"]]["titles"]+=1
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
        for t in [x for x in trs if str(x["id"]) in tournament_ids]:
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

        # New-era records based on the exact EA FC event timeline. Older matches
        # stay valid in all legacy records above, but cannot take part in records
        # which require minutes or the exact order of goals.
        detailed_records={
            "fastest_goal":None,"latest_goal":None,"fastest_hat_trick":None,
            "biggest_comeback":None,"biggest_blown_lead":None,
        }
        match_lookup={(str(m.get("tournament_id")),int(m.get("match_no") or 0)):m for m in matches}
        if tids:
            event_rows=self._fetchall(conn,f"""SELECT me.tournament_id,me.match_no,me.event_order,me.event_type,
                    me.minute,me.stoppage,me.minute_label,me.footballer_name,me.synthetic_de,
                    me.actor_player_id,me.credited_player_id
                FROM match_events me
                WHERE me.tournament_id IN ({qmarks})
                ORDER BY me.tournament_id,me.match_no,me.event_order,me.id""",tuple(tids))
        else:
            event_rows=[]
        by_match=defaultdict(list)
        for e in event_rows:
            by_match[(str(e.get("tournament_id")),int(e.get("match_no") or 0))].append(e)

        def event_minute_value(e):
            try: minute=int(e.get("minute"))
            except Exception: return None
            try: stoppage=int(e.get("stoppage") or 0)
            except Exception: stoppage=0
            # 90+4 is treated as minute 94 and 120+1 as 121 for ordering and
            # hat-trick duration. event_order remains the source of chronology.
            return minute+max(stoppage,0)

        def event_label(e):
            label=str(e.get("minute_label") or "").strip().replace("′","").replace("'","")
            if label:return label
            try: minute=int(e.get("minute"))
            except Exception:return "?"
            try: stoppage=int(e.get("stoppage") or 0)
            except Exception:stoppage=0
            return f"{minute}+{stoppage}" if stoppage else str(minute)

        def match_desc(m):
            return f"{m.get('home_name') or '?'} {int(m.get('home_score') or 0)}:{int(m.get('away_score') or 0)} {m.get('away_name') or '?'}"

        # Fastest/latest goal and fastest hat-trick: only real goals credited to a
        # footballer. Own goals and the technical DE advantage are not individual
        # scoring records.
        individual_goal_types={"normal_goal","penalty_goal"}
        goal_candidates=[]
        hat_groups=defaultdict(list)
        for mk,evs in by_match.items():
            m=match_lookup.get(mk)
            if not m:continue
            for e in evs:
                if str(e.get("event_type") or "") not in individual_goal_types:continue
                if int(e.get("synthetic_de") or 0):continue
                if not str(e.get("credited_player_id") or ""):continue
                mv=event_minute_value(e)
                if mv is None:continue
                item={
                    "minute_value":mv,"minute_label":event_label(e),
                    "footballer":str(e.get("footballer_name") or "?").strip() or "?",
                    "player_id":str(e.get("credited_player_id") or ""),
                    "player_name":players.get(e.get("credited_player_id"),"?"),
                    "match":match_desc(m),"event_order":int(e.get("event_order") or 10**9),
                    "tournament_id":mk[0],"match_no":mk[1],
                }
                goal_candidates.append(item)
                norm=" ".join(item["footballer"].lower().split())
                hat_groups[(mk[0],mk[1],item["player_id"],norm)].append(item)
        if goal_candidates:
            fastest=min(goal_candidates,key=lambda x:(x["minute_value"],x["event_order"]))
            latest=max(goal_candidates,key=lambda x:(x["minute_value"],-x["event_order"]))
            detailed_records["fastest_goal"]={k:v for k,v in fastest.items() if k not in ("event_order","tournament_id","match_no")}
            detailed_records["latest_goal"]={k:v for k,v in latest.items() if k not in ("event_order","tournament_id","match_no")}
        best_hat=None
        for _key,goals in hat_groups.items():
            goals=sorted(goals,key=lambda x:(x["event_order"],x["minute_value"]))
            if len(goals)<3:continue
            for i in range(len(goals)-2):
                first,third=goals[i],goals[i+2]
                duration=max(0,int(third["minute_value"])-int(first["minute_value"]))
                candidate={
                    "duration":duration,"footballer":first["footballer"],"player_name":first["player_name"],
                    "from_label":first["minute_label"],"to_label":third["minute_label"],"match":first["match"],
                }
                if best_hat is None or (duration,int(third["minute_value"])) < (int(best_hat["duration"]),int(best_hat.get("to_value") or 10**9)):
                    candidate["to_value"]=int(third["minute_value"]);best_hat=candidate
        if best_hat:
            best_hat.pop("to_value",None);detailed_records["fastest_hat_trick"]=best_hat

        # Comeback / blown lead records need a complete goal timeline. All goals
        # affecting the scoreboard count here (including own goals and the technical
        # DE starting advantage), but only when their count matches the final score.
        score_goal_types={"normal_goal","penalty_goal","own_goal"}
        best_comeback=None;best_blown=None
        for mk,evs in by_match.items():
            m=match_lookup.get(mk)
            if not m:continue
            h=str(m.get("home_player_id") or "");a=str(m.get("away_player_id") or "")
            if not h or not a:continue
            hs=int(m.get("home_score") or 0);ass=int(m.get("away_score") or 0)
            winner=str(m.get("winner_player_id") or "")
            if not winner:
                if hs>ass:winner=h
                elif ass>hs:winner=a
            if winner not in (h,a):continue
            loser=a if winner==h else h
            goals=[e for e in evs if str(e.get("event_type") or "") in score_goal_types and str(e.get("credited_player_id") or "") in (h,a)]
            if len(goals)!=(hs+ass):continue
            goals=sorted(goals,key=lambda e:(int(e.get("event_order") or 10**9),int(e.get("minute") or 0),int(e.get("stoppage") or 0)))
            score={h:0,a:0};max_winner_deficit=0;max_loser_lead=0
            for e in goals:
                pid=str(e.get("credited_player_id") or "")
                score[pid]+=1
                deficit=score[loser]-score[winner]
                if deficit>max_winner_deficit:max_winner_deficit=deficit
                lead=score[loser]-score[winner]
                if lead>max_loser_lead:max_loser_lead=lead
            if max_winner_deficit>0:
                rec={
                    "deficit":max_winner_deficit,"player_id":winner,"player_name":players.get(winner,"?"),
                    "opponent_name":players.get(loser,"?"),"match":match_desc(m),
                }
                if best_comeback is None or max_winner_deficit>int(best_comeback.get("deficit") or 0):best_comeback=rec
            if max_loser_lead>0:
                rec={
                    "lead":max_loser_lead,"player_id":loser,"player_name":players.get(loser,"?"),
                    "opponent_name":players.get(winner,"?"),"match":match_desc(m),
                }
                if best_blown is None or max_loser_lead>int(best_blown.get("lead") or 0):best_blown=rec
        detailed_records["biggest_comeback"]=best_comeback
        detailed_records["biggest_blown_lead"]=best_blown

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
            "detailed_records":detailed_records,
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
        if fmt in ("league3_final","league4_final","league5_final"):
            ids=list(players.keys());ties={pid:int(players[pid].get("tie_order") or 9999) for pid in ids}
            league_matches=[m for m in played if m.get("stage")=="LEAGUE"]
            table=group_table(ids,league_matches,ties)
            if len(table)>=3:third_pid=table[2]["player_id"]
            if len(table)>=4:fourth_pid=table[3]["player_id"]
        elif fmt in ("groups6","groups6_full","groups7","groups7_sf","groups8_sf","groups8_barrage"):
            sf_losers=rank_same_stage([self._loser_of(m) for m in played if m.get("stage")=="SF"])
            if sf_losers: third_pid=sf_losers[0]
            if len(sf_losers)>1: fourth_pid=sf_losers[1]
        elif fmt=="double4":
            third_pid=self._loser_of(by_no.get(5)); fourth_pid=self._loser_of(by_no.get(3))
        elif fmt=="double5":
            third_pid=self._loser_of(by_no.get(7)); fourth_pid=self._loser_of(by_no.get(6))
        elif fmt=="double6":
            third_pid=self._loser_of(by_no.get(9)); fourth_pid=self._loser_of(by_no.get(8))
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
                    SELECT t.id FROM tournaments t JOIN flex_tournament_meta fm ON fm.tournament_id=t.id
                    WHERE t.status IN ('completed','abandoned') AND t.is_test=0 AND fm.format_key<>'duel1v1'
                    ORDER BY COALESCE(t.completed_at,t.created_at), t.created_at, t.id
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
            if m.get("home_player_id") and m.get("away_player_id") and m.get("home_score") is None and str(m.get("match_status") or "pending")!="skipped":
                return m
        return None

    def next_ready_match_from(self, matches: list[dict], current_no: int, extra: dict | None = None) -> dict | None:
        order=[int(x) for x in ((extra or {}).get("match_play_order") or [])]
        rank={no:i for i,no in enumerate(order)}
        current_rank=rank.get(int(current_no),-1)
        ordered=sorted(matches,key=lambda m:(rank.get(int(m.get("match_no") or 0),10_000+int(m.get("match_no") or 0)),int(m.get("match_no") or 0)))
        later=[m for m in ordered if rank.get(int(m.get("match_no") or 0),10_000+int(m.get("match_no") or 0))>current_rank]
        for m in later:
            if m.get("home_player_id") and m.get("away_player_id") and m.get("home_score") is None and str(m.get("match_status") or "pending")!="skipped":
                return m
        return None

    def live_schedule_from(self, matches: list[dict], extra: dict | None = None) -> list[dict]:
        """Return matches in the order useful during a live tournament.

        Logical ``match_no`` never changes because bracket dependencies refer to it.
        The displayed schedule, however, should follow the preferred play order and
        react when a previously locked match becomes ready after a result. Completed
        matches stay at the top in their real played order, then currently ready
        matches are shown, and unresolved/locked matches follow afterwards.
        """
        order=[int(x) for x in ((extra or {}).get("match_play_order") or [])]
        rank={no:i for i,no in enumerate(order)}
        def pref(m):
            no=int(m.get("match_no") or 0)
            return (rank.get(no,10_000+no),no)
        def skipped(m):
            return str(m.get("match_status") or "pending")=="skipped"
        def done(m):
            return m.get("home_score") is not None or skipped(m)

        completed=[m for m in matches if done(m)]
        # played_at is an UTC ISO timestamp for both played and skipped matches.
        # Keep a deterministic fallback for legacy rows without a timestamp.
        completed.sort(key=lambda m:(str(m.get("played_at") or "9999"),pref(m)))
        pending=[m for m in matches if not done(m)]
        ready=sorted([m for m in pending if m.get("home_player_id") and m.get("away_player_id")],key=pref)
        locked=sorted([m for m in pending if not (m.get("home_player_id") and m.get("away_player_id"))],key=pref)
        return completed+ready+locked

    def can_defer_match(self, tid: str, match_no: int) -> dict:
        """Return whether an active match can be moved behind the next match that is ready now.

        This never skips or completes the match. It only changes the preferred live play order
        stored in ``extra_json``. The option is available only when at least one different
        pending match already has both players resolved, so the app always has something real
        to put on screen next.
        """
        with self.connect() as conn:
            meta=self._fetchone(conn,"SELECT extra_json FROM flex_tournament_meta WHERE tournament_id=?",(tid,))
            if not meta:
                return {"allowed":False,"reason":"Nie znaleziono turnieju."}
            extra=json.loads(meta.get("extra_json") or "{}")
            matches=self._matches_conn(conn,tid)
            order=[int(x) for x in (extra.get("match_play_order") or [])]
            rank={no:i for i,no in enumerate(order)}
            def pref(m):
                no=int(m.get("match_no") or 0)
                return (rank.get(no,10_000+no),no)
            ready=sorted([m for m in matches if m.get("home_player_id") and m.get("away_player_id") and m.get("home_score") is None and str(m.get("match_status") or "pending")!="skipped"],key=pref)
            current=next((m for m in ready if int(m.get("match_no") or 0)==int(match_no)),None)
            if current is None:
                return {"allowed":False,"reason":"Ten mecz nie jest teraz gotowy do rozegrania."}
            alternatives=[m for m in ready if int(m.get("match_no") or 0)!=int(match_no)]
            if not alternatives:
                return {"allowed":False,"reason":"Nie ma innego gotowego meczu, który można zagrać teraz."}
            nxt=alternatives[0]
            return {"allowed":True,"reason":"Można przesunąć ten mecz na później.",
                    "next_match_no":int(nxt.get("match_no") or 0),
                    "next_home":nxt.get("home_name") or "?","next_away":nxt.get("away_name") or "?"}

    def defer_match(self, tid: str, match_no: int) -> dict:
        """Move a ready match behind exactly the next playable match."""
        with self.connect() as conn:
            meta=self._fetchone(conn,"SELECT extra_json FROM flex_tournament_meta WHERE tournament_id=?",(tid,))
            if not meta:
                raise ValueError("Nie znaleziono turnieju.")
            extra=json.loads(meta.get("extra_json") or "{}")
            matches=self._matches_conn(conn,tid)
            valid_nos=[int(m.get("match_no") or 0) for m in matches]
            base=[int(x) for x in (extra.get("match_play_order") or []) if int(x) in valid_nos]
            for no in sorted(valid_nos):
                if no not in base: base.append(no)
            rank={no:i for i,no in enumerate(base)}
            def pref(m):
                no=int(m.get("match_no") or 0)
                return (rank.get(no,10_000+no),no)
            ready=sorted([m for m in matches if m.get("home_player_id") and m.get("away_player_id") and m.get("home_score") is None and str(m.get("match_status") or "pending")!="skipped"],key=pref)
            current=next((m for m in ready if int(m.get("match_no") or 0)==int(match_no)),None)
            alternatives=[m for m in ready if int(m.get("match_no") or 0)!=int(match_no)]
            if current is None:
                raise ValueError("Ten mecz nie jest teraz gotowy do rozegrania.")
            if not alternatives:
                raise ValueError("Nie ma innego gotowego meczu, który można zagrać teraz.")
            # Minimal manual intervention: move the current match by exactly one playable
            # slot. The algorithm still controls the rest of the order. If the player is
            # still unavailable when the match comes back, it can be deferred once more.
            reordered=[no for no in base if no!=int(match_no)]
            next_no=int(alternatives[0].get("match_no") or 0)
            next_idx=reordered.index(next_no)
            reordered.insert(next_idx+1,int(match_no))
            extra["match_play_order"]=reordered
            conn.execute(self._sql("UPDATE flex_tournament_meta SET extra_json=? WHERE tournament_id=?"),(json.dumps(extra,ensure_ascii=False),tid))
            nxt=alternatives[0]
            return {"next_match_no":int(nxt.get("match_no") or 0),
                    "next_home":nxt.get("home_name") or "?","next_away":nxt.get("away_name") or "?"}

    def can_skip_match(self, tid: str, match_no: int) -> dict:
        """Return whether the current league match can be skipped without changing the finalist pair.

        For safety this is intentionally limited to league+final formats and to the last
        still-pending league match. Scores in the app are bounded to 0..99, so checking
        all 10,000 possible scorelines is exact for the UI's result domain.
        """
        with self.connect() as conn:
            meta=self._fetchone(conn,"SELECT format_key FROM flex_tournament_meta WHERE tournament_id=?",(tid,))
            if not meta or meta.get("format_key") not in ("league3_final","league4_final","league5_final"):
                return {"allowed":False,"reason":"Pomijanie jest dostępne tylko w lidze + finał."}
            m=self._fetchone(conn,"SELECT * FROM matches WHERE tournament_id=? AND match_no=?",(tid,int(match_no)))
            if not m or m.get("stage")!="LEAGUE" or m.get("home_score") is not None or str(m.get("match_status") or "pending")=="skipped":
                return {"allowed":False,"reason":"Ten mecz nie jest oczekującym meczem ligowym."}
            if not m.get("home_player_id") or not m.get("away_player_id"):
                return {"allowed":False,"reason":"Nie ustalono jeszcze obu graczy."}
            league=self._fetchall(conn,"SELECT * FROM matches WHERE tournament_id=? AND stage='LEAGUE' ORDER BY match_no",(tid,))
            other_pending=[x for x in league if int(x["match_no"])!=int(match_no) and x.get("home_score") is None and str(x.get("match_status") or "pending")!="skipped"]
            if other_pending:
                return {"allowed":False,"reason":"To nie jest ostatni nierozstrzygnięty mecz ligowy."}
            prows=self._fetchall(conn,"SELECT player_id,tie_order FROM tournament_players WHERE tournament_id=? AND group_name='L'",(tid,))
            ids=[str(x["player_id"]) for x in prows];ties={str(x["player_id"]):int(x.get("tie_order") or 9999) for x in prows}
            played=[x for x in league if x.get("home_score") is not None]
            finalists=None
            for hs in range(100):
                for ass in range(100):
                    fake=dict(m);fake["home_score"]=hs;fake["away_score"]=ass
                    fake["home_penalties"]=None;fake["away_penalties"]=None
                    fake["winner_player_id"]=winner_from_result(hs,ass,m["home_player_id"],m["away_player_id"])
                    table=group_table(ids,played+[fake],ties)
                    pair=frozenset(str(x["player_id"]) for x in table[:2])
                    if finalists is None: finalists=pair
                    elif pair!=finalists:
                        return {"allowed":False,"reason":"Wynik może jeszcze zmienić parę finalistów."}
            names={r["id"]:r["name"] for r in self._fetchall(conn,"SELECT id,name FROM players")}
            return {"allowed":True,"reason":"Para finalistów jest już matematycznie pewna.",
                    "finalists":[names.get(pid,"?") for pid in (finalists or [])]}

    def skip_match(self, tid: str, match_no: int) -> None:
        check=self.can_skip_match(tid,match_no)
        if not check.get("allowed"):
            raise ValueError(check.get("reason") or "Tego meczu nie można bezpiecznie pominąć.")
        with self.connect() as conn:
            meta=self._fetchone(conn,"SELECT format_key FROM flex_tournament_meta WHERE tournament_id=?",(tid,));fmt=meta["format_key"]
            conn.execute(self._sql("""UPDATE matches SET match_status='skipped',played_at=?,home_score=NULL,away_score=NULL,
                home_penalties=NULL,away_penalties=NULL,winner_player_id=NULL WHERE tournament_id=? AND match_no=?"""),(now_iso(),tid,int(match_no)))
            self._resolve_all_conn(conn,tid,fmt)

    def save_result(self, tid: str, match_no: int, hs: int, ass: int, hp: int | None = None, ap: int | None = None, scorers: dict | None = None, events: list[dict] | None = None) -> None:
        with self.connect() as conn:
            m=self._fetchone(conn,"SELECT * FROM matches WHERE tournament_id=? AND match_no=?",(tid,match_no))
            if not m or not m.get("home_player_id") or not m.get("away_player_id"): raise ValueError("Ten mecz nie ma jeszcze ustalonych graczy.")
            if hs<0 or ass<0: raise ValueError("Wynik nie może być ujemny.")
            meta=self._fetchone(conn,"SELECT format_key FROM flex_tournament_meta WHERE tournament_id=?",(tid,)); fmt=meta["format_key"]
            if fmt in ("double4","double5","double6","double7","double8") and m["stage"]=="FINAL" and hs<1:
                raise ValueError("Zwycięzca Winners Bracket zaczyna finał od 1:0.")
            knockout = m["stage"] not in ("GROUP","LEAGUE")
            if knockout and hs==ass and (hp is None or ap is None or hp==ap): raise ValueError("W fazie pucharowej remis wymaga karnych.")
            winner=winner_from_result(hs,ass,m["home_player_id"],m["away_player_id"],hp,ap)
            # A red-card/injury absence lasts for exactly the player's next actually
            # played match, regardless of numeric match_no or deferred schedule order.
            self._serve_active_absences_conn(conn,tid,int(match_no),[str(m["home_player_id"]),str(m["away_player_id"])])
            if events is not None:
                teams=self._fetchone(conn,"""SELECT htp.team AS home_team,atp.team AS away_team
                    FROM matches mm
                    LEFT JOIN tournament_players htp ON htp.tournament_id=mm.tournament_id AND htp.player_id=mm.home_player_id
                    LEFT JOIN tournament_players atp ON atp.tournament_id=mm.tournament_id AND atp.player_id=mm.away_player_id
                    WHERE mm.tournament_id=? AND mm.match_no=?""",(tid,match_no)) or {}
                self._save_match_events_conn(conn,tid,match_no,events)
                self._sync_absences_from_events_conn(conn,tid,match_no,events)
                scorers=self._aggregate_scorers_from_events(events,str(m["home_player_id"]),str(m["away_player_id"]),
                                                            str(teams.get("home_team") or ""),str(teams.get("away_team") or ""))
            self._save_scorers_conn(conn,tid,match_no,hs,ass,scorers)
            conn.execute(self._sql("UPDATE matches SET home_score=?,away_score=?,home_penalties=?,away_penalties=?,winner_player_id=?,played_at=?,match_status='played' WHERE tournament_id=? AND match_no=?"),(hs,ass,hp,ap,winner,now_iso(),tid,match_no))
            if fmt=="double7": self._prepare_double7_pairing_conn(conn,tid)
            if fmt in ("groups6","groups6_full","groups7","groups7_sf","groups8_sf","groups8_barrage"): self._prepare_group_playoffs_conn(conn,tid)
            self._resolve_all_conn(conn,tid,fmt)
            self._maybe_finish_conn(conn,tid,fmt)

    def _maybe_finish_conn(self, conn, tid: str, fmt: str) -> None:
        rows=self._fetchall(conn,"SELECT * FROM matches WHERE tournament_id=? ORDER BY match_no",(tid,)); mm={int(m["match_no"]):m for m in rows}
        champion=None
        if fmt=="duel1v1": champion=mm[1].get("winner_player_id")
        elif fmt=="league3_final": champion=mm[4].get("winner_player_id")
        elif fmt=="league4_final": champion=mm[7].get("winner_player_id")
        elif fmt=="double4": champion=mm[6].get("winner_player_id")
        elif fmt=="league5_final": champion=mm[11].get("winner_player_id")
        elif fmt=="groups6": champion=mm[9].get("winner_player_id")
        elif fmt=="groups6_full": champion=mm[11].get("winner_player_id")
        elif fmt=="double6": champion=mm[10].get("winner_player_id")
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
            last=self._fetchone(conn,"""SELECT * FROM matches WHERE tournament_id=? AND (home_score IS NOT NULL OR match_status='skipped')
                ORDER BY played_at DESC,match_no DESC LIMIT 1""",(tid,))
            if not last:return None
            no=int(last["match_no"])
            conn.execute(self._sql("DELETE FROM match_scorers WHERE tournament_id=? AND match_no=?"),(tid,no))
            # Remove sanctions created by the undone match and restore sanctions that
            # had just been served in it. This makes Undo fully reversible.
            conn.execute(self._sql("DELETE FROM tournament_absences WHERE tournament_id=? AND source_match_no=?"),(tid,no))
            conn.execute(self._sql("UPDATE tournament_absences SET served_match_no=NULL,served_at=NULL WHERE tournament_id=? AND served_match_no=?"),(tid,no))
            conn.execute(self._sql("DELETE FROM match_events WHERE tournament_id=? AND match_no=?"),(tid,no))
            conn.execute(self._sql("UPDATE matches SET home_score=NULL,away_score=NULL,home_penalties=NULL,away_penalties=NULL,winner_player_id=NULL,played_at=NULL,match_status='pending' WHERE tournament_id=? AND match_no=?"),(tid,no))
            # Rebuild participants only for genuinely pending games. Skipped league matches stay terminal.
            conn.execute(self._sql("UPDATE matches SET home_player_id=NULL,away_player_id=NULL WHERE tournament_id=? AND home_score IS NULL AND COALESCE(match_status,'pending')='pending'"),(tid,))
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
            if fmt in ("league3_final", "league4_final", "league5_final"): return {"L":self._table_from_conn(conn,tid,"L")}
            if fmt in ("groups6", "groups6_full", "groups7", "groups7_sf", "groups8_sf", "groups8_barrage"): return {"A":self._table_from_conn(conn,tid,"A"),"B":self._table_from_conn(conn,tid,"B")}
            return {}

    def abandon_tournament(self, tid: str) -> dict:
        """Close an official tournament early without deleting already played matches.

        The event remains official and visible in history, but has no champion, podium or
        settlement. Played matches/scorers stay available to match-based statistics,
        Awards, team/scorer stats, H2H, badges and global match/goal milestones.
        """
        with self.connect() as conn:
            t=self._fetchone(conn,"SELECT id,status,is_test FROM tournaments WHERE id=?",(tid,))
            if not t: raise ValueError("Nie znaleziono turnieju.")
            if str(t.get("status") or "")!="active": raise ValueError("Tylko trwający turniej można zakończyć jako niedokończony.")
            if int(t.get("is_test") or 0): raise ValueError("Turniej testowy można po prostu zresetować.")
            meta=self._fetchone(conn,"SELECT format_key FROM flex_tournament_meta WHERE tournament_id=?",(tid,))
            if not meta or str(meta.get("format_key") or "")=="duel1v1":
                raise ValueError("Mecz 1 vs 1 musi zostać normalnie zakończony wynikiem.")
            played=self._fetchone(conn,"SELECT COUNT(*) AS n FROM matches WHERE tournament_id=? AND home_score IS NOT NULL",(tid,))
            played_n=int((played or {}).get("n") or 0)
            if played_n<=0:
                raise ValueError("Nie rozegrano jeszcze żadnego meczu. Jeśli chcesz zrezygnować z turnieju, użyj resetu.")
            total=self._fetchone(conn,"SELECT COUNT(*) AS n FROM matches WHERE tournament_id=?",(tid,))
            total_n=int((total or {}).get("n") or 0)
            closed_at=now_iso()
            conn.execute(self._sql("UPDATE tournaments SET status='abandoned',phase='abandoned',champion_player_id=NULL,completed_at=? WHERE id=?"),(closed_at,tid))
            if self._setting_get_conn(conn,CURRENT_KEY)==tid:
                self._setting_set_conn(conn,CURRENT_KEY,"")
            return {"id":tid,"played":played_n,"total":total_n,"closed_at":closed_at}

    def reset_current(self, tid: str) -> None:
        with self.connect() as conn:
            conn.execute(self._sql("DELETE FROM flex_match_sources WHERE tournament_id=?"),(tid,)); conn.execute(self._sql("DELETE FROM match_scorers WHERE tournament_id=?"),(tid,)); conn.execute(self._sql("DELETE FROM tournament_absences WHERE tournament_id=?"),(tid,)); conn.execute(self._sql("DELETE FROM match_events WHERE tournament_id=?"),(tid,)); conn.execute(self._sql("DELETE FROM matches WHERE tournament_id=?"),(tid,)); conn.execute(self._sql("DELETE FROM tournament_players WHERE tournament_id=?"),(tid,)); conn.execute(self._sql("DELETE FROM flex_tournament_meta WHERE tournament_id=?"),(tid,)); conn.execute(self._sql("DELETE FROM tournaments WHERE id=?"),(tid,)); self._setting_set_conn(conn,CURRENT_KEY,"")

    def start_new(self) -> None:
        with self.connect() as conn: self._setting_set_conn(conn,CURRENT_KEY,"")

    def clear_flex_history(self) -> None:
        with self.connect() as conn:
            ids=[r["tournament_id"] for r in self._fetchall(conn,"SELECT tournament_id FROM flex_tournament_meta")]
            for tid in ids:
                conn.execute(self._sql("DELETE FROM flex_match_sources WHERE tournament_id=?"),(tid,)); conn.execute(self._sql("DELETE FROM match_scorers WHERE tournament_id=?"),(tid,)); conn.execute(self._sql("DELETE FROM tournament_absences WHERE tournament_id=?"),(tid,)); conn.execute(self._sql("DELETE FROM match_events WHERE tournament_id=?"),(tid,)); conn.execute(self._sql("DELETE FROM matches WHERE tournament_id=?"),(tid,)); conn.execute(self._sql("DELETE FROM tournament_players WHERE tournament_id=?"),(tid,)); conn.execute(self._sql("DELETE FROM tournaments WHERE id=?"),(tid,))
            conn.execute("DELETE FROM flex_tournament_meta")
            self._setting_set_conn(conn,CURRENT_KEY,"")

    def _finance_ledger_conn(self, conn) -> tuple[list[dict],dict[str,str],int]:
        """Replay official cash events chronologically, including tournament jackpots.

        Old tournaments without cash_player_ids are treated as if everybody played for
        money, preserving v1.7.x behaviour. 1v1 events never consume or create the
        tournament jackpot; if either duelist opted out their stored stake is zero.
        """
        events=self._fetchall(conn,"""
            SELECT t.id,t.created_at,t.completed_at,t.champion_player_id,fm.player_count,fm.format_key,fm.extra_json
            FROM tournaments t JOIN flex_tournament_meta fm ON fm.tournament_id=t.id
            WHERE t.status='completed' AND t.is_test=0
            ORDER BY COALESCE(t.completed_at,t.created_at),t.created_at,t.id
        """)
        parts=self._fetchall(conn,"""SELECT tp.tournament_id,tp.player_id,p.name
            FROM tournament_players tp JOIN players p ON p.id=tp.player_id
            JOIN tournaments t ON t.id=tp.tournament_id
            WHERE t.status='completed' AND t.is_test=0""")
        by_tid=defaultdict(list); names={}
        for r in parts:
            tid=str(r["tournament_id"]);pid=str(r["player_id"]);name=str(r.get("name") or "?")
            by_tid[tid].append(pid);names[pid]=name
        ledger=[];jackpot=0;carry_sources=[]
        for r in events:
            tid=str(r["id"]);pids=list(dict.fromkeys(by_tid.get(tid,[])));champ=str(r.get("champion_player_id") or "")
            try: extra=json.loads(r.get("extra_json") or "{}")
            except Exception: extra={}
            stake=self._stake_cents(extra.get("stake_per_player") or 0);fmt=str(r.get("format_key") or "")
            if "cash_player_ids" in extra:
                cash=[str(x) for x in (extra.get("cash_player_ids") or []) if str(x) in pids]
            else:
                cash=pids.copy()
            entry={
                "id":tid,"created_at":r.get("created_at"),"completed_at":r.get("completed_at"),
                "champion_player_id":champ,"champion_name":names.get(champ,"?"),"player_count":int(r.get("player_count") or len(pids)),
                "format_key":fmt,"stake_cents":stake,"cash_player_ids":cash,"cash_count":len(cash),
                "settled":bool(extra.get("cash_settled") or False),"settled_at":extra.get("cash_settled_at"),
                "contribution_cents":0,"jackpot_in_cents":0,"jackpot_out_cents":jackpot,"prize_cents":0,
                "prize_winner_player_id":None,"prize_winner_name":None,"jackpot_source_ids":[],
            }
            if fmt=="duel1v1":
                if stake>0 and len(cash)==2 and champ in cash:
                    entry["contribution_cents"]=stake*2
                    entry["prize_cents"]=stake*2
                    entry["prize_winner_player_id"]=champ;entry["prize_winner_name"]=names.get(champ,"?")
                entry["jackpot_out_cents"]=jackpot
                ledger.append(entry);continue
            if stake>0 and len(cash)>=2:
                contribution=stake*len(cash);entry["contribution_cents"]=contribution;entry["jackpot_in_cents"]=jackpot
                total=contribution+jackpot
                if champ in cash:
                    entry["prize_cents"]=total;entry["prize_winner_player_id"]=champ;entry["prize_winner_name"]=names.get(champ,"?")
                    entry["jackpot_source_ids"]=carry_sources.copy()
                    jackpot=0;carry_sources=[]
                else:
                    jackpot=total;carry_sources=carry_sources+[tid]
                entry["jackpot_out_cents"]=jackpot
            ledger.append(entry)
        return ledger,names,jackpot

    def finance_event(self, tid: str) -> dict | None:
        with self.connect() as conn:
            ledger,_names,_jackpot=self._finance_ledger_conn(conn)
        return next((dict(x) for x in ledger if str(x.get("id"))==str(tid)),None)

    def current_jackpot_cents(self) -> int:
        with self.connect() as conn:
            _ledger,_names,jackpot=self._finance_ledger_conn(conn)
            return int(jackpot)

    def settlement_tournaments(self, limit: int = 100) -> list[dict]:
        limit=max(1,min(200,int(limit or 100)))
        with self.connect() as conn:
            ledger,_names,_jackpot=self._finance_ledger_conn(conn)
            official=self._fetchall(conn,"""SELECT t.id FROM tournaments t JOIN flex_tournament_meta fm ON fm.tournament_id=t.id
                WHERE t.status IN ('completed','abandoned') AND t.is_test=0 AND fm.format_key<>'duel1v1'
                ORDER BY COALESCE(t.completed_at,t.created_at),t.created_at,t.id""")
            numbers={str(r["id"]):i+1 for i,r in enumerate(official)}
        rows=list(reversed(ledger))[:limit]
        out=[]
        for r in rows:
            item=dict(r);item["official_no"]=numbers.get(str(r["id"]));item["stake_per_player"]=int(r.get("stake_cents") or 0)/100
            out.append(item)
        return out

    def financial_ranking(self) -> list[dict]:
        with self.connect() as conn:
            ledger,names,_jackpot=self._finance_ledger_conn(conn)
        stats={}
        for e in ledger:
            stake=int(e.get("stake_cents") or 0)
            if stake<=0: continue
            for pid in e.get("cash_player_ids") or []:
                row=stats.setdefault(pid,{"player_id":pid,"name":names.get(pid,"?"),"paid_cents":0,"won_cents":0,"paid_tournaments":0,"wins":0})
                row["paid_cents"]+=stake;row["paid_tournaments"]+=1
            winner=e.get("prize_winner_player_id");prize=int(e.get("prize_cents") or 0)
            if winner and prize>0:
                row=stats.setdefault(winner,{"player_id":winner,"name":names.get(winner,"?"),"paid_cents":0,"won_cents":0,"paid_tournaments":0,"wins":0})
                row["won_cents"]+=prize;row["wins"]+=1
        out=[]
        for row in stats.values():
            item=dict(row);item["balance_cents"]=int(item["won_cents"])-int(item["paid_cents"]);out.append(item)
        out.sort(key=lambda x:(-int(x["balance_cents"]),-int(x["won_cents"]),str(x["name"])))
        return out

    def settlement_summary(self, tournament_ids: list[str]) -> dict:
        requested=list(dict.fromkeys(str(x) for x in (tournament_ids or []) if x))
        if not requested:return {"tournaments":[],"balances":[],"transfers":[],"total_pot_cents":0,"pending_jackpot_cents":0}
        with self.connect() as conn:
            ledger,names,current_jackpot=self._finance_ledger_conn(conn)
        by={str(e["id"]):e for e in ledger};selected=set(x for x in requested if x in by)
        # If a selected tournament receives a carried jackpot, include the source events
        # automatically so debtors and the final creditor balance to zero.
        changed=True
        while changed:
            changed=False
            for tid in list(selected):
                e=by.get(tid) or {}
                for src in e.get("jackpot_source_ids") or []:
                    if src not in selected:
                        selected.add(src);changed=True
        ordered=[e for e in ledger if str(e["id"]) in selected]
        balances=defaultdict(int);total_contrib=0;pending=0
        for e in ordered:
            stake=int(e.get("stake_cents") or 0)
            if stake<=0:continue
            for pid in e.get("cash_player_ids") or []:balances[pid]-=stake
            total_contrib+=int(e.get("contribution_cents") or 0)
            winner=e.get("prize_winner_player_id");prize=int(e.get("prize_cents") or 0)
            if winner and prize>0:balances[str(winner)]+=prize
        # A selected unresolved rollover legitimately has no creditor yet. Surface it
        # instead of creating impossible transfers.
        if ordered:
            latest=ordered[-1]
            if int(latest.get("jackpot_out_cents") or 0)>0 and not latest.get("prize_winner_player_id"):
                pending=int(latest.get("jackpot_out_cents") or 0)
        debtors=[[pid,-amount] for pid,amount in balances.items() if amount<0]
        creditors=[[pid,amount] for pid,amount in balances.items() if amount>0]
        debtors.sort(key=lambda x:(-x[1],names.get(x[0],x[0])));creditors.sort(key=lambda x:(-x[1],names.get(x[0],x[0])))
        transfers=[];i=j=0
        while i<len(debtors) and j<len(creditors):
            amount=min(debtors[i][1],creditors[j][1])
            if amount>0:transfers.append({"from_player_id":debtors[i][0],"from_name":names.get(debtors[i][0],"?"),"to_player_id":creditors[j][0],"to_name":names.get(creditors[j][0],"?"),"amount_cents":amount})
            debtors[i][1]-=amount;creditors[j][1]-=amount
            if debtors[i][1]==0:i+=1
            if creditors[j][1]==0:j+=1
        balance_rows=[{"player_id":pid,"name":names.get(pid,"?"),"balance_cents":amount} for pid,amount in balances.items()]
        balance_rows.sort(key=lambda x:(-x["balance_cents"],x["name"]))
        return {"tournaments":ordered,"balances":balance_rows,"transfers":transfers,"total_pot_cents":total_contrib,
                "pending_jackpot_cents":pending,"current_jackpot_cents":current_jackpot,"expanded_ids":[e["id"] for e in ordered]}

    def completed_tournaments(self, include_tests: bool = False, limit: int = 200) -> list[dict]:
        """Archived FIFA Night events for the read-only history browser.

        Besides normally completed events this includes official tournaments closed early
        with status ``abandoned``. Official numbering counts every official non-duel FIFA
        Night event, so an unfinished night keeps its historical number.
        """
        limit=max(1,min(500,int(limit or 200)))
        with self.connect() as conn:
            official=self._fetchall(conn,"""SELECT t.id FROM tournaments t JOIN flex_tournament_meta fm ON fm.tournament_id=t.id
                WHERE t.status IN ('completed','abandoned') AND t.is_test=0 AND fm.format_key<>'duel1v1'
                ORDER BY COALESCE(t.completed_at,t.created_at),t.created_at,t.id""")
            numbers={str(r["id"]):i+1 for i,r in enumerate(official)}
            where="WHERE t.status IN ('completed','abandoned')" if include_tests else "WHERE t.status IN ('completed','abandoned') AND t.is_test=0"
            rows=self._fetchall(conn,f"""SELECT t.id,t.status,t.created_at,t.completed_at,t.is_test,t.champion_player_id,p.name champion_name,
                    fm.player_count,fm.format_key
                FROM tournaments t
                JOIN flex_tournament_meta fm ON fm.tournament_id=t.id
                LEFT JOIN players p ON p.id=t.champion_player_id
                {where}
                ORDER BY COALESCE(t.completed_at,t.created_at) DESC,t.created_at DESC,t.id DESC
                LIMIT {limit}""")
        out=[]
        for r in rows:
            item=dict(r);item["official_no"]=numbers.get(str(r.get("id")));out.append(item)
        return out

    def last_completed_tournament(self) -> dict | None:
        with self.connect() as conn:
            t=self._fetchone(conn,"""SELECT t.id,t.status,t.created_at,t.completed_at,t.champion_player_id,p.name champion_name
                FROM tournaments t LEFT JOIN players p ON p.id=t.champion_player_id
                WHERE t.status IN ('completed','abandoned') AND t.is_test=0
                  AND EXISTS (SELECT 1 FROM flex_tournament_meta fm WHERE fm.tournament_id=t.id AND fm.format_key<>'duel1v1')
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
        conn.execute(self._sql("DELETE FROM tournament_absences WHERE tournament_id=?"),(tid,))
        conn.execute(self._sql("DELETE FROM match_events WHERE tournament_id=?"),(tid,))
        conn.execute(self._sql("DELETE FROM flex_tournament_meta WHERE tournament_id=?"),(tid,))
        conn.execute(self._sql("DELETE FROM matches WHERE tournament_id=?"),(tid,))
        conn.execute(self._sql("DELETE FROM tournament_players WHERE tournament_id=?"),(tid,))
        conn.execute(self._sql("DELETE FROM tournaments WHERE id=?"),(tid,))
        if self._setting_get_conn(conn,CURRENT_KEY)==tid: self._setting_set_conn(conn,CURRENT_KEY,"")

    def delete_last_completed_tournament(self) -> dict | None:
        with self.connect() as conn:
            t=self._fetchone(conn,"""SELECT t.id,t.status,t.created_at,t.completed_at,t.champion_player_id,p.name champion_name
                FROM tournaments t LEFT JOIN players p ON p.id=t.champion_player_id
                WHERE t.status IN ('completed','abandoned') AND t.is_test=0
                  AND EXISTS (SELECT 1 FROM flex_tournament_meta fm WHERE fm.tournament_id=t.id AND fm.format_key<>'duel1v1')
                ORDER BY COALESCE(t.completed_at,t.created_at) DESC LIMIT 1""")
            if not t: return None
            cnt=self._fetchone(conn,"SELECT COUNT(*) AS c FROM tournament_players WHERE tournament_id=?",(t["id"],)); t["player_count"]=int(cnt["c"]) if cnt else 0
            self._delete_tournament_conn(conn,t["id"]); return t

    def delete_archived_tournament(self, tid: str) -> dict:
        """Delete one selected archived tournament (or a completed 1 VS 1 match).

        Deletion always requires an explicit admin confirmation in the UI/API. We intentionally do not support deleting one match
        from the middle of a completed multi-match tournament because it would break
        bracket/standings/champion consistency; such corrections should be made before
        the tournament is closed or by deleting the whole archived tournament.
        """
        tid=str(tid or "").strip()
        if not tid: raise ValueError("Brak turnieju do usunięcia.")
        with self.connect() as conn:
            t=self._fetchone(conn,"SELECT id,status,is_test,created_at,completed_at FROM tournaments WHERE id=?",(tid,))
            if not t: raise ValueError("Nie znaleziono turnieju w historii.")
            if str(t.get("status") or "") not in ("completed","abandoned"):
                raise ValueError("Można usuwać tylko zamknięte pozycje z Historii.")
            meta=self._fetchone(conn,"SELECT format_key,player_count FROM flex_tournament_meta WHERE tournament_id=?",(tid,)) or {}
            out=dict(t);out.update(meta)
            self._delete_tournament_conn(conn,tid)
            return out

    def clear_all_history(self) -> None:
        with self.connect() as conn:
            conn.execute("DELETE FROM flex_match_sources")
            conn.execute("DELETE FROM match_scorers")
            conn.execute("DELETE FROM tournament_absences")
            conn.execute("DELETE FROM match_events")
            conn.execute("DELETE FROM flex_tournament_meta")
            conn.execute("DELETE FROM matches")
            conn.execute("DELETE FROM tournament_players")
            conn.execute("DELETE FROM tournaments")
            # Keep players and remembered lineups. Only live tournament pointers are cleared.
            self._setting_set_conn(conn,CURRENT_KEY,"")

    def team_stats(self) -> list[dict]:
        """Statystyki klubów z rozegranych oficjalnych meczów (Classic + Flex).

        Mecze z oficjalnych turniejów zamkniętych jako niedokończone liczą się do
        bilansu drużyn, ale tytuły pochodzą wyłącznie z ukończonych turniejów.
        """
        with self.connect() as conn:
            matches=self._official_matches_conn(conn)
            champions=self._fetchall(conn,"""SELECT tp.team,tp.player_id,p.name
                FROM tournaments t
                JOIN flex_tournament_meta fm ON fm.tournament_id=t.id
                JOIN tournament_players tp ON tp.tournament_id=t.id AND tp.player_id=t.champion_player_id
                JOIN players p ON p.id=tp.player_id
                WHERE t.status='completed' AND t.is_test=0 AND fm.format_key<>'duel1v1' AND tp.team<>''""")
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


    def player_award_wins(self, player_id: str) -> list[dict]:
        """Organizer-selected individual FIFA Night Awards belonging to one participant."""
        pid=str(player_id or "")
        if not pid:return []
        titles={
            "player_year":"Gracz Roku","offensive":"Ofensywny Gracz Roku","defense":"Beton Roku",
            "player_scorers":"Król Strzelców FIFA Night","clutch":"Clutch Player Roku",
            "sharpest":"Najostrzejszy Gracz","late_king":"Król Końcówek","comeback_king":"Comeback King","fair_play":"Fair Play",
            "regular":"Najbardziej Regularny","progress":"Największy Progres","spectacle":"Najbardziej Widowiskowy Gracz",
            "penalties":"Król Karnych","duel":"Król 1 vs 1","universal":"Najbardziej Uniwersalny Gracz",
            "wildcards":"Król Wild Cardów","debut":"Debiut Roku","outsider":"Najlepszy spoza dominatorów",
            "finance":"Rekin Finansowy",
        }
        direct=set(titles)-{"player_scorers"}
        with self.connect() as conn:
            rows=self._fetchall(conn,"SELECT key,value FROM app_settings WHERE key LIKE ?",("flex_award_selections_%",))
        out=[]
        for r in rows:
            key=str(r.get("key") or "")
            try:year=int(key.rsplit("_",1)[1])
            except Exception:continue
            try:data=json.loads(r.get("value") or "{}")
            except Exception:continue
            for cat,sel in (data or {}).items():
                cat=str(cat);sel=sel or {};cid=str(sel.get("id") or "")
                belongs=(cat in direct and cid==pid) or (cat=="player_scorers" and cid.split("|",1)[0]==pid)
                if belongs:
                    out.append({"year":year,"key":cat,"title":titles.get(cat,cat),"name":str(sel.get("name") or ""),"selected_at":sel.get("selected_at")})
        out.sort(key=lambda x:(x["year"],x["title"]))
        return out

    def player_trophy_case(self, player_id: str) -> dict:
        """Badges, selected annual awards and global milestone moments connected with a player."""
        pid=str(player_id or "")
        if not pid:return {"badges":[],"badge_count":0,"badge_total":0,"awards":[],"milestones":[]}
        ach=self.achievement_center();pa=next((x for x in ach.get("players",[]) if str(x.get("player_id"))==pid),None) or {}
        with self.connect() as conn:
            prow=self._fetchone(conn,"SELECT name FROM players WHERE id=?",(pid,))
        pname=str((prow or {}).get("name") or "")
        milestones=[]
        for x in self.global_milestones().get("timeline",[]):
            detail=str(x.get("detail") or "")
            resolution=x.get("scorer_resolution") or {}
            # Timeline details are rebuilt from current player names, so historical renames remain visible.
            text_hit=bool(pname and pname.casefold() in detail.casefold())
            scorer_hit=str(resolution.get("player_id") or "")==pid
            if text_hit or scorer_hit:
                milestones.append(x)
        milestones.sort(key=lambda x:x.get("earned_at") or "",reverse=True)
        return {
            "badges":pa.get("unlocked") or [],
            "badge_count":int(pa.get("count") or 0),
            "badge_total":int(pa.get("total") or len(ach.get("catalog") or [])),
            "awards":self.player_award_wins(pid),
            "milestones":milestones[:12],
        }

    # ------------------------------------------------------------------
    # Achievements & global FIFA Night milestones (v1.8.0 hotfix 18)
    # ------------------------------------------------------------------
    @staticmethod
    def _event_when_match(m: dict) -> str:
        return str(m.get("played_at") or m.get("completed_at") or m.get("created_at") or "")

    @staticmethod
    def _achievement_catalog() -> list[dict]:
        return [
            {"key":"first_blood","icon":"🥇","name":"Pierwsza krew","desc":"Pierwsze oficjalne zwycięstwo."},
            {"key":"first_title","icon":"🏆","name":"Pierwszy skalp","desc":"Pierwszy wygrany turniej FIFA Night."},
            {"key":"wins_10","icon":"🔟","name":"10 zwycięstw","desc":"10 oficjalnych zwycięstw."},
            {"key":"wins_50","icon":"5️⃣0️⃣","name":"50 zwycięstw","desc":"50 oficjalnych zwycięstw."},
            {"key":"matches_100","icon":"💯","name":"100 meczów","desc":"100 oficjalnych meczów."},
            {"key":"goals_100","icon":"⚽","name":"100 goli","desc":"100 strzelonych goli w oficjalnych meczach."},
            {"key":"titles_5","icon":"👑","name":"Pięciokrotny mistrz","desc":"5 wygranych turniejów FIFA Night."},
            {"key":"on_fire","icon":"🔥","name":"On Fire","desc":"5 oficjalnych zwycięstw z rzędu."},
            {"key":"unstoppable","icon":"🚀","name":"Nie do zatrzymania","desc":"10 oficjalnych zwycięstw z rzędu."},
            {"key":"wall","icon":"🧱","name":"Mur","desc":"3 czyste konta z rzędu."},
            {"key":"massacre","icon":"💥","name":"Masakra","desc":"Zwycięstwo różnicą co najmniej 5 goli."},
            {"key":"thriller","icon":"🎬","name":"Thriller","desc":"Wygrany mecz jedną bramką, w którym padło co najmniej 7 goli."},
            {"key":"ice_cold","icon":"🥶","name":"Ice Cold","desc":"Wygrana seria rzutów karnych."},
            {"key":"many_clubs","icon":"🔄","name":"Człowiek wielu klubów","desc":"Zwycięstwo oficjalnego meczu pięcioma różnymi drużynami."},
            {"key":"wild_one","icon":"🎲","name":"Wild One","desc":"Wygrany turniej drużyną z Wild Carda."},
            {"key":"perfect_night","icon":"💯","name":"Perfect Night","desc":"Wygraj FIFA Night, wygrywając każdy swój mecz w regulaminowych 90 minutach — bez remisu, dogrywki i serii karnych."},
            {"key":"unkillable","icon":"🔥","name":"Nie do zabicia","desc":"Wygraj mecz po tym, jak przegrywałeś co najmniej 3 golami."},
            {"key":"ten_men","icon":"🟥","name":"W dziesiątkę raźniej","desc":"Wygraj mecz mimo czerwonej kartki dla swojej drużyny."},
            {"key":"penalty_executioner","icon":"🎯","name":"Egzekutor z wapna","desc":"Zdobądź 10 goli z rzutów karnych w trakcie meczu."},
            {"key":"after_hours","icon":"➕","name":"Po godzinach","desc":"Zdobądź gola na wagę zwycięstwa w dogrywce."},
            {"key":"hat_trick_express","icon":"🎩","name":"Hat-trick Express","desc":"Niech jeden piłkarz Twojej drużyny zdobędzie hat-tricka w ciągu maksymalnie 15 minut."},
            {"key":"butcher","icon":"🪓","name":"Rzeźnik","desc":"Uzbieraj 25 punktów dyscyplinarnych w szczegółowo śledzonych meczach (żółta = 1, czerwona = 3)."},
            {"key":"joker","icon":"🃏","name":"Joker","desc":"Zmiennik zdobywa gola na wagę zwycięstwa po wejściu z ławki."},
            {"key":"from_the_dead","icon":"🐦‍🔥","name":"Powrót zza grobu","desc":"Wygrany Double Elimination po wcześniejszym spadku do Losers Bracket."},
            {"key":"shark","icon":"🦈","name":"Rekin","desc":"Historyczny bilans finansowy osiąga co najmniej +250 zł."},
            {"key":"sponsor","icon":"🤡","name":"Sponsor imprezy","desc":"Historyczny bilans finansowy spada do -250 zł lub niżej."},
            {"key":"back_to_back","icon":"🏆","name":"Back to Back","desc":"Dwa tytuły FIFA Night z rzędu."},
            {"key":"steel_nerves","icon":"🧊","name":"Nerwy ze stali","desc":"Wygrany finał FIFA Night po rzutach karnych."},
            {"key":"executioner","icon":"⚔️","name":"Egzekutor","desc":"Trzy wygrane mecze eliminacyjne w jednym turnieju."},
            {"key":"revenge","icon":"😈","name":"Zemsta najlepiej smakuje","desc":"Po wcześniejszej porażce z rywalem w tym samym turnieju pokonaj go później w meczu, po którym odpada lub w finale."},
            {"key":"fortress","icon":"🏰","name":"Twierdza","desc":"Wygraj turniej bez straty ani jednego gola."},
            {"key":"on_the_edge","icon":"🫀","name":"Na styku","desc":"Wygraj trzy mecze różnicą jednej bramki w jednym turnieju."},
            {"key":"champion_hunter","icon":"🏹","name":"Łowca mistrza","desc":"Pokonaj obrońcę tytułu w następnym FIFA Night."},
            {"key":"last_ticket","icon":"🎟️","name":"Rzutem na taśmę","desc":"Wyjdź z grupy z ostatniego premiowanego miejsca i wygraj cały turniej."},
            {"key":"rebirth","icon":"♻️","name":"Odrodzenie","desc":"Przegraj mecz w grupie lub lidze, a mimo to wygraj cały turniej."},
        ]

    def achievement_center(self) -> dict:
        """Return player badges with the historical moment each badge was first earned.

        General match-based badges include every official match, including 1v1. Tournament
        badges deliberately ignore 1v1. Once a historical sequence crosses a condition,
        the first crossing is reported even if the player's current form/balance later changes.
        """
        catalog=self._achievement_catalog()
        with self.connect() as conn:
            matches=self._official_matches_conn(conn)
            names={str(r["id"]):str(r["name"]) for r in self._fetchall(conn,"SELECT id,name FROM players")}
            events=self._fetchall(conn,"""SELECT t.id,t.status,t.champion_player_id,t.completed_at,t.created_at,fm.format_key
                FROM tournaments t JOIN flex_tournament_meta fm ON fm.tournament_id=t.id
                WHERE t.status IN ('completed','abandoned') AND t.is_test=0 AND fm.format_key<>'duel1v1'
                ORDER BY COALESCE(t.completed_at,t.created_at),t.created_at,t.id""")
            tps=self._fetchall(conn,"""SELECT tp.tournament_id,tp.player_id,tp.team,tp.group_name,tp.tie_order
                FROM tournament_players tp JOIN tournaments t ON t.id=tp.tournament_id
                WHERE t.status IN ('completed','abandoned') AND t.is_test=0""")
            ledger,_finance_names,_jackpot=self._finance_ledger_conn(conn)
            detailed_events=self._fetchall(conn,"""SELECT me.tournament_id,me.match_no,me.event_order,me.event_type,
                    me.minute,me.stoppage,me.minute_label,me.actor_player_id,me.credited_player_id,
                    me.footballer_name,me.normalized_footballer,me.related_footballer_name,me.synthetic_de,me.confidence
                FROM match_events me
                JOIN tournaments t ON t.id=me.tournament_id
                WHERE t.is_test=0
                ORDER BY me.tournament_id,me.match_no,me.event_order,me.id""")
        detailed_by_match=defaultdict(list)
        for e in detailed_events:
            detailed_by_match[(str(e.get("tournament_id") or ""),int(e.get("match_no") or 0))].append(e)
        team_by={(str(r["tournament_id"]),str(r["player_id"])):str(r.get("team") or "") for r in tps}
        group_by={(str(r["tournament_id"]),str(r["player_id"])):str(r.get("group_name") or "") for r in tps}
        group_players=defaultdict(list);tie_by={}
        for r in tps:
            tid0,pid0,grp0=str(r["tournament_id"]),str(r["player_id"]),str(r.get("group_name") or "")
            tie_by[(tid0,pid0)]=int(r.get("tie_order") or 0)
            if grp0:group_players[(tid0,grp0)].append(pid0)
        fixed={self._norm_team_name(x) for x in FIXED_TEAMS}
        tournament_no={str(e["id"]):i+1 for i,e in enumerate(events)}
        event_by={str(e["id"]):e for e in events}

        unlocked=defaultdict(dict)
        progress=defaultdict(lambda:{"wins":0,"matches":0,"goals":0,"titles":0,"max_win_streak":0,"max_clean_streak":0,"pen_wins":0,"win_teams":set(),"max_margin":0,"balance_cents":0,"max_balance_cents":0,"min_balance_cents":0,"title_streak":0,"max_title_streak":0,"max_elim_wins_tournament":0,"max_close_wins_tournament":0,"penalty_goals":0,"discipline_points":0,"max_comeback_deficit":0})
        win_streak=defaultdict(int);clean_streak=defaultdict(int)

        def award(pid,key,when="",tid=None,match_no=None,detail=""):
            pid=str(pid or "")
            if not pid or key in unlocked[pid]: return
            unlocked[pid][key]={"key":key,"earned_at":str(when or ""),"tournament_id":str(tid) if tid else None,
                                "tournament_no":tournament_no.get(str(tid)) if tid else None,"match_no":int(match_no) if match_no is not None else None,
                                "detail":str(detail or "")}

        # Match achievements in true chronological order.
        for m in matches:
            tid=str(m.get("tournament_id") or "");no=int(m.get("match_no") or 0);when=self._event_when_match(m)
            hs,ass=int(m.get("home_score") or 0),int(m.get("away_score") or 0)
            fmt_here=str((event_by.get(tid) or {}).get("format_key") or "")
            wb_bonus=1 if fmt_here.startswith("double") and str(m.get("stage") or "")=="FINAL" else 0
            actual_hs=max(0,hs-wb_bonus)
            for pid,home in ((str(m.get("home_player_id") or ""),True),(str(m.get("away_player_id") or ""),False)):
                if not pid: continue
                pr=progress[pid];pr["matches"]+=1
                gf=(actual_hs if home else ass);ga=(ass if home else actual_hs);pr["goals"]+=gf
                if pr["matches"]==100: award(pid,"matches_100",when,tid,no,f"100. mecz: {m.get('home_name')} {hs}:{ass} {m.get('away_name')}")
                if pr["goals"]>=100 and "goals_100" not in unlocked[pid]: award(pid,"goals_100",when,tid,no,f"Próg 100 goli przekroczony w meczu {m.get('home_name')} {hs}:{ass} {m.get('away_name')}")
                result=self._result_for_player(m,pid)
                if result=="W":
                    pr["wins"]+=1;win_streak[pid]+=1;clean_streak[pid]=clean_streak[pid]+1 if ga==0 else 0
                    if pr["wins"]==1: award(pid,"first_blood",when,tid,no,f"{m.get('home_name')} {hs}:{ass} {m.get('away_name')}")
                    if pr["wins"]==10: award(pid,"wins_10",when,tid,no,"10. oficjalne zwycięstwo")
                    if pr["wins"]==50: award(pid,"wins_50",when,tid,no,"50. oficjalne zwycięstwo")
                    if win_streak[pid]>=5: award(pid,"on_fire",when,tid,no,"5 zwycięstw z rzędu")
                    if win_streak[pid]>=10: award(pid,"unstoppable",when,tid,no,"10 zwycięstw z rzędu")
                    margin=gf-ga;pr["max_margin"]=max(pr["max_margin"],margin)
                    if margin>=5: award(pid,"massacre",when,tid,no,f"Wygrana {gf}:{ga}")
                    if margin==1 and gf+ga>=7: award(pid,"thriller",when,tid,no,f"Wygrana {gf}:{ga}")
                    team=(m.get("home_team") if home else m.get("away_team")) or ""
                    if str(team).strip():
                        pr["win_teams"].add(self._norm_team_name(str(team)))
                        if len(pr["win_teams"])>=5: award(pid,"many_clubs",when,tid,no,"Wygrana pięcioma różnymi drużynami")
                else:
                    win_streak[pid]=0
                    clean_streak[pid]=clean_streak[pid]+1 if ga==0 else 0
                pr["max_win_streak"]=max(pr["max_win_streak"],win_streak[pid]);pr["max_clean_streak"]=max(pr["max_clean_streak"],clean_streak[pid])
                if clean_streak[pid]>=3: award(pid,"wall",when,tid,no,"3 czyste konta z rzędu")
                if result=="W" and m.get("home_penalties") is not None and m.get("away_penalties") is not None:
                    pr["pen_wins"]+=1;award(pid,"ice_cold",when,tid,no,f"Karne {m.get('home_penalties')}:{m.get('away_penalties')}")

            # New-era badges based on the confirmed EA FC event timeline. These are
            # never inferred for older/manual matches that have no detailed events.
            evs=list(detailed_by_match.get((tid,no),[]))
            if evs:
                evs.sort(key=lambda e:(int(e.get("event_order") or 10**9),int(e.get("minute") or 0),int(e.get("stoppage") or 0)))
                home_pid=str(m.get("home_player_id") or "");away_pid=str(m.get("away_player_id") or "")
                rh=self._result_for_player(m,home_pid) if home_pid else "D"
                winner=home_pid if rh=="W" else (away_pid if rh=="L" else "")

                # Cumulative event counters: penalty goals and discipline points.
                for e in evs:
                    et=str(e.get("event_type") or "")
                    actor=str(e.get("actor_player_id") or "")
                    credited=str(e.get("credited_player_id") or "")
                    synthetic=bool(int(e.get("synthetic_de") or 0))
                    if et=="penalty_goal" and credited and not synthetic:
                        progress[credited]["penalty_goals"]+=1
                        if progress[credited]["penalty_goals"]>=10:
                            award(credited,"penalty_executioner",when,tid,no,"10. gol z rzutu karnego w trakcie meczu")
                    if actor and et in {"yellow_card","red_card"}:
                        progress[actor]["discipline_points"] += 1 if et=="yellow_card" else 3
                        if progress[actor]["discipline_points"]>=25:
                            award(actor,"butcher",when,tid,no,f"25 pkt dyscyplinarnych (aktualnie {progress[actor]['discipline_points']})")

                # W dziesiątkę raźniej: a red card for the eventual match winner.
                if winner and any(str(e.get("event_type") or "")=="red_card" and str(e.get("actor_player_id") or "")==winner for e in evs):
                    award(winner,"ten_men",when,tid,no,"Zwycięstwo mimo czerwonej kartki")

                # Goal-sequence badges require a complete REAL goal timeline. The
                # synthetic +1 in a DE Grand Final is excluded from achievements.
                goal_types={"normal_goal","penalty_goal","own_goal"}
                real_goals=[e for e in evs if str(e.get("event_type") or "") in goal_types and not int(e.get("synthetic_de") or 0)]
                known_goals=[e for e in real_goals if str(e.get("credited_player_id") or "") in {home_pid,away_pid}]
                expected_h=actual_hs; expected_a=ass
                goals_complete=(len(real_goals)==len(known_goals)==expected_h+expected_a and
                                sum(1 for e in known_goals if str(e.get("credited_player_id") or "")==home_pid)==expected_h and
                                sum(1 for e in known_goals if str(e.get("credited_player_id") or "")==away_pid)==expected_a)
                if goals_complete:
                    # Replay from 0:0 and remember the largest deficit later overcome
                    # by the eventual real-score winner.
                    actual_winner=home_pid if expected_h>expected_a else (away_pid if expected_a>expected_h else "")
                    if actual_winner:
                        score={home_pid:0,away_pid:0};max_deficit=0
                        other=away_pid if actual_winner==home_pid else home_pid
                        for e in known_goals:
                            credited=str(e.get("credited_player_id") or "")
                            score[credited]+=1
                            max_deficit=max(max_deficit,score.get(other,0)-score.get(actual_winner,0))
                        progress[actual_winner]["max_comeback_deficit"]=max(progress[actual_winner]["max_comeback_deficit"],max_deficit)
                        if max_deficit>=3:
                            award(actual_winner,"unkillable",when,tid,no,f"Zwycięstwo po przegrywaniu {max_deficit} golami")

                        # The match-winning goal is the winner's (loser's final score + 1)th goal.
                        loser_final=expected_a if actual_winner==home_pid else expected_h
                        winner_goal_no=0;winning_goal=None
                        for e in known_goals:
                            if str(e.get("credited_player_id") or "")==actual_winner:
                                winner_goal_no+=1
                                if winner_goal_no==loser_final+1:
                                    winning_goal=e;break
                        if winning_goal:
                            try: win_minute=int(winning_goal.get("minute"))
                            except Exception: win_minute=0
                            scorer=" ".join(str(winning_goal.get("footballer_name") or "").strip().split())
                            if win_minute>90:
                                award(actual_winner,"after_hours",when,tid,no,f"Zwycięski gol w dogrywce: {scorer or '—'} {winning_goal.get('minute_label') or str(win_minute)+"'"}")

                            # Joker: the decisive scorer had previously entered as a substitute.
                            # For substitution events footballer_name = player IN, related = player OUT.
                            scorer_norm=self._norm_scorer_name(scorer)
                            if scorer_norm:
                                win_order=int(winning_goal.get("event_order") or 10**9)
                                sub=next((x for x in evs if str(x.get("event_type") or "")=="substitution"
                                          and str(x.get("actor_player_id") or "")==actual_winner
                                          and self._norm_scorer_name(str(x.get("footballer_name") or ""))==scorer_norm
                                          and int(x.get("event_order") or 10**9)<win_order),None)
                                if sub:
                                    award(actual_winner,"joker",when,tid,no,f"{scorer} wszedł z ławki i zdobył gola na wagę zwycięstwa")

                    # Hat-trick Express can be earned by either participant, even if
                    # they do not win the match. Own goals are never scorer goals.
                    scorer_goals=defaultdict(list)
                    for e in known_goals:
                        if str(e.get("event_type") or "") not in {"normal_goal","penalty_goal"}:continue
                        pid0=str(e.get("credited_player_id") or "")
                        scorer=" ".join(str(e.get("footballer_name") or "").strip().split())
                        norm=self._norm_scorer_name(scorer)
                        try:minute=int(e.get("minute"))
                        except Exception:continue
                        try:stoppage=int(e.get("stoppage") or 0)
                        except Exception:stoppage=0
                        if pid0 and norm:
                            scorer_goals[(pid0,norm,scorer)].append((minute+max(stoppage,0),e))
                    for (pid0,_norm,scorer),seq in scorer_goals.items():
                        seq.sort(key=lambda x:(x[0],int(x[1].get("event_order") or 10**9)))
                        for i in range(2,len(seq)):
                            span=seq[i][0]-seq[i-2][0]
                            if span<=15:
                                award(pid0,"hat_trick_express",when,tid,no,f"{scorer}: hat-trick w {span} min")
                                break

        # Tournament-context achievements.  These need the history inside one FIFA Night,
        # so they are evaluated per completed tournament instead of as global streaks.
        elimination_stages={"QF","BARRAGE","SF","LB","LB_FINAL","FINAL","RESET_FINAL"}
        proper_events=[e for e in events if str(e.get("format_key") or "")!="duel1v1"]
        completed_events=[e for e in events if str(e.get("status") or "")=="completed"]
        defending_champion_by_tid={}
        prev_champ_for_event=None
        for e in proper_events:
            defending_champion_by_tid[str(e["id"])]=prev_champ_for_event
            if e.get("champion_player_id"):prev_champ_for_event=str(e.get("champion_player_id") or "")

        def actual_scores(m: dict) -> tuple[int,int]:
            hs,ass=int(m.get("home_score") or 0),int(m.get("away_score") or 0)
            tid=str(m.get("tournament_id") or "")
            fmt=str((event_by.get(tid) or {}).get("format_key") or "")
            if fmt.startswith("double") and str(m.get("stage") or "")=="FINAL":hs=max(0,hs-1)
            return hs,ass

        for e in proper_events:
            tid=str(e["id"]);defending=defending_champion_by_tid.get(tid)
            tmatches=[m for m in matches if str(m.get("tournament_id") or "")==tid]
            tmatches.sort(key=lambda m:(self._event_when_match(m),int(m.get("match_no") or 0)))
            prior_losses=defaultdict(set);elim_wins=defaultdict(int);close_wins=defaultdict(int)
            for m in tmatches:
                home=str(m.get("home_player_id") or "");away=str(m.get("away_player_id") or "")
                if not home or not away:continue
                rh=self._result_for_player(m,home)
                if rh=="D":continue
                winner=home if rh=="W" else away;loser=away if winner==home else home
                stage=str(m.get("stage") or "");when=self._event_when_match(m);no=int(m.get("match_no") or 0)
                hs,ass=actual_scores(m);margin=abs(hs-ass)

                if margin==1:
                    close_wins[winner]+=1
                    progress[winner]["max_close_wins_tournament"]=max(progress[winner]["max_close_wins_tournament"],close_wins[winner])
                    if close_wins[winner]>=3:
                        award(winner,"on_the_edge",when,tid,no,f"3. wygrana jedną bramką w tym turnieju: {m.get('home_name')} {int(m.get('home_score') or 0)}:{int(m.get('away_score') or 0)} {m.get('away_name')}")

                if stage in elimination_stages:
                    elim_wins[winner]+=1
                    progress[winner]["max_elim_wins_tournament"]=max(progress[winner]["max_elim_wins_tournament"],elim_wins[winner])
                    if elim_wins[winner]>=3:
                        award(winner,"executioner",when,tid,no,"3. wygrany mecz eliminacyjny w tym turnieju")
                    if loser in prior_losses[winner]:
                        award(winner,"revenge",when,tid,no,f"Rewanż z {names.get(loser,'rywalem')} zakończony zwycięstwem w meczu eliminacyjnym")

                if stage in {"FINAL","RESET_FINAL"} and m.get("home_penalties") is not None and m.get("away_penalties") is not None:
                    award(winner,"steel_nerves",when,tid,no,f"Finał po karnych {m.get('home_penalties')}:{m.get('away_penalties')}")

                if defending and loser==defending and winner!=defending:
                    award(winner,"champion_hunter",when,tid,no,f"Pokonany obrońca tytułu: {names.get(defending,'?')}")

                prior_losses[loser].add(winner)

        # Tournament achievements require a completed tournament. An unfinished official
        # event keeps its match achievements, but never creates a title/podium badge.
        previous_champ=None
        for e in completed_events:
            tid=str(e["id"]);champ=str(e.get("champion_player_id") or "");when=str(e.get("completed_at") or e.get("created_at") or "")
            if not champ:
                previous_champ=None;continue
            pr=progress[champ];pr["titles"]+=1
            if pr["titles"]==1: award(champ,"first_title",when,tid,None,f"Mistrz FIFA Night #{tournament_no.get(tid,'?')}")
            if pr["titles"]==5: award(champ,"titles_5",when,tid,None,"5. tytuł FIFA Night")
            if previous_champ==champ:
                pr["title_streak"]+=1
            else:
                pr["title_streak"]=1
            pr["max_title_streak"]=max(pr["max_title_streak"],pr["title_streak"])
            if pr["title_streak"]>=2: award(champ,"back_to_back",when,tid,None,"Dwa tytuły z rzędu")
            previous_champ=champ
            team=" ".join(str(team_by.get((tid,champ),"") or "").strip().split())
            if team and self._norm_team_name(team) not in fixed:
                award(champ,"wild_one",when,tid,None,f"Tytuł Wild Cardem: {team}")
            own=[m for m in matches if str(m.get("tournament_id"))==tid and champ in (str(m.get("home_player_id") or ""),str(m.get("away_player_id") or ""))]
            if own:
                # Perfect Night means ONLY regulation-time wins. A shoot-out is a
                # draw after 90', and any confirmed goal after minute 90 proves the
                # match went to extra time. For legacy matches without a detailed
                # timeline, we can still reject known shoot-outs but cannot invent
                # an unrecorded extra time.
                perfect=True
                for pm in own:
                    if self._result_for_player(pm,champ)!="W":
                        perfect=False;break
                    if pm.get("home_penalties") is not None or pm.get("away_penalties") is not None:
                        perfect=False;break
                    pevs=detailed_by_match.get((tid,int(pm.get("match_no") or 0)),[])
                    if any(str(x.get("event_type") or "") in {"normal_goal","penalty_goal","own_goal"}
                           and not int(x.get("synthetic_de") or 0) and int(x.get("minute") or 0)>90 for x in pevs):
                        perfect=False;break
                if perfect:
                    award(champ,"perfect_night",when,tid,None,"Mistrzostwo po samych zwycięstwach w regulaminowych 90 minutach")
            if own:
                goals_against=0
                for m in own:
                    ah,aa=actual_scores(m)
                    goals_against += aa if str(m.get("home_player_id") or "")==champ else ah
                if goals_against==0:
                    award(champ,"fortress",when,tid,None,"Tytuł bez straty gola")
            fmt=str(e.get("format_key") or "")
            if fmt.startswith("double") and any(self._result_for_player(m,champ)=="L" for m in own):
                award(champ,"from_the_dead",when,tid,None,"Tytuł po spadku do Losers Bracket")
            if (fmt.startswith("groups") or fmt.startswith("league")) and any(str(m.get("stage") or "") in {"GROUP","LEAGUE"} and self._result_for_player(m,champ)=="L" for m in own):
                award(champ,"rebirth",when,tid,None,"Tytuł mimo wcześniejszej porażki w grupie lub lidze")
            qualifying_last={"groups6":2,"groups6_full":3,"groups7":3,"groups7_sf":2,"groups8_sf":2,"groups8_barrage":3}
            if fmt in qualifying_last:
                grp=group_by.get((tid,champ),"")
                if grp:
                    ids=group_players.get((tid,grp),[])
                    gm=[m for m in matches if str(m.get("tournament_id") or "")==tid and str(m.get("group_name") or "")==grp]
                    ties={pid0:tie_by.get((tid,pid0),0) for pid0 in ids}
                    rows=group_table(ids,gm,ties) if ids else []
                    pos=next((i+1 for i,r in enumerate(rows) if str(r.get("player_id") or "")==champ),None)
                    if pos==qualifying_last[fmt]:
                        award(champ,"last_ticket",when,tid,None,f"Awans z {pos}. miejsca w grupie i tytuł FIFA Night")

        # Historical finance thresholds: simulate balance after each official cash event.
        balances=defaultdict(int)
        for e in ledger:
            when=str(e.get("completed_at") or e.get("created_at") or "");tid=str(e.get("id") or "")
            stake=int(e.get("stake_cents") or 0)
            if stake>0:
                for pid in e.get("cash_player_ids") or []: balances[str(pid)]-=stake
            winner=str(e.get("prize_winner_player_id") or "");prize=int(e.get("prize_cents") or 0)
            if winner and prize>0:balances[winner]+=prize
            touched=set(str(x) for x in (e.get("cash_player_ids") or []))|({winner} if winner else set())
            for pid in touched:
                pr=progress[pid];pr["balance_cents"]=balances[pid];pr["max_balance_cents"]=max(pr["max_balance_cents"],balances[pid]);pr["min_balance_cents"]=min(pr["min_balance_cents"],balances[pid])
                if balances[pid]>=25000:award(pid,"shark",when,tid,None,f"Bilans osiągnął {balances[pid]/100:.2f} zł")
                if balances[pid]<=-25000:award(pid,"sponsor",when,tid,None,f"Bilans spadł do {balances[pid]/100:.2f} zł")

        # Include every player with official history, even if no badge yet.
        participant_ids=set()
        for m in matches:
            participant_ids|={str(m.get("home_player_id") or ""),str(m.get("away_player_id") or "")}
        participant_ids.discard("")
        out=[]
        cat_by={x["key"]:x for x in catalog}
        for pid in sorted(participant_ids,key=lambda x:names.get(x,"?").casefold()):
            pr=progress[pid];earned=[];locked=[]
            for c in catalog:
                if c["key"] in unlocked[pid]: earned.append({**c,**unlocked[pid][c["key"]]})
                else:
                    k=c["key"]
                    if k=="first_blood":pg=f"{pr['wins']}/1 zwycięstwo"
                    elif k=="first_title":pg=f"{pr['titles']}/1 tytuł"
                    elif k=="wins_10":pg=f"{min(pr['wins'],10)}/10 zwycięstw"
                    elif k=="wins_50":pg=f"{min(pr['wins'],50)}/50 zwycięstw"
                    elif k=="matches_100":pg=f"{min(pr['matches'],100)}/100 meczów"
                    elif k=="goals_100":pg=f"{min(pr['goals'],100)}/100 goli"
                    elif k=="titles_5":pg=f"{min(pr['titles'],5)}/5 tytułów"
                    elif k=="on_fire":pg=f"najlepsza seria: {pr['max_win_streak']}/5"
                    elif k=="unstoppable":pg=f"najlepsza seria: {pr['max_win_streak']}/10"
                    elif k=="wall":pg=f"najlepsza seria czystych kont: {pr['max_clean_streak']}/3"
                    elif k=="massacre":pg=f"największa przewaga: {pr['max_margin']}/5"
                    elif k=="thriller":pg="czeka na thriller"
                    elif k=="ice_cold":pg=f"wygrane karne: {pr['pen_wins']}"
                    elif k=="many_clubs":pg=f"{min(len(pr['win_teams']),5)}/5 drużyn"
                    elif k=="wild_one":pg="czeka na tytuł Wild Cardem"
                    elif k=="perfect_night":pg="czeka na mistrzostwo po samych wygranych w 90 minutach"
                    elif k=="unkillable":pg=f"największa odrobiona strata: {pr['max_comeback_deficit']}/3"
                    elif k=="ten_men":pg="czeka na zwycięstwo mimo czerwonej kartki"
                    elif k=="penalty_executioner":pg=f"{min(pr['penalty_goals'],10)}/10 goli z karnych"
                    elif k=="after_hours":pg="czeka na zwycięskiego gola w dogrywce"
                    elif k=="hat_trick_express":pg="czeka na hat-trick w maks. 15 minut"
                    elif k=="butcher":pg=f"{min(pr['discipline_points'],25)}/25 pkt dyscyplinarnych"
                    elif k=="joker":pg="czeka na zwycięskiego gola zmiennika"
                    elif k=="from_the_dead":pg="czeka na mistrzowski powrót z LB"
                    elif k=="shark":pg=f"bilans: {pr['balance_cents']/100:.2f} zł / +250 zł"
                    elif k=="sponsor":pg=f"bilans: {pr['balance_cents']/100:.2f} zł / -250 zł"
                    elif k=="back_to_back":pg=f"najlepsza seria tytułów: {pr['max_title_streak']}/2"
                    elif k=="steel_nerves":pg="czeka na wygrany finał po karnych"
                    elif k=="executioner":pg=f"najlepiej w turnieju: {pr['max_elim_wins_tournament']}/3 meczów eliminacyjnych"
                    elif k=="revenge":pg="czeka na zwycięski rewanż w meczu eliminacyjnym"
                    elif k=="fortress":pg="czeka na tytuł bez straty gola"
                    elif k=="on_the_edge":pg=f"najlepiej w turnieju: {pr['max_close_wins_tournament']}/3 wygranych jedną bramką"
                    elif k=="champion_hunter":pg="czeka na pokonanie obrońcy tytułu"
                    elif k=="last_ticket":pg="czeka na mistrzostwo po awansie z ostatniego premiowanego miejsca"
                    elif k=="rebirth":pg="czeka na tytuł mimo porażki w grupie lub lidze"
                    else:pg="—"
                    locked.append({**c,"progress":pg})
            earned.sort(key=lambda x:(x.get("earned_at") or "",list(cat_by).index(x["key"])))
            out.append({"player_id":pid,"name":names.get(pid,"?"),"unlocked":earned,"locked":locked,"count":len(earned),"total":len(catalog)})
        return {"catalog":catalog,"players":out}

    def achievements_unlocked_in_tournament(self, tid: str) -> list[dict]:
        data=self.achievement_center();out=[]
        for p in data.get("players",[]):
            for a in p.get("unlocked",[]):
                if str(a.get("tournament_id") or "")==str(tid):out.append({"player_id":p["player_id"],"player_name":p["name"],**a})
        return out

    def _goal_milestone_resolutions_conn(self, conn) -> dict:
        raw=self._setting_get_conn(conn,"flex_global_goal_milestone_scorers")
        try:return json.loads(raw) if raw else {}
        except Exception:return {}

    def set_goal_milestone_scorer(self, milestone_key: str, scorer_name: str, player_id: str | None = None, player_name: str | None = None) -> None:
        key=str(milestone_key or "").strip();scorer=" ".join(str(scorer_name or "").strip().split())
        if not key or not scorer:raise ValueError("Wybierz lub wpisz strzelca jubileuszowego gola.")
        with self.connect() as conn:
            data=self._goal_milestone_resolutions_conn(conn)
            data[key]={"scorer_name":scorer,"player_id":str(player_id or ""),"player_name":str(player_name or ""),"resolved_at":now_iso()}
            self._setting_set_conn(conn,"flex_global_goal_milestone_scorers",json.dumps(data,ensure_ascii=False))

    def global_milestones(self) -> dict:
        """Historical FIFA Night milestones plus the next counters.

        Match/goal/win counters include all official matches, including 1v1. Tournament
        numbers count only real tournaments. Goal-scorer identity is admin-resolved because
        match_scorers stores totals, not chronological goal order inside a match.
        """
        with self.connect() as conn:
            matches=self._official_matches_conn(conn)
            events_all=self._fetchall(conn,"""SELECT t.id,t.status,t.champion_player_id,t.completed_at,t.created_at,fm.format_key
                FROM tournaments t JOIN flex_tournament_meta fm ON fm.tournament_id=t.id
                WHERE t.status IN ('completed','abandoned') AND t.is_test=0
                ORDER BY COALESCE(t.completed_at,t.created_at),t.created_at,t.id""")
            tps=self._fetchall(conn,"""SELECT tp.tournament_id,tp.player_id,tp.team,p.name
                FROM tournament_players tp JOIN players p ON p.id=tp.player_id
                JOIN tournaments t ON t.id=tp.tournament_id WHERE t.status IN ('completed','abandoned') AND t.is_test=0""")
            scorer_rows=self._fetchall(conn,"""SELECT ms.tournament_id,ms.match_no,ms.side,ms.scorer_name,ms.goals
                FROM match_scorers ms JOIN tournaments t ON t.id=ms.tournament_id
                WHERE t.status IN ('completed','abandoned') AND t.is_test=0 ORDER BY ms.tournament_id,ms.match_no,ms.side,ms.scorer_name""")
            detailed_goal_rows=self._fetchall(conn,"""SELECT me.*
                FROM match_events me JOIN tournaments t ON t.id=me.tournament_id
                WHERE t.status IN ('completed','abandoned') AND t.is_test=0
                  AND me.event_type IN ('normal_goal','penalty_goal','own_goal')
                  AND COALESCE(me.synthetic_de,0)=0
                ORDER BY me.tournament_id,me.match_no,me.event_order,me.id""")
            detailed_event_rows=self._fetchall(conn,"""SELECT me.*
                FROM match_events me JOIN tournaments t ON t.id=me.tournament_id
                WHERE t.status IN ('completed','abandoned') AND t.is_test=0
                  AND me.event_type IN ('penalty_goal','penalty_miss','own_goal','yellow_card','red_card','normal_goal')
                ORDER BY me.tournament_id,me.match_no,me.event_order,me.id""")
            resolutions=self._goal_milestone_resolutions_conn(conn)
        names={str(r["player_id"]):str(r["name"]) for r in tps};team_by={(str(r["tournament_id"]),str(r["player_id"])):str(r.get("team") or "") for r in tps}
        fixed={self._norm_team_name(x) for x in FIXED_TEAMS}
        tournaments=[e for e in events_all if str(e.get("format_key"))!="duel1v1"]
        event_fmt={str(e["id"]):str(e.get("format_key") or "") for e in events_all}
        tournament_no={str(e["id"]):i+1 for i,e in enumerate(tournaments)}
        def actual_score_pair(m):
            bonus=1 if event_fmt.get(str(m.get("tournament_id") or ""),"").startswith("double") and str(m.get("stage") or "")=="FINAL" else 0
            return max(0,int(m.get("home_score") or 0)-bonus),int(m.get("away_score") or 0)
        def actual_goals_in_match(m):
            hs,ass=actual_score_pair(m);return hs+ass
        match_by={(str(m["tournament_id"]),int(m["match_no"])):m for m in matches}
        scorer_by=defaultdict(list)
        for r in scorer_rows:scorer_by[(str(r["tournament_id"]),int(r["match_no"]))].append(r)
        detailed_goals_by=defaultdict(list)
        for r in detailed_goal_rows:detailed_goals_by[(str(r["tournament_id"]),int(r["match_no"]))].append(r)
        detailed_events_by=defaultdict(list)
        for r in detailed_event_rows:detailed_events_by[(str(r["tournament_id"]),int(r["match_no"]))].append(r)
        timeline=[];pending=[]
        def add(key,icon,title,when="",tid=None,match_no=None,detail="",kind="other",order=0,extra=None):
            timeline.append({"key":key,"icon":icon,"title":title,"earned_at":str(when or ""),"tournament_id":str(tid) if tid else None,
                             "tournament_no":tournament_no.get(str(tid)) if tid else None,"match_no":int(match_no) if match_no is not None else None,
                             "detail":str(detail or ""),"kind":kind,"order":order,**(extra or {})})
        def mdetail(m):
            score=f"{m.get('home_name')} {int(m.get('home_score') or 0)}:{int(m.get('away_score') or 0)} {m.get('away_name')}"
            if m.get("home_penalties") is not None:score+=f" (k. {m.get('home_penalties')}:{m.get('away_penalties')})"
            return score

        # First-time history moments that do not depend on a threshold series.
        if matches:
            m=matches[0];add("first_match","🌟","Pierwszy oficjalny mecz FIFA Night",self._event_when_match(m),m["tournament_id"],m["match_no"],mdetail(m),"first",1)
        first_champion_event=next((e for e in tournaments if str(e.get("status") or "")=="completed" and e.get("champion_player_id")),None)
        if first_champion_event:
            e=first_champion_event;champ=str(e.get("champion_player_id") or "");add("first_champion","🏆","Pierwszy mistrz FIFA Night",e.get("completed_at") or e.get("created_at"),e["id"],None,names.get(champ,"?"),"first",2)
        first_pen=next((m for m in matches if m.get("home_penalties") is not None and m.get("away_penalties") is not None),None)
        if first_pen:add("first_penalties","🥅","Pierwsze karne",self._event_when_match(first_pen),first_pen["tournament_id"],first_pen["match_no"],mdetail(first_pen),"first",3)
        first_cs=next((m for m in matches if 0 in actual_score_pair(m)),None)
        if first_cs:
            holders=[];fhs,fas=actual_score_pair(first_cs)
            if fas==0:holders.append(str(first_cs.get("home_name") or "?"))
            if fhs==0:holders.append(str(first_cs.get("away_name") or "?"))
            add("first_clean_sheet","🧱","Pierwsze czyste konto",self._event_when_match(first_cs),first_cs["tournament_id"],first_cs["match_no"],f"{', '.join(holders)} • {mdetail(first_cs)}","first",4)
        first_ten=next((m for m in matches if actual_goals_in_match(m)>=10),None)
        if first_ten:add("first_10_goals_match","🔥","Pierwszy mecz z 10+ golami",self._event_when_match(first_ten),first_ten["tournament_id"],first_ten["match_no"],mdetail(first_ten),"first",5)
        first_mass=next((m for m in matches if abs(actual_score_pair(m)[0]-actual_score_pair(m)[1])>=5),None)
        if first_mass:add("first_big_win","💥","Pierwsze zwycięstwo różnicą 5+",self._event_when_match(first_mass),first_mass["tournament_id"],first_mass["match_no"],mdetail(first_mass),"first",6)
        first_de=next((e for e in tournaments if str(e.get("format_key") or "").startswith("double")),None)
        if first_de:
            champ=str(first_de.get("champion_player_id") or "")
            de_detail=(f"Mistrz: {names.get(champ,'?')}" if champ else "Turniej zakończony jako niedokończony")
            add("first_de","⚔️","Pierwszy Double Elimination",first_de.get("completed_at") or first_de.get("created_at"),first_de["id"],None,de_detail,"first",7)
        first_duel=next((e for e in events_all if str(e.get("format_key"))=="duel1v1"),None)
        if first_duel:
            dm=next((m for m in matches if str(m.get("tournament_id"))==str(first_duel["id"])),None)
            add("first_duel","🥊","Pierwszy oficjalny 1 vs 1",first_duel.get("completed_at") or first_duel.get("created_at"),first_duel["id"],dm.get("match_no") if dm else None,mdetail(dm) if dm else "","first",8)
        first_wc=None
        for e in tournaments:
            tid=str(e["id"]);champ=str(e.get("champion_player_id") or "");team=" ".join(str(team_by.get((tid,champ),"") or "").strip().split())
            if champ and team and self._norm_team_name(team) not in fixed:first_wc=(e,champ,team);break
        if first_wc:
            e,champ,team=first_wc;add("first_wc_champion","🎲","Pierwszy mistrz Wild Cardem",e.get("completed_at") or e.get("created_at"),e["id"],None,f"{names.get(champ,'?')} • {team}","first",9)

        # Match number milestones.
        for idx,m in enumerate(matches,1):
            if idx==50 or (idx>=100 and idx%100==0):add(f"match_{idx}","💎",f"{idx}. mecz FIFA Night",self._event_when_match(m),m["tournament_id"],m["match_no"],mdetail(m),"match",idx)

        # Global goals. New scanned matches can resolve the exact jubilee goal
        # automatically from chronological match_events; older matches keep the
        # existing manual-resolution fallback.
        cumulative=0
        max_goal_total=sum(actual_goals_in_match(m) for m in matches)
        goal_thresholds=(1,50,*tuple(range(100,((max_goal_total//100)+1)*100+1,100)))
        for m in matches:
            match_goal_count=actual_goals_in_match(m)
            before=cumulative;cumulative+=match_goal_count
            crossed=[x for x in goal_thresholds if before<x<=cumulative]
            if not crossed:continue
            detailed=detailed_goals_by.get((str(m["tournament_id"]),int(m["match_no"])),[])
            detailed_complete=(len(detailed)==match_goal_count)
            for th in crossed:
                key="first_goal" if th==1 else f"goal_{th}";title="Pierwszy gol FIFA Night" if th==1 else f"{th}. gol FIFA Night"
                auto_event=None
                if detailed_complete:
                    pos=int(th-before)-1
                    if 0<=pos<len(detailed):auto_event=detailed[pos]
                resolution=resolutions.get(key) or {}
                scorer=str(resolution.get("scorer_name") or "");owner=str(resolution.get("player_name") or "")
                auto_resolution={}
                if auto_event:
                    et=str(auto_event.get("event_type") or "")
                    credited_pid=str(auto_event.get("credited_player_id") or "")
                    credited_name=names.get(credited_pid,"")
                    footballer=str(auto_event.get("footballer_name") or "").strip()
                    minute_label=str(auto_event.get("minute_label") or "").strip()
                    minute_suffix=f" ({minute_label}')" if minute_label else ""
                    if et=="own_goal":
                        scorer=""
                        own_by=footballer or "?"
                        event_detail=f"samobój: {own_by}{f' • gol dla {credited_name}' if credited_name else ''}{minute_suffix}"
                        auto_resolution={"auto":True,"event_type":"own_goal","own_goal_by":own_by,"player_id":credited_pid,"player_name":credited_name}
                    else:
                        scorer=footballer
                        owner=credited_name
                        pen=" (karny)" if et=="penalty_goal" else ""
                        event_detail=f"strzelec: {scorer}{pen}{f' dla {owner}' if owner else ''}{minute_suffix}"
                        auto_resolution={"auto":True,"event_type":et,"scorer_name":scorer,"player_id":credited_pid,"player_name":owner}
                    detail=mdetail(m)+f" • {event_detail}"
                else:
                    scorer_txt=(f"{scorer} dla {owner}" if scorer and owner else scorer)
                    detail=mdetail(m)+(f" • strzelec: {scorer_txt}" if scorer else " • strzelec do wskazania")
                candidates=[]
                for sr in scorer_by.get((str(m["tournament_id"]),int(m["match_no"])),[]):
                    side=str(sr.get("side") or "");pid=str(m.get("home_player_id") if side=="home" else m.get("away_player_id") or "")
                    pname=str(m.get("home_name") if side=="home" else m.get("away_name") or "?")
                    team=str(m.get("home_team") if side=="home" else m.get("away_team") or "")
                    candidates.append({"scorer_name":str(sr.get("scorer_name") or ""),"goals":int(sr.get("goals") or 0),"player_id":pid,"player_name":pname,"team":team})
                effective_resolution=auto_resolution or resolution
                extra={"threshold":th,"scorer_resolution":effective_resolution,"scorer_candidates":candidates,"auto_resolved":bool(auto_event)}
                add(key,"⚽",title,self._event_when_match(m),m["tournament_id"],m["match_no"],detail,"goal",th,extra)
                if not auto_event and not scorer:
                    pending.append({"key":key,"title":title,"threshold":th,"match":m,"detail":mdetail(m),"candidates":candidates})

        # Tournament number milestones.
        for idx,e in enumerate(tournaments,1):
            if idx in (10,25,50,100):
                champ=str(e.get("champion_player_id") or "")
                detail=(f"Mistrz: {names.get(champ,'?')}" if champ else "Turniej zakończony jako niedokończony")
                add(f"tournament_{idx}","🏆",f"{idx}. FIFA Night",e.get("completed_at") or e.get("created_at"),e["id"],None,detail,"tournament",idx)

        # Global match wins (not player win badges). Draws do not advance this counter.
        wins=0
        for m in matches:
            if self._result_for_player(m,str(m.get("home_player_id") or ""))=="D":continue
            wins+=1
            if wins==50 or (wins>=100 and wins%100==0):
                winner=str(m.get("winner_player_id") or (m.get("home_player_id") if int(m.get("home_score") or 0)>int(m.get("away_score") or 0) else m.get("away_player_id")) or "")
                add(f"win_{wins}","🥇",f"{wins}. zwycięstwo w historii FIFA Night",self._event_when_match(m),m["tournament_id"],m["match_no"],f"{names.get(winner,m.get('home_name') if winner==m.get('home_player_id') else m.get('away_name'))} • {mdetail(m)}","win",wins)

        # Penalty shootouts.
        pen_count=0
        for m in matches:
            if m.get("home_penalties") is None or m.get("away_penalties") is None:continue
            pen_count+=1
            if pen_count in (10,25,50):add(f"penalties_{pen_count}","🥅",f"{pen_count}. seria rzutów karnych",self._event_when_match(m),m["tournament_id"],m["match_no"],mdetail(m),"penalties",pen_count)

        # Clean sheets. A 0:0 creates two clean sheets in the same match.
        cs_count=0
        for m in matches:
            holders=[];mhs,mas=actual_score_pair(m)
            if mas==0:holders.append((str(m.get("home_player_id") or ""),str(m.get("home_name") or "?")))
            if mhs==0:holders.append((str(m.get("away_player_id") or ""),str(m.get("away_name") or "?")))
            for pid,pname in holders:
                cs_count+=1
                if cs_count%25==0:add(f"clean_sheet_{cs_count}","🧱",f"{cs_count}. czyste konto w historii",self._event_when_match(m),m["tournament_id"],m["match_no"],f"{pname} • {mdetail(m)}","clean_sheet",cs_count)

        # Hat-tricks from entered scorer rows.
        hat_events=[]
        for sr in scorer_rows:
            if int(sr.get("goals") or 0)<3:continue
            m=match_by.get((str(sr["tournament_id"]),int(sr["match_no"])))
            if not m:continue
            side=str(sr.get("side") or "");pname=str(m.get("home_name") if side=="home" else m.get("away_name") or "?")
            hat_events.append((self._event_when_match(m),str(sr["tournament_id"]),int(sr["match_no"]),str(sr.get("scorer_name") or "?"),pname,m))
        hat_events.sort(key=lambda x:(x[0],x[1],x[2],x[3].casefold()))
        if hat_events:
            when,tid,no,scorer,pname,m=hat_events[0];add("first_hattrick","🎩","Pierwszy hat-trick",when,tid,no,f"{scorer} dla {pname} • {mdetail(m)}","first",10)
        for idx,item in enumerate(hat_events,1):
            if idx%25==0:
                when,tid,no,scorer,pname,m=item;add(f"hattrick_{idx}","🎩",f"{idx}. hat-trick w historii",when,tid,no,f"{scorer} dla {pname} • {mdetail(m)}","hattrick",idx)

        # New-era global event milestones. These counters begin when detailed EA FC
        # event tracking was introduced, so titles explicitly say "zarejestrowany".
        # Penalty shoot-outs are not stored in match_events and therefore never count here.
        event_specs={
            "penalties_awarded":{
                "thresholds":(25,50,100,200),"icon":"🎯","kind":"match_penalty",
                "title":lambda n:f"{n}. zarejestrowany rzut karny w meczu",
                "match":lambda e: str(e.get("event_type") or "") in {"penalty_goal","penalty_miss"},
            },
            "own_goals":{
                "thresholds":(10,25,50,100),"icon":"↩️","kind":"own_goal",
                "title":lambda n:f"{n}. zarejestrowany samobój",
                "match":lambda e: str(e.get("event_type") or "")=="own_goal" and not int(e.get("synthetic_de") or 0),
            },
            "yellow_cards":{
                "thresholds":(25,50,100,250),"icon":"🟨","kind":"yellow_card",
                "title":lambda n:f"{n}. zarejestrowana żółta kartka",
                "match":lambda e: str(e.get("event_type") or "")=="yellow_card",
            },
            "red_cards":{
                "thresholds":(5,10,25,50),"icon":"🟥","kind":"red_card",
                "title":lambda n:f"{n}. zarejestrowana czerwona kartka",
                "match":lambda e: str(e.get("event_type") or "")=="red_card",
            },
            "extra_time_goals":{
                "thresholds":(25,50,100,200),"icon":"➕","kind":"extra_time_goal",
                "title":lambda n:f"{n}. zarejestrowany gol w dogrywce",
                "match":lambda e: str(e.get("event_type") or "") in {"normal_goal","penalty_goal","own_goal"}
                                  and not int(e.get("synthetic_de") or 0) and int(e.get("minute") or 0)>90,
            },
        }
        event_counts={k:0 for k in event_specs}
        for m in matches:
            key=(str(m["tournament_id"]),int(m["match_no"]))
            for e in detailed_events_by.get(key,[]):
                et=str(e.get("event_type") or "")
                footballer=str(e.get("footballer_name") or "").strip()
                minute_label=str(e.get("minute_label") or "").strip()
                minute_suffix=f" ({minute_label}')" if minute_label else ""
                actor_pid=str(e.get("actor_player_id") or "")
                credited_pid=str(e.get("credited_player_id") or "")
                actor_name=names.get(actor_pid,"")
                credited_name=names.get(credited_pid,"")
                for stat_key,spec in event_specs.items():
                    if not spec["match"](e):continue
                    event_counts[stat_key]+=1
                    n=event_counts[stat_key]
                    if n not in spec["thresholds"]:continue
                    if et=="own_goal":
                        who=footballer or "?"
                        ev_detail=f"samobój: {who}{f' • gol dla {credited_name}' if credited_name else ''}{minute_suffix}"
                    elif et=="penalty_miss":
                        ev_detail=f"niewykorzystany karny: {footballer or '?'}{f' • {actor_name}' if actor_name else ''}{minute_suffix}"
                    elif et=="penalty_goal":
                        ev_detail=f"karny: {footballer or '?'}{f' • {credited_name or actor_name}' if (credited_name or actor_name) else ''}{minute_suffix}"
                    elif et in {"yellow_card","red_card"}:
                        ev_detail=f"{footballer or '?'}{f' • {actor_name}' if actor_name else ''}{minute_suffix}"
                    else:
                        ev_detail=f"{footballer or '?'}{f' • {credited_name}' if credited_name else ''}{minute_suffix}"
                    add(f"{stat_key}_{n}",spec["icon"],spec["title"](n),self._event_when_match(m),m["tournament_id"],m["match_no"],
                        f"{mdetail(m)} • {ev_detail}",spec["kind"],n)

        timeline.sort(key=lambda x:(x.get("earned_at") or "",x.get("order") or 0,x.get("title") or ""))

        def next_target(current, thresholds):
            return next((x for x in thresholds if current<x),None)
        def next_50_then_100(current):
            if current<50:return 50
            if current<100:return 100
            return ((current//100)+1)*100
        def next_25(current):
            return ((current//25)+1)*25
        total_goals=sum(actual_goals_in_match(m) for m in matches)
        total_wins=sum(1 for m in matches if self._result_for_player(m,str(m.get("home_player_id") or ""))!="D")
        total_pens=sum(1 for m in matches if m.get("home_penalties") is not None and m.get("away_penalties") is not None)
        total_cs=sum((1 if actual_score_pair(m)[1]==0 else 0)+(1 if actual_score_pair(m)[0]==0 else 0) for m in matches)
        total_hats=len(hat_events)
        counters=[
            ("Mecze",len(matches),next_50_then_100(len(matches))),
            ("Gole",total_goals,next_50_then_100(total_goals)),
            ("FIFA Night",len(tournaments),next_target(len(tournaments),(10,25,50,100))),
            ("Zwycięstwa",total_wins,next_50_then_100(total_wins)),
            ("Serie karnych",total_pens,next_target(total_pens,(10,25,50,100))),
            ("Czyste konta",total_cs,next_25(total_cs)),
            ("Hat-tricki",total_hats,next_25(total_hats)),
            ("Karne w meczu",event_counts["penalties_awarded"],next_target(event_counts["penalties_awarded"],(25,50,100,200))),
            ("Samobóje",event_counts["own_goals"],next_target(event_counts["own_goals"],(10,25,50,100))),
            ("Żółte kartki",event_counts["yellow_cards"],next_target(event_counts["yellow_cards"],(25,50,100,250))),
            ("Czerwone kartki",event_counts["red_cards"],next_target(event_counts["red_cards"],(5,10,25,50))),
            ("Gole w dogrywce",event_counts["extra_time_goals"],next_target(event_counts["extra_time_goals"],(25,50,100,200))),
        ]
        next_rows=[{"name":n,"current":cur,"target":target,"left":max(0,target-cur) if target else 0} for n,cur,target in counters if target]
        return {"timeline":timeline,"pending_goal_scorers":pending,"next":next_rows,"totals":{
            "matches":len(matches),"goals":total_goals,"tournaments":len(tournaments),"wins":total_wins,
            "penalties":total_pens,"clean_sheets":total_cs,"hattricks":total_hats,
            **event_counts,
        }}

    def milestones_in_tournament(self, tid: str) -> list[dict]:
        return [x for x in self.global_milestones().get("timeline",[]) if str(x.get("tournament_id") or "")==str(tid)]

    def upcoming_global_match_milestone(self) -> dict | None:
        """Milestone badge for the next official match, including matches already played in an active event."""
        with self.connect() as conn:
            row=self._fetchone(conn,"""SELECT COUNT(*) AS n FROM matches m JOIN tournaments t ON t.id=m.tournament_id
                WHERE t.is_test=0 AND m.home_score IS NOT NULL""")
        no=int((row or {}).get("n") or 0)+1
        if no==50 or (no>=100 and no%100==0):return {"number":no,"title":f"{no}. OFICJALNY MECZ FIFA NIGHT"}
        return None

    def live_global_milestone_alerts(self, tid: str | None = None) -> list[dict]:
        """Near-term global milestone alerts for the live controller/TV.

        Includes official matches already played in the currently active tournament.
        Test tournaments are ignored and the technical +1 in a Double Elimination
        final is excluded from the global goal counter.
        """
        with self.connect() as conn:
            matches=self._fetchall(conn,"""
                SELECT m.home_score,m.away_score,m.stage,fm.format_key,t.completed_at,t.created_at,m.played_at
                FROM matches m
                JOIN tournaments t ON t.id=m.tournament_id
                JOIN flex_tournament_meta fm ON fm.tournament_id=m.tournament_id
                WHERE t.is_test=0 AND m.home_score IS NOT NULL
                ORDER BY COALESCE(m.played_at,t.completed_at,t.created_at),m.tournament_id,m.match_no
            """)
            tournament_rows=self._fetchall(conn,"""
                SELECT t.id,t.status,t.created_at,fm.format_key
                FROM tournaments t JOIN flex_tournament_meta fm ON fm.tournament_id=t.id
                WHERE t.is_test=0 AND fm.format_key<>'duel1v1'
                ORDER BY t.created_at,t.id
            """)
        def actual_goals(m):
            hs=int(m.get("home_score") or 0);ass=int(m.get("away_score") or 0)
            if str(m.get("format_key") or "").startswith("double") and str(m.get("stage") or "")=="FINAL":
                hs=max(0,hs-1)
            return hs+ass
        total_matches=len(matches)
        total_goals=sum(actual_goals(m) for m in matches)

        def next_50_then_100(cur:int) -> int:
            if cur<50:return 50
            if cur<100:return 100
            return ((cur//100)+1)*100

        alerts=[]
        mt=next_50_then_100(total_matches);mleft=mt-total_matches
        if 1<=mleft<=2:
            alerts.append({
                "kind":"match","target":mt,"left":mleft,
                "title":f"{mt}. oficjalny mecz FIFA Night",
                "message":f"Ten mecz będzie {mt}. oficjalnym meczem FIFA Night." if mleft==1 else f"Następny mecz po obecnym będzie {mt}. oficjalnym meczem FIFA Night.",
                "icon":"💎",
            })
        gt=next_50_then_100(total_goals);gleft=gt-total_goals
        if 1<=gleft<=5:
            alerts.append({
                "kind":"goal","target":gt,"left":gleft,
                "title":f"{gt}. gol FIFA Night",
                "message":f"Następny gol będzie {gt}. golem w historii FIFA Night." if gleft==1 else f"Do {gt}. gola w historii FIFA Night zostało {gleft}.",
                "icon":"⚽",
            })

        if tid:
            tids=[str(r.get("id") or "") for r in tournament_rows]
            if str(tid) in tids:
                no=tids.index(str(tid))+1
                if no in (10,25,50,100):
                    alerts.insert(0,{
                        "kind":"tournament","target":no,"left":0,
                        "title":f"{no}. FIFA Night",
                        "message":f"To jest jubileuszowy {no}. turniej FIFA Night.",
                        "icon":"🏆",
                    })
        return alerts

    def award_selections(self, year: int) -> dict:
        with self.connect() as conn:
            raw=self._setting_get_conn(conn,f"flex_award_selections_{int(year)}")
        try:return json.loads(raw) if raw else {}
        except Exception:return {}

    def set_award_selection(self, year: int, category_key: str, candidate_id: str, candidate_name: str) -> None:
        data=self.award_selections(year)
        data[str(category_key)]={"id":str(candidate_id),"name":str(candidate_name),"selected_at":now_iso()}
        with self.connect() as conn:
            self._setting_set_conn(conn,f"flex_award_selections_{int(year)}",json.dumps(data,ensure_ascii=False))

    def annual_awards(self, year: int) -> dict:
        """Live statistical TOP5 for the annual Awards screen.

        Tournament-style individual awards deliberately ignore 1v1 matches. Duels are
        used only by shared H2H/rivalry/team context and the dedicated King 1v1 award.
        """
        import math, statistics
        year=int(year); like=f"{year}-%"
        with self.connect() as conn:
            events=self._fetchall(conn,"""SELECT t.id,t.status,t.champion_player_id,t.completed_at,t.created_at,fm.format_key
                FROM tournaments t JOIN flex_tournament_meta fm ON fm.tournament_id=t.id
                WHERE t.status IN ('completed','abandoned') AND t.is_test=0 AND COALESCE(t.completed_at,t.created_at) LIKE ?
                ORDER BY COALESCE(t.completed_at,t.created_at),t.created_at,t.id""",(like,))
            if not events:
                return {"year":year,"categories":[],"overview":{"tournaments":0,"duels":0,"matches":0,"goals":0,"players":0}}
            tids=[str(x["id"]) for x in events]; q=','.join('?' for _ in tids)
            matches=self._fetchall(conn,f"""SELECT m.*,t.completed_at,t.created_at,hp.name home_name,ap.name away_name,
                htp.team home_team,atp.team away_team
                FROM matches m JOIN tournaments t ON t.id=m.tournament_id
                LEFT JOIN players hp ON hp.id=m.home_player_id LEFT JOIN players ap ON ap.id=m.away_player_id
                LEFT JOIN tournament_players htp ON htp.tournament_id=m.tournament_id AND htp.player_id=m.home_player_id
                LEFT JOIN tournament_players atp ON atp.tournament_id=m.tournament_id AND atp.player_id=m.away_player_id
                WHERE m.tournament_id IN ({q}) AND m.home_score IS NOT NULL
                ORDER BY COALESCE(m.played_at,t.completed_at,t.created_at),m.tournament_id,m.match_no""",tuple(tids))
            tps=self._fetchall(conn,f"""SELECT tp.tournament_id,tp.player_id,tp.team,p.name
                FROM tournament_players tp JOIN players p ON p.id=tp.player_id WHERE tp.tournament_id IN ({q})""",tuple(tids))
            scorer_rows=self._fetchall(conn,f"""SELECT ms.tournament_id,ms.match_no,ms.side,ms.scorer_name,ms.goals
                FROM match_scorers ms WHERE ms.tournament_id IN ({q})""",tuple(tids))
            detailed_event_rows=self._fetchall(conn,f"""SELECT me.tournament_id,me.match_no,me.event_order,me.event_type,
                me.actor_player_id,me.credited_player_id,me.synthetic_de,me.minute,me.stoppage,me.minute_label
                FROM match_events me WHERE me.tournament_id IN ({q})
                ORDER BY me.tournament_id,me.match_no,me.event_order,me.id""",tuple(tids))
            first_dates=self._fetchall(conn,"""SELECT tp.player_id,MIN(COALESCE(t.completed_at,t.created_at)) AS first_date
                FROM tournament_players tp JOIN tournaments t ON t.id=tp.tournament_id
                JOIN flex_tournament_meta fm ON fm.tournament_id=t.id
                WHERE t.status IN ('completed','abandoned') AND t.is_test=0 AND fm.format_key<>'duel1v1'
                GROUP BY tp.player_id""")
            finance_ledger,finance_names,_jp=self._finance_ledger_conn(conn)
            placements={tid:self._placement_order_conn(conn,tid) for tid in tids}

        event_by={str(e["id"]):e for e in events}; tournament_ids={tid for tid,e in event_by.items() if str(e.get("format_key"))!='duel1v1'}
        completed_tournament_ids={tid for tid,e in event_by.items() if tid in tournament_ids and str(e.get("status") or "")=="completed"}
        duel_ids=set(tids)-tournament_ids
        name_by={str(r["player_id"]):str(r["name"]) for r in tps}
        team_by={(str(r["tournament_id"]),str(r["player_id"])):str(r.get("team") or "") for r in tps}
        participant_tournaments=defaultdict(set)
        for r in tps:
            if str(r["tournament_id"]) in tournament_ids: participant_tournaments[str(r["player_id"])].add(str(r["tournament_id"]))
        fixed_norm={self._norm_team_name(x) for x in FIXED_TEAMS}
        ps=defaultdict(lambda:{"m":0,"w":0,"d":0,"l":0,"gf":0,"ga":0,"clean_sheets":0,"titles":0,"finals":0,"clutch_m":0,"clutch_w":0,
                               "pen":0,"pen_w":0,"big_wins":0,"max_margin":0,"one_goal_wins":0,"narrow_losses":0,
                               "teams":defaultdict(lambda:{"m":0,"w":0,"gf":0,"ga":0}),"wc_m":0,"wc_w":0,"wc_gf":0,"wc_ga":0,
                               "wc_titles":0,"wc_finals":0,"spectacle_scores":[],"spectacle_goals":0,"spectacle_pens":0,
                               "result_points":[],"t_results":defaultdict(lambda:{"m":0,"pts":0,"gf":0,"ga":0}),"scorer_goals":0})
        # Clutch = mecz, po którym porażka realnie kończy turniej / szansę na tytuł.
        # Winners Bracket i WB Final nie są clutch: przegrany nadal gra w Lower Bracket.
        clutch_stages={"QF","BARRAGE","SF","LB","LB_FINAL","FINAL","RESET_FINAL"}
        pair=defaultdict(lambda:{"n":0,"aw":0,"bw":0,"d":0,"important_matches":0,"importance_points":0,"names":None})
        teamagg=defaultdict(lambda:{"display":None,"m":0,"w":0,"d":0,"l":0,"gf":0,"ga":0,"titles":0})
        match_candidates=[]
        match_map={(str(m["tournament_id"]),int(m["match_no"])):m for m in matches}
        stages_by_player_tournament=defaultdict(set)
        debut_seq=defaultdict(list)
        has_reset_by_tid={
            tid:any(str(m.get("stage") or "")=="RESET_FINAL" for m in matches if str(m.get("tournament_id"))==tid)
            for tid in tournament_ids
        }

        for e in events:
            tid=str(e["id"]); champ=str(e.get("champion_player_id") or "")
            if tid in tournament_ids and champ:
                ps[champ]["titles"]+=1
                cteam=" ".join(str(team_by.get((tid,champ),"") or "").split())
                if cteam and self._norm_team_name(cteam) not in fixed_norm:
                    ps[champ]["wc_titles"]+=1
        for tid in completed_tournament_ids:
            finals=[m for m in matches if str(m["tournament_id"])==tid and m.get("stage") in ("FINAL","RESET_FINAL")]
            if finals:
                f=finals[-1]
                for pid in (f.get("home_player_id"),f.get("away_player_id")):
                    if pid:
                        pid=str(pid); ps[pid]["finals"]+=1
                        fteam=" ".join(str(team_by.get((tid,pid),"") or "").split())
                        if fteam and self._norm_team_name(fteam) not in fixed_norm:
                            ps[pid]["wc_finals"]+=1

        for m in matches:
            tid=str(m["tournament_id"]);h=str(m.get("home_player_id") or "");a=str(m.get("away_player_id") or "")
            if not h or not a:continue
            hs,ass=int(m["home_score"]),int(m["away_score"]); stage=str(m.get("stage") or "")
            rh=self._result_for_player(m,h);ra=self._result_for_player(m,a)
            # Rivalry uses all official matches including duels.
            k=tuple(sorted((h,a)));rec=pair[k];rec["n"]+=1;rec["names"]=(name_by.get(k[0],m.get("home_name") or "?"),name_by.get(k[1],m.get("away_name") or "?"))
            rk=self._result_for_player(m,k[0])
            if rk=="W":rec["aw"]+=1
            elif rk=="L":rec["bw"]+=1
            else:rec["d"]+=1
            importance_weight=4 if stage=="FINAL" else (3 if stage in ("SF","WB_FINAL","LB_FINAL") else (2 if stage in ("QF","BARRAGE","WB","LB") else 0))
            if importance_weight:
                rec["important_matches"]+=1
                rec["importance_points"]+=importance_weight
            # Team awards/rating also use all official matches.
            for pid,team,gf,ga,r in ((h,m.get("home_team"),hs,ass,rh),(a,m.get("away_team"),ass,hs,ra)):
                team=" ".join(str(team or "").split())
                if team:
                    nt=self._norm_team_name(team);tr=teamagg[nt];tr["display"]=tr["display"] or team;tr["m"]+=1;tr["gf"]+=gf;tr["ga"]+=ga;tr[{"W":"w","D":"d","L":"l"}[r]]+=1
            if tid not in tournament_ids:continue
            stages_by_player_tournament[(tid,h)].add(stage); stages_by_player_tournament[(tid,a)].add(stage)
            for pid,team,gf,ga,r in ((h,m.get("home_team"),hs,ass,rh),(a,m.get("away_team"),ass,hs,ra)):
                v=ps[pid];v["m"]+=1;v["gf"]+=gf;v["ga"]+=ga;v["clean_sheets"]+=int(ga==0);v[{"W":"w","D":"d","L":"l"}[r]]+=1
                pts=3 if r=="W" else (1 if r=="D" else 0);v["result_points"].append((pts,gf-ga))
                debut_seq[pid].append({"tid":tid,"stage":stage,"result":r,"pts":pts,"gf":gf,"ga":ga})
                tr=v["t_results"][tid];tr["m"]+=1;tr["pts"]+=pts;tr["gf"]+=gf;tr["ga"]+=ga
                team=" ".join(str(team or "").split())
                if team:
                    nt=self._norm_team_name(team);tv=v["teams"][nt];tv["m"]+=1;tv["gf"]+=gf;tv["ga"]+=ga;tv["w"]+=int(r=="W")
                    if nt not in fixed_norm:v["wc_m"]+=1;v["wc_w"]+=int(r=="W");v["wc_gf"]+=gf;v["wc_ga"]+=ga
                if stage in clutch_stages:v["clutch_m"]+=1;v["clutch_w"]+=int(r=="W")
                if r=="W":
                    margin=gf-ga;v["max_margin"]=max(v["max_margin"],margin);v["big_wins"]+=int(margin>=3);v["one_goal_wins"]+=int(margin==1)
                if r=="L":v["narrow_losses"]+=int((ga-gf)==1 or m.get("home_penalties") is not None)
                if m.get("home_penalties") is not None and m.get("away_penalties") is not None:v["pen"]+=1;v["pen_w"]+=int(m.get("winner_player_id")==pid)
            # Mecz Roku: wynik końcowy jest ważniejszy niż sama etykieta fazy.
            # W rankingu dominują (1) bliskość meczu i (2) realna stawka / ryzyko odpadnięcia.
            # Ranga fazy i liczba goli są tylko czynnikami pomocniczymi. Wartość score jest
            # wyłącznie techniczna do sortowania i nigdy nie jest pokazywana w UI.
            margin=abs(hs-ass)
            has_pens=m.get("home_penalties") is not None and m.get("away_penalties") is not None
            if has_pens:
                closeness=1.00; closeness_text="rozstrzygnięty po karnych"
            elif margin==0:
                closeness=1.00; closeness_text="remis"
            elif margin==1:
                closeness=1.00; closeness_text="różnica 1 gola"
            elif margin==2:
                # Dwa gole różnicy to już wyraźnie mniej emocji niż mecz na styku.
                # Sama wysoka stawka nie może wypchnąć zwykłego 2:0 nad 4:4 czy karne.
                closeness=.55; closeness_text="różnica 2 goli"
            elif margin==3:
                # Od tego miejsca oba wyniki są już wyraźne. Nie robimy ogromnej
                # przepaści między np. 4:1 i 7:3 — przy podobnej stawce bardziej
                # bramkowy 7:3 może być ciekawszym kandydatem do Meczu Roku.
                closeness=.25; closeness_text="różnica 3 goli"
            elif margin==4:
                closeness=.20; closeness_text="różnica 4 goli"
            else:
                closeness=.08; closeness_text=f"różnica {margin} goli"

            # Stakes answer the practical question: co oznaczała porażka w tym meczu?
            if stage in ("FINAL","RESET_FINAL"):
                stakes=1.00; stakes_text="mecz o tytuł"
            elif stage=="LB_FINAL":
                stakes=1.00; stakes_text="przegrany odpadał"
            elif stage in ("SF","QF","BARRAGE","LB"):
                stakes=.90; stakes_text="przegrany odpadał"
            elif stage=="WB_FINAL":
                stakes=.55; stakes_text="wysoka stawka, bez eliminacji"
            elif stage=="WB":
                stakes=.35; stakes_text="ważny mecz drabinki"
            else:
                stakes=.15; stakes_text="faza ligowa / grupowa"

            rank_value={
                "FINAL":1.00,"RESET_FINAL":1.00,"LB_FINAL":.86,"WB_FINAL":.80,"SF":.80,
                "QF":.60,"BARRAGE":.60,"LB":.46,"WB":.42
            }.get(stage,.20)
            stage_text={
                "FINAL":"finał","RESET_FINAL":"finał resetowy","LB_FINAL":"finał Lower Bracket",
                "WB_FINAL":"finał Winners Bracket","SF":"półfinał","QF":"ćwierćfinał",
                "BARRAGE":"baraż","LB":"Lower Bracket","WB":"Winners Bracket",
                "GROUP":"faza grupowa","L":"liga"
            }.get(stage,stage or "mecz")
            goals_value=min(hs+ass,8)/8.0

            # Mecz Roku: zgodnie z balansem ustalonym dla Awards. Nadal nie pokazujemy
            # punktów technicznych w UI — użytkownik widzi wyłącznie wynik i uzasadnienie.
            penalties_drama=1.0 if has_pens else 0.0
            match_score=(
                closeness*.35
                + goals_value*.22
                + stakes*.18
                + rank_value*.13
                + penalties_drama*.12
            )

            # Najbardziej Widowiskowy Gracz bazuje na charakterze KAŻDEGO meczu, nie na
            # randze fazy ani wyniku gracza. Dzięki temu nie jest kopią Gracza Roku.
            spectacle_match=closeness*.45 + goals_value*.40 + penalties_drama*.15
            for pid in (h,a):
                ps[pid]["spectacle_scores"].append(spectacle_match)
                ps[pid]["spectacle_goals"]+=hs+ass
                ps[pid]["spectacle_pens"]+=int(has_pens)

            reason_parts=[stage_text,closeness_text,stakes_text,f"{hs+ass} goli"]
            if has_pens:
                reason_parts.append(f"karne {m.get('home_penalties')}:{m.get('away_penalties')}")
            match_candidates.append({
                "id":f"{tid}:{m['match_no']}",
                "name":f"{m.get('home_name')} {hs}:{ass} {m.get('away_name')}",
                "score":round(match_score,6),
                "reason":" • ".join(reason_parts),
            })
        # tournament champion clubs
        for e in events:
            tid=str(e["id"]);champ=str(e.get("champion_player_id") or "")
            if tid in tournament_ids and champ:
                team=team_by.get((tid,champ),"");nt=self._norm_team_name(team)
                if nt:teamagg[nt]["display"]=teamagg[nt]["display"] or team;teamagg[nt]["titles"]+=1
        # Scorers:
        # - scorer_totals: concrete EA FC footballer across all official matches (Supersnajper)
        # - scorer_by_player: concrete footballer + FIFA Night participant controlling him (Król Strzelców)
        scorer_totals=defaultdict(int)
        scorer_display={}
        scorer_by_player=defaultdict(int)
        scorer_pair_display={}
        scorer_pair_teams=defaultdict(set)
        scorer_pair_team_display=defaultdict(set)
        scorer_pair_hattricks=defaultdict(int)
        for r in scorer_rows:
            m=match_map.get((str(r["tournament_id"]),int(r["match_no"])))
            if not m:continue
            scorer=" ".join(str(r.get("scorer_name") or "").split())
            goals=int(r.get("goals") or 0)
            if not scorer or goals<=0:continue
            sn=scorer.casefold()
            scorer_totals[sn]+=goals
            scorer_display.setdefault(sn,scorer)
            if str(r["tournament_id"]) in tournament_ids:
                pid=m.get("home_player_id") if str(r.get("side"))=="home" else m.get("away_player_id")
                if pid:
                    pid=str(pid)
                    pair_key=(pid,sn)
                    scorer_by_player[pair_key]+=goals
                    scorer_pair_display.setdefault(pair_key,scorer)
                    side_team=m.get("home_team") if str(r.get("side"))=="home" else m.get("away_team")
                    side_team=" ".join(str(side_team or "").split())
                    if side_team:
                        scorer_pair_teams[pair_key].add(self._norm_team_name(side_team))
                        scorer_pair_team_display[pair_key].add(side_team)
                    if goals>=3:
                        scorer_pair_hattricks[pair_key]+=1

        # New-era event rankings. These use only detailed match_events from official
        # tournament matches; old matches without a visual event timeline are not
        # treated as zeroes. 1v1 is intentionally excluded from annual FIFA Night
        # Awards/Rankings, consistently with the tournament-based player categories.
        event_rank=defaultdict(lambda:{"penalties_awarded":0,"penalty_goals":0,"penalty_misses":0,"own_goals":0,"first_goals":0})
        first_goal_by_match={}
        for e in detailed_event_rows:
            tid=str(e.get("tournament_id") or "")
            if tid not in tournament_ids:
                continue
            et=str(e.get("event_type") or "")
            actor=str(e.get("actor_player_id") or "")
            credited=str(e.get("credited_player_id") or "")
            synthetic=int(e.get("synthetic_de") or 0)
            if actor and et in ("penalty_goal","penalty_miss"):
                event_rank[actor]["penalties_awarded"]+=1
            if credited and et=="penalty_goal" and not synthetic:
                event_rank[credited]["penalty_goals"]+=1
            if actor and et=="penalty_miss":
                event_rank[actor]["penalty_misses"]+=1
            if actor and et=="own_goal" and not synthetic:
                event_rank[actor]["own_goals"]+=1
            if et in ("normal_goal","penalty_goal","own_goal") and credited and not synthetic:
                mk=(tid,int(e.get("match_no") or 0))
                order=int(e.get("event_order") or 10**9)
                prev=first_goal_by_match.get(mk)
                if prev is None or order<prev[0]:
                    first_goal_by_match[mk]=(order,credited)
        for _mk,(_order,pid) in first_goal_by_match.items():
            if pid:
                event_rank[pid]["first_goals"]+=1

        # New Awards based on detailed EA FC timelines. Only matches with a saved
        # event timeline are used, so older matches are never silently treated as
        # zero cards / zero late goals.
        discipline=defaultdict(lambda:{"yellow":0,"red":0,"points":0})
        late_stats=defaultdict(lambda:{"late_goals":0,"goals_90plus":0,"latest_value":0,"latest_label":""})
        detailed_match_keys=set()
        detailed_events_by_match=defaultdict(list)
        for e in detailed_event_rows:
            tid=str(e.get("tournament_id") or "")
            if tid not in tournament_ids:
                continue
            mk=(tid,int(e.get("match_no") or 0))
            detailed_match_keys.add(mk)
            detailed_events_by_match[mk].append(e)
            et=str(e.get("event_type") or "")
            actor=str(e.get("actor_player_id") or "")
            credited=str(e.get("credited_player_id") or "")
            synthetic=int(e.get("synthetic_de") or 0)
            if actor and et=="yellow_card":
                discipline[actor]["yellow"]+=1;discipline[actor]["points"]+=1
            elif actor and et=="red_card":
                discipline[actor]["red"]+=1;discipline[actor]["points"]+=3
            # Król Końcówek: only goals actually credited to a footballer. Own goals
            # and the technical DE goal do not create a late-goal achievement.
            if credited and et in ("normal_goal","penalty_goal") and not synthetic:
                minute=int(e.get("minute") or 0)
                stoppage=int(e.get("stoppage") or 0)
                if minute>=85:
                    ls=late_stats[credited]
                    ls["late_goals"]+=1
                    if minute>=90: ls["goals_90plus"]+=1
                    value=minute*100+stoppage
                    if value>ls["latest_value"]:
                        ls["latest_value"]=value
                        ls["latest_label"]=str(e.get("minute_label") or (f"{minute}+{stoppage}'" if stoppage else f"{minute}'"))

        # Number of detailed matches per participant, needed for a fair Fair Play
        # denominator. A detailed match counts for both players even when one of
        # them received no card at all.
        detailed_matches_by_player=defaultdict(int)
        for mk in detailed_match_keys:
            m=match_map.get(mk)
            if not m: continue
            for pid in (str(m.get("home_player_id") or ""),str(m.get("away_player_id") or "")):
                if pid: detailed_matches_by_player[pid]+=1

        # Comeback King. For every fully reconstructed detailed match we replay the
        # goal timeline and measure the largest deficit overcome by the eventual
        # winner. Scoring uses a gentler progressive scale agreed for FIFA Night:
        # 1 goal = 1 pt, 2 = 2 pts, 3 = 4 pts, 4 = 7 pts, 5 = 11 pts, etc.
        comeback_stats=defaultdict(lambda:{"wins":0,"points":0,"max_deficit":0,"from_deficits":defaultdict(int)})
        goal_types={"normal_goal","penalty_goal","own_goal"}
        for mk,evs in detailed_events_by_match.items():
            m=match_map.get(mk)
            if not m: continue
            winner=str(m.get("winner_player_id") or "")
            if not winner: continue
            h=str(m.get("home_player_id") or ""); a=str(m.get("away_player_id") or "")
            if winner not in (h,a): continue
            hs=int(m.get("home_score") or 0); ass=int(m.get("away_score") or 0)
            goals=[e for e in evs if str(e.get("event_type") or "") in goal_types and str(e.get("credited_player_id") or "")]
            # Do not infer missing goals. Comeback is calculated only when the
            # detailed timeline accounts for the actual scoreboard.
            if len(goals)!=(hs+ass): continue
            goals=sorted(goals,key=lambda e:(int(e.get("event_order") or 10**9),int(e.get("minute") or 0),int(e.get("stoppage") or 0)))
            score={h:0,a:0}; max_deficit=0
            for e in goals:
                pid=str(e.get("credited_player_id") or "")
                if pid in score: score[pid]+=1
                other=a if winner==h else h
                max_deficit=max(max_deficit,score.get(other,0)-score.get(winner,0))
            if max_deficit>0:
                cs=comeback_stats[winner]
                # Sequence 1,2,4,7,11... (increments grow by 1 each level).
                comeback_points=1+(max_deficit*(max_deficit-1))//2
                cs["wins"]+=1;cs["points"]+=comeback_points
                cs["max_deficit"]=max(cs["max_deficit"],max_deficit)
                cs["from_deficits"][max_deficit]+=1

        def pc(pid,v):return round(v["w"]/v["m"]*100,1) if v["m"] else 0.0
        def cand(pid,score,reason):return {"id":str(pid),"name":name_by.get(str(pid),"?"),"score":round(float(score),2),"reason":reason}
        def top(items,n=5):
            if any("_sort" in x for x in items):
                ranked=sorted(items,key=lambda x:x.get("_sort",()),reverse=True)[:n]
            else:
                ranked=sorted(items,key=lambda x:(float(x.get("score") or 0),str(x.get("name") or "")),reverse=True)[:n]
            return [{k:v for k,v in x.items() if k!="_sort"} for x in ranked]
        cats=[]
        def add(key,title,desc,items,award=True,secondary=None):cats.append({"key":key,"title":title,"description":desc,"award":award,"candidates":top(items),"secondary":secondary})

        # 1 player of year
        items=[]
        for pid,v in ps.items():
            if v["m"]<2:continue
            wp=pc(pid,v);cl=(v["clutch_w"]/v["clutch_m"]*100 if v["clutch_m"] else 0);gdpm=(v["gf"]-v["ga"])/v["m"]
            score=v["titles"]*27+v["finals"]*14+wp*.28+cl*.11+gdpm*4+len(participant_tournaments[pid])
            items.append(cand(pid,score,f"{v['titles']} tytuł(y), {v['finals']} finał(y), W% {wp}, bilans {v['gf']}:{v['ga']}"))
        add("player_year","🏆 Gracz Roku","Cały sezon w jednym miejscu: tytuły, finały, wyniki i najważniejsze mecze. 1 VS 1 gra tu we własnej lidze.",items)
        items=[cand(pid,(v["gf"]/v["m"])*18+v["gf"]*.6+v["big_wins"]*5+v["max_margin"]*2,f"{v['gf']/v['m']:.2f} gola strzelonego/mecz • {v['gf']} goli • {v['big_wins']} wygrane 3+") for pid,v in ps.items() if v["m"]>=2]
        add("offensive","🔥 Ofensywny Gracz Roku","Dla tych, którzy nie lubią wygrywać 1:0. Gole, gole i jeszcze raz gole.",items)
        items=[]
        for pid,v in ps.items():
            if v["m"]<3:continue
            ga_pm=v["ga"]/v["m"];cs_rate=v["clean_sheets"]/v["m"]*100
            score=110-ga_pm*25+min(v["m"],20)+cs_rate*.18+v["clean_sheets"]*1.5
            items.append(cand(pid,score,f"{ga_pm:.2f} gola straconego/mecz • {v['clean_sheets']} czystych kont • {v['ga']} straconych • {v['m']} meczów"))
        add("defense","🧱 Beton Roku","Tu gole wpuszcza się niechętnie, a najlepiej wcale.",items)
        items=[cand(pid,(v["clutch_w"]/v["clutch_m"]*100)+v["clutch_w"]*4,f"{v['clutch_w']}/{v['clutch_m']} wygranych w meczach clutch") for pid,v in ps.items() if v["clutch_m"]>=2]
        add("clutch","🎯 Clutch Player Roku","Najważniejsze są mecze bez marginesu błędu. Przegrywasz — kończy się droga po tytuł. Winners Bracket daje jeszcze drugie życie, więc tu nie wchodzi.",items)
        items=[cand(
            pid,
            (v["wc_w"]/v["wc_m"]*100)+((v["wc_gf"]-v["wc_ga"])/v["wc_m"])*5+v["wc_titles"]*18+v["wc_finals"]*7,
            f"WC: {v['wc_w']}/{v['wc_m']} W • bilans {v['wc_gf']}:{v['wc_ga']} • {v['wc_finals']} finał(y) WC • {v['wc_titles']} tytuł(y) WC"
        ) for pid,v in ps.items() if v["wc_m"]>=3]
        add("wildcards","🎲 Król Wild Cardów","Wild Card miał być niewiadomą. Niektórzy robią z niego broń.",items,award=False)
        items=[]
        for pid,v in ps.items():
            seq=v["result_points"]
            if len(seq)<6:continue
            mid=len(seq)//2;early=seq[:mid];late=seq[mid:]
            epts=sum(x[0] for x in early)/len(early);lpts=sum(x[0] for x in late)/len(late);egd=sum(x[1] for x in early)/len(early);lgd=sum(x[1] for x in late)/len(late)
            items.append(cand(pid,(lpts-epts)*30+(lgd-egd)*10,f"punkty/mecz {epts:.2f} → {lpts:.2f} • bilans bramek/mecz {egd:+.2f} → {lgd:+.2f}"))
        add("progress","📈 Największy Progres","Kto zaczął rok jednym graczem, a kończy go jak zupełnie inny zawodnik?",items,award=False)
        items=[]
        for pid,v in ps.items():
            vals=v["spectacle_scores"]
            if len(vals)<5:continue
            avg=sum(vals)/len(vals)
            spectacular=sum(1 for x in vals if x>=.75)
            spectacular_rate=spectacular/len(vals)
            score=avg*80+spectacular_rate*20
            avg_goals=v["spectacle_goals"]/len(vals)
            items.append(cand(pid,score,f"{avg_goals:.2f} gola/mecz w jego spotkaniach • {spectacular}/{len(vals)} bardzo widowiskowych • {v['spectacle_pens']} mecz(e) z karnymi"))
        add("spectacle","🎆 Najbardziej Widowiskowy Gracz","Jeśli gra, zwykle coś się dzieje. Gole, końcówki, karne — spokojne 1:0 mile widziane gdzie indziej. Minimum 5 meczów.",items)
        items=[]
        for pid,v in ps.items():
            vals=[tr["pts"]/tr["m"] for tr in v["t_results"].values() if tr["m"]]
            if len(vals)<3:continue
            avg=sum(vals)/len(vals);sd=statistics.pstdev(vals) if len(vals)>1 else 0
            items.append(cand(pid,avg*25-sd*14+len(vals),f"{len(vals)} turniejów • średnio {avg:.2f} pkt/mecz • odchylenie {sd:.2f}"))
        add("regular","🎯 Najbardziej Regularny","Bez wielkich zjazdów i przypadkowych wyskoków. Forma ma się zgadzać turniej po turnieju.",items,award=False)

        # Detailed-event Awards. These are official Award categories, unlike the
        # informational rankings below.
        items=[]
        for pid,v in discipline.items():
            if v["points"]<=0: continue
            items.append(cand(pid,v["points"],f"{v['points']} pkt dyscypliny • 🟨 {v['yellow']} • 🟥 {v['red']} (żółta = 1, czerwona = 3)"))
        add("sharpest","🪓 Najostrzejszy Gracz","Kartki mówią same za siebie. Im więcej koloru pokazuje sędzia, tym wyżej tutaj.",items)

        items=[]
        for pid,v in late_stats.items():
            if v["late_goals"]<=0: continue
            items.append({
                "id":str(pid),"name":name_by.get(str(pid),"?"),
                "score":float(v["late_goals"]),
                "_sort":(int(v["late_goals"]),int(v["goals_90plus"]),int(v["latest_value"])),
                "reason":f"{v['late_goals']} goli od 85. minuty • {v['goals_90plus']} od 90. minuty • najpóźniejszy {v['latest_label'] or '—'}"
            })
        add("late_king","⏰ Król Końcówek","Od 85. minuty zaczyna się jego ulubiona część meczu. Im później boli rywala, tym lepiej.",items)

        items=[]
        for pid,v in comeback_stats.items():
            if v["wins"]<=0: continue
            breakdown=", ".join(f"-{d}: {n}×" for d,n in sorted(v["from_deficits"].items(),reverse=True))
            items.append({
                "id":str(pid),"name":name_by.get(str(pid),"?"),"score":float(v["points"]),
                "_sort":(int(v["points"]),int(v["max_deficit"]),int(v["wins"])),
                "reason":f"{v['wins']} comeback win • {v['points']} pkt comebacku • największa odrobiona strata {v['max_deficit']} gola(e)"+(f" • {breakdown}" if breakdown else "")
            })
        add("comeback_king","🔄 Comeback King","Najpierw kłopoty, potem odrabianie. Liczymy zwycięstwa, w których trzeba było naprawdę wracać z daleka.",items)

        items=[]
        for pid,matches_n in detailed_matches_by_player.items():
            if matches_n<3: continue
            d=discipline[pid]; ppm=d["points"]/matches_n
            items.append({
                "id":str(pid),"name":name_by.get(str(pid),"?"),
                "score":round(100-ppm*20,4),"_sort":(-ppm,int(matches_n),-int(d["points"])),
                "reason":f"{d['points']} pkt dyscypliny w {matches_n} meczach • {ppm:.2f} pkt/mecz • 🟨 {d['yellow']} • 🟥 {d['red']}"
            })
        add("fair_play","😇 Fair Play","Da się wygrać bez koszenia wszystkiego, co się rusza. Minimum 3 mecze ze szczegółowym przebiegiem.",items)

        # Additional live rankings based on detailed EA FC event timelines.
        # They are informational and do not create an official Award winner.
        items=[cand(pid,v["penalties_awarded"],f"{v['penalties_awarded']} przyznanych karnych (trafione + niewykorzystane)")
               for pid,v in event_rank.items() if v["penalties_awarded"]>0]
        add("simulator","🎭 Największy symulant","Kto najczęściej słyszy gwizdek i od razu wskazanie na wapno? Liczymy karne w trakcie meczu.",items,award=False)
        items=[cand(pid,v["penalty_goals"],f"{v['penalty_goals']} goli z karnych")
               for pid,v in event_rank.items() if v["penalty_goals"]>0]
        add("penaldo","🐐 Penaldo","Ile razy wapno zamieniło się w gola. Serie po meczu zostają poza tą klasyfikacją.",items,award=False)
        items=[cand(pid,v["first_goals"],f"{v['first_goals']} razy strzelił pierwszy gol meczu")
               for pid,v in event_rank.items() if v["first_goals"]>0]
        add("first_goals","🥇 Najwięcej pierwszych goli","Kto najczęściej otwiera wynik. Techniczne 1:0 w finale DE oczywiście się nie wciska do statystyk.",items,award=False)
        items=[cand(pid,v["own_goals"],f"{v['own_goals']} samobój(e) jego drużyny")
               for pid,v in event_rank.items() if v["own_goals"]>0]
        add("own_goals","↩️ Samobóje","Czasem przeciwnik nawet nie musi strzelać. Techniczne 1:0 w finale DE się nie liczy.",items,award=False)
        items=[cand(pid,v["penalty_misses"],f"{v['penalty_misses']} niewykorzystany(e) karny(e)")
               for pid,v in event_rank.items() if v["penalty_misses"]>0]
        add("penalty_misses","❌🎯 Niewykorzystane karne","Wapno było. Gol już niekoniecznie. Serie po meczu zostają poza tą klasyfikacją.",items,award=False)

        first_by={str(x["player_id"]):str(x.get("first_date") or "") for x in first_dates}
        # Debiut Roku ma własną tożsamość: oceniamy wyłącznie początek kariery FIFA Night,
        # zamiast całorocznych wyników. Pokazujemy dwa niezależne rankingi (pierwsze 5 i 10
        # oficjalnych meczów turniejowych). Ranking pierwszych 10 jest główną podstawą nagrody;
        # pierwsze 5 daje kontekst, jak mocny był sam start.
        def debut_window(pid,n):
            seq=list(debut_seq.get(pid,[]))[:n]
            if len(seq)<n:return None
            w=sum(1 for x in seq if x["result"]=="W");d=sum(1 for x in seq if x["result"]=="D");l=n-w-d
            pts=sum(int(x["pts"]) for x in seq);gf=sum(int(x["gf"]) for x in seq);ga=sum(int(x["ga"]) for x in seq)
            wp=w/n*100;ppm=pts/n;gdpm=(gf-ga)/n
            semi_tids={x["tid"] for x in seq if x["stage"] in ("SF","WB_FINAL","LB_FINAL")}
            final_tids={x["tid"] for x in seq if x["stage"] in ("FINAL","RESET_FINAL")}
            title_tids=set()
            for x in seq:
                tid=x["tid"]
                if str(event_by.get(tid,{}).get("champion_player_id") or "")!=str(pid):continue
                closes_title=(x["stage"]=="RESET_FINAL") or (x["stage"]=="FINAL" and not has_reset_by_tid.get(tid,False))
                if closes_title and x["result"]=="W":title_tids.add(tid)
            # Wyniki dominują, osiągnięcia fazowe są dodatkiem. Dzięki temu Debiut Roku
            # nie staje się miniaturową kopią Gracza Roku opartą głównie na trofeach.
            score=wp*.35+ppm*15+gdpm*6+len(semi_tids)*3+len(final_tids)*7+len(title_tids)*12
            return {
                "id":str(pid),"name":name_by.get(str(pid),"?"),"score":round(float(score),2),
                "reason":f"{w}/{n} W • W% {wp:.1f} • {ppm:.2f} pkt/mecz • bilans {gf}:{ga} • {len(final_tids)} finał(y) • {len(title_tids)} tytuł(y)",
                "matches":n,"w":w,"d":d,"l":l,"win_pct":round(wp,1),"points_per_match":round(ppm,2),
                "gf":gf,"ga":ga,"gd":gf-ga,"deep_runs":len(semi_tids),"finals":len(final_tids),"titles":len(title_tids),
            }

        debut5=[];debut10=[]
        for pid in ps:
            if not first_by.get(pid,"").startswith(str(year)):continue
            r5=debut_window(pid,5);r10=debut_window(pid,10)
            if r5:debut5.append(r5)
            if r10:debut10.append(r10)
        if debut5 or debut10:
            primary=debut10 if debut10 else debut5
            add(
                "debut","🚀 Debiut Roku",
                "Pierwsze mecze pamięta się najlepiej. Patrzymy osobno na start po 5 i 10 oficjalnych spotkaniach.",
                primary
            )
            cats[-1]["debut_first5"]=top(debut5)
            cats[-1]["debut_first10"]=top(debut10)
            cats[-1]["debut_primary_window"]=10 if debut10 else 5
        items=[cand(pid,pc(pid,v)+v["w"]*2+(v["gf"]-v["ga"])*.4,f"maks. 1 tytuł • W% {pc(pid,v)} • {v['w']} W") for pid,v in ps.items() if v["m"]>=3 and v["titles"]<=1]
        add("outsider","🏅 Najlepszy spoza dominatorów","Dla tych, którzy jeszcze nie zapełnili półki pucharami, ale regularnie depczą liderom po piętach.",items)
        successful_teams=defaultdict(set)
        for (tid,pid),stages in stages_by_player_tournament.items():
            fmt=str(event_by.get(tid,{}).get("format_key") or "")
            team=" ".join(str(team_by.get((tid,pid),"") or "").split())
            if not team:continue
            if fmt.startswith("double"):
                success=bool(stages & {"WB_FINAL","LB_FINAL","FINAL","RESET_FINAL"})
            elif fmt.startswith("groups"):
                success=bool(stages & {"SF","FINAL","RESET_FINAL"})
            else:
                # Formaty ligowe nie mają wyjścia z grupy — sukces oznacza dojście do finału.
                success=bool(stages & {"FINAL","RESET_FINAL"})
            if success:
                successful_teams[pid].add(self._norm_team_name(team))
        items=[]
        for pid,v in ps.items():
            good=len(successful_teams.get(pid,set()))
            starts=len(participant_tournaments[pid])
            if len(v["teams"])>=2:
                items.append(cand(
                    pid,
                    good*12+len(v["teams"])*5+pc(pid,v)*.25,
                    f"różne drużyny: {len(v['teams'])} • z sukcesem: {good} • starty: {starts} • W% {pc(pid,v)}"
                ))
        add(
            "universal",
            "🔄 Najbardziej Uniwersalny Gracz",
            "Liczy się gra różnymi drużynami i to, jak daleko gracz potrafił nimi dojść w turnieju.",
            items
        )
        items=[]
        for (pid,sn),goals in scorer_by_player.items():
            pair_key=(pid,sn)
            scorer=scorer_pair_display.get(pair_key,sn)
            player=name_by.get(pid,"?")
            pair_teams=scorer_pair_teams.get(pair_key,set())
            team_matches=sum(int(ps[pid]["teams"].get(nt,{}).get("m",0)) for nt in pair_teams)
            if not team_matches:
                team_matches=ps[pid]["m"]
            hattricks=scorer_pair_hattricks.get(pair_key,0)
            team_names=sorted(scorer_pair_team_display.get(pair_key,set()))
            team_txt=(team_names[0] if len(team_names)==1 else (" / ".join(team_names) if team_names else "drużyną strzelca"))
            items.append({
                "id":f"{pid}|{sn}","name":f"{scorer} — {player}","score":goals,
                "_sort":(goals,-team_matches,hattricks,str(scorer).casefold()),
                "reason":f"{goals} goli • {team_matches} meczów {team_txt} • {hattricks} hat-trick(i) • gracz: {player}"
            })
        add("player_scorers","👟 Król Strzelców FIFA Night","Kto znalazł swojego napastnika idealnego? Liczymy gole konkretnego piłkarza zdobyte dla konkretnego gracza FIFA Night.",items)
        # finance for events completed this year
        finance=defaultdict(lambda:{"paid":0,"won":0})
        year_ids=set(tids)
        for e in finance_ledger:
            if str(e.get("id")) not in year_ids:continue
            stake=int(e.get("stake_cents") or 0)
            for pid in e.get("cash_player_ids") or []:finance[str(pid)]["paid"]+=stake
            if e.get("prize_winner_player_id"):finance[str(e["prize_winner_player_id"])]["won"]+=int(e.get("prize_cents") or 0)
        fin_items=[]
        for pid,v in finance.items():
            bal=v["won"]-v["paid"];fin_items.append(cand(pid,bal/100,f"bilans {(bal/100):+.2f} zł • wygrane {v['won']/100:.2f} zł • wpłaty {v['paid']/100:.2f} zł"))
        sponsor=min(fin_items,key=lambda x:x["score"],default=None)
        add("finance","🦈 Rekin Finansowy","Kto najlepiej wyszedł na FIFA Night w złotówkach? Na drugim końcu czeka honorowy Sponsor wieczorów.",fin_items,secondary=sponsor)
        # duel king
        dv=defaultdict(lambda:{"m":0,"w":0,"gf":0,"ga":0})
        for m in matches:
            if str(m["tournament_id"]) not in duel_ids:continue
            for pid,gf,ga in ((str(m["home_player_id"]),int(m["home_score"]),int(m["away_score"])),(str(m["away_player_id"]),int(m["away_score"]),int(m["home_score"]))):
                dv[pid]["m"]+=1;dv[pid]["gf"]+=gf;dv[pid]["ga"]+=ga;dv[pid]["w"]+=int(m.get("winner_player_id")==pid)
        items=[cand(pid,v["w"]/v["m"]*100+v["w"]*3+(v["gf"]-v["ga"])/v["m"]*2,f"{v['w']}/{v['m']} W • bilans {v['gf']}:{v['ga']}") for pid,v in dv.items() if v["m"]>=5]
        add("duel","⚔️ Król 1 vs 1","Bez grup, bez drabinki, bez wymówek. Tylko oficjalne 1 VS 1; minimum 5 spotkań.",items,award=False)
        # non-individual categories
        rivalry=[]
        for (a,b),v in pair.items():
            if v["n"]<3:continue
            balance=1-abs(v["aw"]-v["bw"])/max(1,v["n"]);score=v["n"]*5+balance*20+v["importance_points"]*2
            na,nb=v["names"] or (name_by.get(a,"?"),name_by.get(b,"?"));rivalry.append({"id":f"{a}|{b}","name":f"{na} vs {nb}","score":round(score,2),"reason":f"{v['n']} meczów • {v['aw']}:{v['bw']} w zwycięstwach • ważne mecze {v['important_matches']}"})
        add("rivalry","⚔️ Rywalizacja Roku","Są pary, które po prostu lubią na siebie wpadać. Minimum 3 bezpośrednie mecze w roku.",rivalry)
        teamitems=[]
        for nt,v in teamagg.items():
            if not v["m"]:continue
            raw=(v["w"]*3+v["d"])/(v["m"]*3);shrink=v["m"]/(v["m"]+6);gdpm=(v["gf"]-v["ga"])/v["m"]
            rating=50+(raw*100-50)*shrink*.8+max(-10,min(10,gdpm*3))*shrink+v["titles"]*3
            teamitems.append({"id":nt,"name":v["display"] or nt,"score":round(rating,2),"reason":f"rating {rating:.1f} • {v['w']}/{v['m']} W • {v['titles']} tytuł(y) • {v['gf']}:{v['ga']}"})
        worst=[{**x,"score":100-float(x["score"])} for x in teamitems]
        worst_team=top(worst,1)[0] if worst else None
        add("team_best","🏟️ Drużyny Roku","Który klub najlepiej służył graczom FIFA Night — i który zdecydowanie mniej? Wyniki mówią swoje.",teamitems,secondary=worst_team)
        scorer_items=[{"id":sn,"name":scorer_display.get(sn,sn),"score":goals,"reason":f"{goals} wpisanych goli łącznie"} for sn,goals in scorer_totals.items() if goals>=5]
        add("superscorer","⚡ Supersnajper Roku","Jedno nazwisko, mnóstwo bramek. Liczymy wszystkie wpisane gole piłkarza w oficjalnych meczach.",scorer_items)
        add("match_year","🎬 Mecz Roku","Taki mecz, o którym jeszcze długo ktoś będzie mówił: „pamiętasz to…?”.",match_candidates)
        items=[cand(pid,v["one_goal_wins"],f"{v['one_goal_wins']} zwycięstw dokładnie jedną bramką") for pid,v in ps.items() if v["one_goal_wins"]>0]
        add("minimalist","📐 Król Minimalistów","Po co strzelać pięć, skoro jedna bramka przewagi też daje zwycięstwo?",items,award=False)
        items=[cand(pid,v["narrow_losses"],f"{v['narrow_losses']} minimalnych porażek / porażek po karnych") for pid,v in ps.items() if v["narrow_losses"]>0]
        add("unlucky","🤕 Pechowiec Roku","Prawie się nie liczy. Statystyki i tak pamiętają każdą porażkę o włos.",items,award=False)

        # Summary of participant nominations across individual award categories.
        # Count a category at most once per player. Team/match/rivalry/EA-player
        # categories are intentionally excluded because the nominee is not one FIFA Night participant.
        direct_player_awards={
            "player_year","offensive","defense","clutch","sharpest","late_king","comeback_king","fair_play",
            "spectacle","debut","outsider","universal","finance"
        }
        nomination_sets=defaultdict(lambda:{"top2":set(),"top3":set(),"top5":set(),"first":set()})
        nomination_titles_top2=defaultdict(set)
        for cat in cats:
            if not cat.get("award"):continue
            key=str(cat.get("key") or "")
            candidates=cat.get("candidates") or []
            mapped=[]
            if key in direct_player_awards:
                mapped=[(str(x.get("id") or ""),x) for x in candidates]
            elif key=="player_scorers":
                # Candidate is footballer + participant; credit the nomination to the FIFA Night participant.
                mapped=[(str(x.get("id") or "").split("|",1)[0],x) for x in candidates]
            else:
                continue
            for pos,(pid,x) in enumerate(mapped[:5],1):
                if not pid or pid not in name_by:continue
                nomination_sets[pid]["top5"].add(key)
                if pos<=3:nomination_sets[pid]["top3"].add(key)
                if pos<=2:
                    nomination_sets[pid]["top2"].add(key)
                    nomination_titles_top2[pid].add(str(cat.get("title") or key))
                if pos==1:nomination_sets[pid]["first"].add(key)
        nomination_summary=[]
        for pid,v in nomination_sets.items():
            nomination_summary.append({
                "player_id":pid,
                "name":name_by.get(pid,"?"),
                "top2":len(v["top2"]),
                "top3":len(v["top3"]),
                "top5":len(v["top5"]),
                "first":len(v["first"]),
                "categories_top2":sorted(nomination_titles_top2.get(pid,set())),
            })
        nomination_summary.sort(key=lambda x:(x["top3"],x["top5"],x["first"],x["name"]),reverse=True)

        overview={"tournaments":len(tournament_ids),"duels":len(duel_ids),"matches":len(matches),"goals":sum(int(m["home_score"])+int(m["away_score"]) for m in matches),
                  "players":len({str(r["player_id"]) for r in tps}),"titles":len(completed_tournament_ids),"top_player":(cats[0]["candidates"][0]["name"] if cats and cats[0]["candidates"] else None),
                  "top_team":(next((c for c in cats if c["key"]=="team_best"),{}).get("candidates") or [{}])[0].get("name") if teamitems else None}
        return {"year":year,"categories":cats,"overview":overview,"selections":self.award_selections(year),"nomination_summary":nomination_summary}

    def all_time_stats(self) -> list[dict]:
        """Shared official stats. Duels count as matches, never as tournament titles/finals."""
        with self.connect() as conn:
            events=self._fetchall(conn,"""SELECT t.id,t.status,t.champion_player_id,fm.format_key
                FROM tournaments t JOIN flex_tournament_meta fm ON fm.tournament_id=t.id
                WHERE t.status IN ('completed','abandoned') AND t.is_test=0""")
            if not events: return []
            all_ids={str(r["id"]) for r in events}
            tournament_ids={str(r["id"]) for r in events if str(r.get("format_key") or "")!='duel1v1'}
            completed_tournament_ids={str(r["id"]) for r in events if str(r.get("format_key") or "")!='duel1v1' and str(r.get("status") or "")=="completed"}
            players={r["id"]:r["name"] for r in self._fetchall(conn,"SELECT id,name FROM players")}
            tps=self._fetchall(conn,"SELECT tournament_id,player_id FROM tournament_players")
            matches=self._fetchall(conn,"SELECT * FROM matches WHERE home_score IS NOT NULL ORDER BY tournament_id,match_no")
        finals=[m for m in matches if m["stage"]=="FINAL" and str(m["tournament_id"]) in completed_tournament_ids]
        stats=defaultdict(lambda:{"tournaments":0,"titles":0,"finals":0,"w":0,"d":0,"l":0,"gf":0,"ga":0,"pen_wins":0,"duels":0,"duel_wins":0})
        for tp in tps:
            tid=str(tp["tournament_id"]); pid=tp["player_id"]
            if tid in tournament_ids: stats[pid]["tournaments"]+=1
            if tid in all_ids and tid not in tournament_ids: stats[pid]["duels"]+=1
        for t in events:
            if str(t["id"]) in completed_tournament_ids and t.get("champion_player_id"): stats[t["champion_player_id"]]["titles"]+=1
        for m in finals:
            if m.get("home_player_id"): stats[m["home_player_id"]]["finals"]+=1
            if m.get("away_player_id"): stats[m["away_player_id"]]["finals"]+=1
        for m in matches:
            tid=str(m["tournament_id"])
            if tid not in all_ids: continue
            h,a=m["home_player_id"],m["away_player_id"]; hs,ass=int(m["home_score"]),int(m["away_score"])
            if not h or not a: continue
            stats[h]["gf"]+=hs; stats[h]["ga"]+=ass; stats[a]["gf"]+=ass; stats[a]["ga"]+=hs
            if hs>ass: stats[h]["w"]+=1; stats[a]["l"]+=1
            elif ass>hs: stats[a]["w"]+=1; stats[h]["l"]+=1
            else:
                stats[h]["d"]+=1; stats[a]["d"]+=1
                if m.get("winner_player_id"): stats[m["winner_player_id"]]["pen_wins"]+=1
            if tid not in tournament_ids and m.get("winner_player_id"):
                stats[m["winner_player_id"]]["duel_wins"]+=1
        out=[]
        for pid,v in stats.items():
            played=v["w"]+v["d"]+v["l"]
            if not played: continue
            out.append({"player_id":pid,"name":players.get(pid,"?"),**v,"gd":v["gf"]-v["ga"],"matches":played,"win_pct":round(v["w"]/played*100,1) if played else 0.0})
        out.sort(key=lambda x:(x["titles"],x["w"],x["gd"],x["gf"]),reverse=True); return out


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

DB_API_VERSION = 1800
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
            settings=self._fetchall(conn,"SELECT key,value FROM app_settings WHERE key LIKE 'flex_last_lineup_%'")
            for row in settings:
                try: values=json.loads(row.get("value") or "[]")
                except Exception: continue
                if not isinstance(values,list): continue
                replaced=[clean if str(v).strip().casefold()==old_name.strip().casefold() else v for v in values]
                if replaced!=values:
                    self._setting_set_conn(conn,row["key"],json.dumps(replaced,ensure_ascii=False))

            # Organizer-selected award names are stored as display snapshots. Refresh the
            # categories where a participant name is embedded in that snapshot.
            award_rows=self._fetchall(conn,"SELECT key,value FROM app_settings WHERE key LIKE 'flex_award_selections_%'")
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
            WHERE t.status='completed' AND t.is_test=0 AND m.home_score IS NOT NULL
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
                WHERE t.status='completed' AND t.is_test=0 AND m.home_score IS NOT NULL
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
        draft_mode = player_count in (3,4,5)
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

    def create_duel(self, player_names: list[str], team_names: list[str], is_test: bool, stake_per_player: float = 0.0,
                    cash_flags: list[bool] | None = None) -> str:
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
        trs=self._fetchall(conn,f"""SELECT t.id,t.champion_player_id,t.completed_at,t.created_at,fm.format_key
            FROM tournaments t LEFT JOIN flex_tournament_meta fm ON fm.tournament_id=t.id
            WHERE t.id IN ({qmarks}) ORDER BY COALESCE(t.completed_at,t.created_at)""",tuple(tids))
        tournament_ids={str(r["id"]) for r in trs if str(r.get("format_key") or "")!='duel1v1'}
        tps=self._fetchall(conn,f"SELECT tournament_id,player_id FROM tournament_players WHERE tournament_id IN ({qmarks})",tuple(tids))
        players={r["id"]:r["name"] for r in self._fetchall(conn,"SELECT id,name FROM players")}
        finals=[m for m in matches if m["stage"]=="FINAL" and str(m["tournament_id"]) in tournament_ids]
        ps=defaultdict(lambda:{"tournaments":0,"titles":0,"finals":0,"w":0,"d":0,"l":0,"gf":0,"ga":0})
        for tp in tps:
            if str(tp["tournament_id"]) in tournament_ids: ps[tp["player_id"]]["tournaments"]+=1
        for t in trs:
            if str(t["id"]) in tournament_ids and t.get("champion_player_id"): ps[t["champion_player_id"]]["titles"]+=1
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
                    WHERE t.status='completed' AND t.is_test=0 AND fm.format_key<>'duel1v1'
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

    def save_result(self, tid: str, match_no: int, hs: int, ass: int, hp: int | None = None, ap: int | None = None, scorers: dict | None = None) -> None:
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
                WHERE t.status='completed' AND t.is_test=0 AND fm.format_key<>'duel1v1'
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

    def last_completed_tournament(self) -> dict | None:
        with self.connect() as conn:
            t=self._fetchone(conn,"""SELECT t.id,t.created_at,t.completed_at,t.champion_player_id,p.name champion_name
                FROM tournaments t LEFT JOIN players p ON p.id=t.champion_player_id
                WHERE t.status='completed' AND t.is_test=0
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
            events=self._fetchall(conn,"""SELECT t.id,t.champion_player_id,t.completed_at,t.created_at,fm.format_key
                FROM tournaments t JOIN flex_tournament_meta fm ON fm.tournament_id=t.id
                WHERE t.status='completed' AND t.is_test=0 AND COALESCE(t.completed_at,t.created_at) LIKE ?
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
            first_dates=self._fetchall(conn,"""SELECT tp.player_id,MIN(COALESCE(t.completed_at,t.created_at)) AS first_date
                FROM tournament_players tp JOIN tournaments t ON t.id=tp.tournament_id
                WHERE t.status='completed' AND t.is_test=0 GROUP BY tp.player_id""")
            finance_ledger,finance_names,_jp=self._finance_ledger_conn(conn)
            placements={tid:self._placement_order_conn(conn,tid) for tid in tids}

        event_by={str(e["id"]):e for e in events}; tournament_ids={tid for tid,e in event_by.items() if str(e.get("format_key"))!='duel1v1'}
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
                               "result_points":[],"t_results":defaultdict(lambda:{"m":0,"pts":0,"gf":0,"ga":0}),"scorer_goals":0})
        clutch_stages={"QF","BARRAGE","SF","WB","WB_FINAL","LB","LB_FINAL","FINAL"}
        pair=defaultdict(lambda:{"n":0,"aw":0,"bw":0,"d":0,"important_matches":0,"importance_points":0,"names":None})
        teamagg=defaultdict(lambda:{"display":None,"m":0,"w":0,"d":0,"l":0,"gf":0,"ga":0,"titles":0})
        match_candidates=[]
        match_map={(str(m["tournament_id"]),int(m["match_no"])):m for m in matches}

        for e in events:
            tid=str(e["id"]); champ=str(e.get("champion_player_id") or "")
            if tid in tournament_ids and champ: ps[champ]["titles"]+=1
        for tid in tournament_ids:
            finals=[m for m in matches if str(m["tournament_id"])==tid and m.get("stage")=="FINAL"]
            if finals:
                f=finals[-1]
                for pid in (f.get("home_player_id"),f.get("away_player_id")):
                    if pid:ps[str(pid)]["finals"]+=1

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
            for pid,team,gf,ga,r in ((h,m.get("home_team"),hs,ass,rh),(a,m.get("away_team"),ass,hs,ra)):
                v=ps[pid];v["m"]+=1;v["gf"]+=gf;v["ga"]+=ga;v["clean_sheets"]+=int(ga==0);v[{"W":"w","D":"d","L":"l"}[r]]+=1
                pts=3 if r=="W" else (1 if r=="D" else 0);v["result_points"].append((pts,gf-ga))
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
                closeness=.96; closeness_text="remis"
            elif margin==1:
                closeness=1.00; closeness_text="różnica 1 gola"
            elif margin==2:
                closeness=.66; closeness_text="różnica 2 goli"
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

            # Dominują bliskość i stawka. Dzięki temu jednostronny finał nie dostaje
            # automatycznie wysokiego miejsca tylko dlatego, że był finałem.
            match_score=closeness*.46 + stakes*.34 + rank_value*.12 + goals_value*.08
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
                    scorer_by_player[(pid,sn)]+=goals
                    scorer_pair_display.setdefault((pid,sn),scorer)

        def pc(pid,v):return round(v["w"]/v["m"]*100,1) if v["m"] else 0.0
        def cand(pid,score,reason):return {"id":str(pid),"name":name_by.get(str(pid),"?"),"score":round(float(score),2),"reason":reason}
        def top(items,n=5):return sorted(items,key=lambda x:(float(x.get("score") or 0),str(x.get("name") or "")),reverse=True)[:n]
        cats=[]
        def add(key,title,desc,items,award=True,secondary=None):cats.append({"key":key,"title":title,"description":desc,"award":award,"candidates":top(items),"secondary":secondary})

        # 1 player of year
        items=[]
        for pid,v in ps.items():
            if v["m"]<2:continue
            wp=pc(pid,v);cl=(v["clutch_w"]/v["clutch_m"]*100 if v["clutch_m"] else 0);gdpm=(v["gf"]-v["ga"])/v["m"]
            score=v["titles"]*32+v["finals"]*11+wp*.28+cl*.11+gdpm*4+len(participant_tournaments[pid])
            items.append(cand(pid,score,f"{v['titles']} tytuł(y), {v['finals']} finał(y), W% {wp}, bilans {v['gf']}:{v['ga']}"))
        add("player_year","🏆 Gracz Roku","Całokształt: tytuły, finały, wyniki, bilans, regularność i ważne mecze. 1v1 nie wchodzi do tej kategorii.",items)
        items=[cand(pid,(v["gf"]/v["m"])*18+v["gf"]*.6+v["big_wins"]*5+v["max_margin"]*2,f"{v['gf']/v['m']:.2f} gola strzelonego/mecz • {v['gf']} goli • {v['big_wins']} wygrane 3+") for pid,v in ps.items() if v["m"]>=2]
        add("offensive","🔥 Ofensywny Gracz Roku","Gole strzelone na mecz, łączna liczba goli, wysokie zwycięstwa i największe wygrane.",items)
        items=[]
        for pid,v in ps.items():
            if v["m"]<3:continue
            ga_pm=v["ga"]/v["m"];cs_rate=v["clean_sheets"]/v["m"]*100
            score=110-ga_pm*25+min(v["m"],20)+cs_rate*.18+v["clean_sheets"]*1.5
            items.append(cand(pid,score,f"{ga_pm:.2f} gola straconego/mecz • {v['clean_sheets']} czystych kont • {v['ga']} straconych • {v['m']} meczów"))
        add("defense","🧱 Beton Roku","Najlepsza defensywa: gole stracone na mecz, czyste konta, łączna liczba straconych goli i wielkość próby.",items)
        items=[cand(pid,(v["clutch_w"]/v["clutch_m"]*100)+v["clutch_w"]*4,f"{v['clutch_w']}/{v['clutch_m']} wygranych w meczach clutch") for pid,v in ps.items() if v["clutch_m"]>=2]
        add("clutch","🎯 Clutch Player Roku","Playoffy, półfinały, finały i mecze eliminacyjne Double Elimination.",items)
        items=[cand(pid,v["pen_w"]/v["pen"]*100+v["pen_w"]*3,f"{v['pen_w']}/{v['pen']} wygranych serii") for pid,v in ps.items() if v["pen"]>=3]
        add("penalties","🥅 Król Karnych","Tylko serie rzutów karnych; minimum 3 serie w roku.",items)
        items=[cand(pid,(v["wc_w"]/v["wc_m"]*100)+((v["wc_gf"]-v["wc_ga"])/v["wc_m"])*5+v["titles"]*5,f"WC: {v['wc_w']}/{v['wc_m']} W • bilans {v['wc_gf']}:{v['wc_ga']}") for pid,v in ps.items() if v["wc_m"]>=3]
        add("wildcards","🎲 Król Wild Cardów","W%, bilans i sukcesy podczas gry klubami z Wild Card.",items)
        items=[]
        for pid,v in ps.items():
            seq=v["result_points"]
            if len(seq)<6:continue
            mid=len(seq)//2;early=seq[:mid];late=seq[mid:]
            epts=sum(x[0] for x in early)/len(early);lpts=sum(x[0] for x in late)/len(late);egd=sum(x[1] for x in early)/len(early);lgd=sum(x[1] for x in late)/len(late)
            items.append(cand(pid,(lpts-epts)*30+(lgd-egd)*10,f"punkty/mecz {epts:.2f} → {lpts:.2f} • bilans bramek/mecz {egd:+.2f} → {lgd:+.2f}"))
        add("progress","📈 Największy Progres","Zmiana między wcześniejszą i późniejszą częścią roku; wymagana sensowna próba.",items)
        items=[]
        for pid,v in ps.items():
            vals=[tr["pts"]/tr["m"] for tr in v["t_results"].values() if tr["m"]]
            if len(vals)<3:continue
            avg=sum(vals)/len(vals);sd=statistics.pstdev(vals) if len(vals)>1 else 0
            items.append(cand(pid,avg*25-sd*14+len(vals),f"{len(vals)} turniejów • średnio {avg:.2f} pkt/mecz • odchylenie {sd:.2f}"))
        add("regular","🎯 Najbardziej Regularny","Stabilność wyników turniej po turnieju, z premią za dobry poziom.",items)
        first_by={str(x["player_id"]):str(x.get("first_date") or "") for x in first_dates}
        items=[cand(pid,v["w"]*4+pc(pid,v)*.4+v["titles"]*15,f"debiut {first_by.get(pid,'')[:10]} • {v['w']} W • W% {pc(pid,v)}") for pid,v in ps.items() if first_by.get(pid,"").startswith(str(year)) and len(participant_tournaments[pid])>=2]
        add("debut","🚀 Debiut Roku","Nowi uczestnicy, którzy zaczęli oficjalną historię w tym roku i zebrali wystarczającą próbę.",items)
        items=[cand(pid,pc(pid,v)+v["w"]*2+(v["gf"]-v["ga"])*.4,f"maks. 1 tytuł • W% {pc(pid,v)} • {v['w']} W") for pid,v in ps.items() if v["m"]>=3 and v["titles"]<=1]
        add("outsider","🏅 Najlepszy spoza dominatorów","Ranking graczy z maksymalnie jednym wygranym turniejem.",items)
        items=[]
        for pid,v in ps.items():
            good=sum(1 for tv in v["teams"].values() if tv["m"]>=2 and tv["w"]/tv["m"]>=.4)
            starts=len(participant_tournaments[pid])
            if len(v["teams"])>=2:
                items.append(cand(
                    pid,
                    good*12+len(v["teams"])*5+pc(pid,v)*.25,
                    f"różne drużyny: {len(v['teams'])} • spełniają próg: {good} • starty: {starts} • W% {pc(pid,v)}"
                ))
        add(
            "universal",
            "🔄 Najbardziej Uniwersalny Gracz",
            "Premia za dobre wyniki wieloma różnymi drużynami. Ranking nie liczy proporcji typu 2/2; premiuje liczbę różnych drużyn spełniających próg (min. 2 mecze i W% ≥ 40%), szerokość puli oraz ogólne W%. „Starty” to liczba rozegranych turniejów.",
            items
        )
        items=[]
        for (pid,sn),goals in scorer_by_player.items():
            scorer=scorer_pair_display.get((pid,sn),sn)
            player=name_by.get(pid,"?")
            items.append({"id":f"{pid}|{sn}","name":f"{scorer} — {player}","score":goals,
                          "reason":f"{goals} goli • gracz: {player}"})
        add("player_scorers","👟 Król Strzelców FIFA Night","Konkretny piłkarz przypisany do konkretnego gracza. Liczy się największa liczba jego goli dla jednej osoby — nie suma wszystkich strzelców gracza.",items)
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
        add("finance","🦈 Rekin Finansowy","Największy dodatni bilans finansowy roku. Sponsor FIFA Night jest pokazany dodatkowo jako największy bilans ujemny.",fin_items,secondary=sponsor)
        # duel king
        dv=defaultdict(lambda:{"m":0,"w":0,"gf":0,"ga":0})
        for m in matches:
            if str(m["tournament_id"]) not in duel_ids:continue
            for pid,gf,ga in ((str(m["home_player_id"]),int(m["home_score"]),int(m["away_score"])),(str(m["away_player_id"]),int(m["away_score"]),int(m["home_score"]))):
                dv[pid]["m"]+=1;dv[pid]["gf"]+=gf;dv[pid]["ga"]+=ga;dv[pid]["w"]+=int(m.get("winner_player_id")==pid)
        items=[cand(pid,v["w"]/v["m"]*100+v["w"]*3+(v["gf"]-v["ga"])/v["m"]*2,f"{v['w']}/{v['m']} W • bilans {v['gf']}:{v['ga']}") for pid,v in dv.items() if v["m"]>=5]
        add("duel","⚔️ Król 1 vs 1","Wyłącznie oficjalne mecze 1v1; minimum 5 spotkań.",items)
        # non-individual categories
        rivalry=[]
        for (a,b),v in pair.items():
            if v["n"]<3:continue
            balance=1-abs(v["aw"]-v["bw"])/max(1,v["n"]);score=v["n"]*5+balance*20+v["importance_points"]*2
            na,nb=v["names"] or (name_by.get(a,"?"),name_by.get(b,"?"));rivalry.append({"id":f"{a}|{b}","name":f"{na} vs {nb}","score":round(score,2),"reason":f"{v['n']} meczów • {v['aw']}:{v['bw']} w zwycięstwach • ważne mecze {v['important_matches']}"})
        add("rivalry","⚔️ Rywalizacja Roku","Minimum 3 bezpośrednie mecze w roku. Ranking premiuje częstotliwość H2H, wyrównany bilans zwycięstw i spotkania o wysokiej randze (finał > półfinał > QF/baraż/WB/LB).",rivalry)
        teamitems=[]
        for nt,v in teamagg.items():
            if not v["m"]:continue
            raw=(v["w"]*3+v["d"])/(v["m"]*3);shrink=v["m"]/(v["m"]+6);gdpm=(v["gf"]-v["ga"])/v["m"]
            rating=50+(raw*100-50)*shrink*.8+max(-10,min(10,gdpm*3))*shrink+v["titles"]*3
            teamitems.append({"id":nt,"name":v["display"] or nt,"score":round(rating,2),"reason":f"rating {rating:.1f} • {v['w']}/{v['m']} W • {v['titles']} tytuł(y) • {v['gf']}:{v['ga']}"})
        add("team_best","🏟️ Drużyna Roku","Najlepszy klub wg wyników, próby, bilansu i tytułów.",teamitems)
        worst=[{**x,"score":100-float(x["score"])} for x in teamitems]
        add("team_worst","📉 Najgorsza Drużyna Roku","Najsłabszy klub wg tej samej bazy danych co Drużyna Roku.",worst)
        scorer_items=[{"id":sn,"name":scorer_display.get(sn,sn),"score":goals,"reason":f"{goals} wpisanych goli łącznie"} for sn,goals in scorer_totals.items() if goals>=5]
        add("superscorer","⚡ Supersnajper Roku","Konkretny piłkarz z EA FC z największą liczbą wpisanych goli; kategoria pojawia się przy sensownej próbie.",scorer_items)
        add("match_year","🎬 Mecz Roku","Ranking stawia przede wszystkim na bliskość wyniku i stawkę spotkania (np. czy przegrany odpadał albo był to mecz o tytuł). Ranga fazy i liczba goli pomagają rozstrzygać kolejność, ale nie dominują rankingu. Punkty techniczne nie są pokazywane.",match_candidates)
        items=[cand(pid,v["one_goal_wins"],f"{v['one_goal_wins']} zwycięstw dokładnie jedną bramką") for pid,v in ps.items() if v["one_goal_wins"]>0]
        add("minimalist","📐 Król Minimalistów","Najwięcej zwycięstw dokładnie jedną bramką.",items,award=False)
        items=[cand(pid,v["narrow_losses"],f"{v['narrow_losses']} minimalnych porażek / porażek po karnych") for pid,v in ps.items() if v["narrow_losses"]>0]
        add("unlucky","🤕 Pechowiec Roku","Najwięcej minimalnych porażek jedną bramką lub po karnych.",items,award=False)

        # Summary of participant nominations across individual award categories.
        # Count a category at most once per player. Team/match/rivalry/EA-player
        # categories are intentionally excluded because the nominee is not one FIFA Night participant.
        direct_player_awards={
            "player_year","offensive","defense","clutch","penalties","wildcards",
            "progress","regular","debut","outsider","universal","finance","duel"
        }
        nomination_sets=defaultdict(lambda:{"top3":set(),"top5":set(),"first":set()})
        nomination_titles=defaultdict(set)
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
                nomination_titles[pid].add(str(cat.get("title") or key))
                if pos<=3:nomination_sets[pid]["top3"].add(key)
                if pos==1:nomination_sets[pid]["first"].add(key)
        nomination_summary=[]
        for pid,v in nomination_sets.items():
            nomination_summary.append({
                "player_id":pid,
                "name":name_by.get(pid,"?"),
                "top3":len(v["top3"]),
                "top5":len(v["top5"]),
                "first":len(v["first"]),
                "categories":sorted(nomination_titles.get(pid,set())),
            })
        nomination_summary.sort(key=lambda x:(x["top3"],x["top5"],x["first"],x["name"]),reverse=True)

        overview={"tournaments":len(tournament_ids),"duels":len(duel_ids),"matches":len(matches),"goals":sum(int(m["home_score"])+int(m["away_score"]) for m in matches),
                  "players":len({str(r["player_id"]) for r in tps}),"titles":len(tournament_ids),"top_player":(cats[0]["candidates"][0]["name"] if cats and cats[0]["candidates"] else None),
                  "top_team":(next((c for c in cats if c["key"]=="team_best"),{}).get("candidates") or [{}])[0].get("name") if teamitems else None}
        return {"year":year,"categories":cats,"overview":overview,"selections":self.award_selections(year),"nomination_summary":nomination_summary}

    def all_time_stats(self) -> list[dict]:
        """Shared official stats. Duels count as matches, never as tournament titles/finals."""
        with self.connect() as conn:
            events=self._fetchall(conn,"""SELECT t.id,t.champion_player_id,fm.format_key
                FROM tournaments t JOIN flex_tournament_meta fm ON fm.tournament_id=t.id
                WHERE t.status='completed' AND t.is_test=0""")
            if not events: return []
            all_ids={str(r["id"]) for r in events}
            tournament_ids={str(r["id"]) for r in events if str(r.get("format_key") or "")!='duel1v1'}
            players={r["id"]:r["name"] for r in self._fetchall(conn,"SELECT id,name FROM players")}
            tps=self._fetchall(conn,"SELECT tournament_id,player_id FROM tournament_players")
            matches=self._fetchall(conn,"SELECT * FROM matches WHERE home_score IS NOT NULL ORDER BY tournament_id,match_no")
        finals=[m for m in matches if m["stage"]=="FINAL" and str(m["tournament_id"]) in tournament_ids]
        stats=defaultdict(lambda:{"tournaments":0,"titles":0,"finals":0,"w":0,"d":0,"l":0,"gf":0,"ga":0,"pen_wins":0,"duels":0,"duel_wins":0})
        for tp in tps:
            tid=str(tp["tournament_id"]); pid=tp["player_id"]
            if tid in tournament_ids: stats[pid]["tournaments"]+=1
            if tid in all_ids and tid not in tournament_ids: stats[pid]["duels"]+=1
        for t in events:
            if str(t["id"]) in tournament_ids and t.get("champion_player_id"): stats[t["champion_player_id"]]["titles"]+=1
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


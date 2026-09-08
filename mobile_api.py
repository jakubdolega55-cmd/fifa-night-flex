from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import secrets
import time
from datetime import datetime, timezone
from typing import Any

from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from database import Database
from logic import FORMAT_LABELS, FORMAT_MATCH_COUNTS

API_VERSION = "0.1.0"
TOKEN_TTL_SECONDS = 30 * 24 * 60 * 60

STAGE_LABELS = {
    "DUEL": "1 VS 1",
    "GROUP": "GRUPA",
    "LEAGUE": "LIGA",
    "WB": "DRABINKA WYGRANYCH",
    "WB_FINAL": "FINAŁ WINNERS",
    "LB": "DRABINKA PRZEGRANYCH",
    "LB_FINAL": "FINAŁ LOSERS",
    "QF": "ĆWIERĆFINAŁ",
    "BARRAGE": "BARAŻ",
    "SF": "PÓŁFINAŁ",
    "FINAL": "FINAŁ",
    "RESET_FINAL": "RESET FINAL",
}

app = FastAPI(title="FIFA Night Mobile API", version=API_VERSION)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

db = Database()


@app.on_event("startup")
def startup() -> None:
    db.init_schema()


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _admin_password() -> str:
    return str(os.getenv("ADMIN_PASSWORD") or "")


def _token_secret() -> str:
    return str(os.getenv("MOBILE_TOKEN_SECRET") or _admin_password())


def _b64encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("ascii").rstrip("=")


def _b64decode(data: str) -> bytes:
    return base64.urlsafe_b64decode(data + "=" * (-len(data) % 4))


def issue_controller_token() -> tuple[str, int]:
    secret = _token_secret()
    if not secret:
        raise HTTPException(503, "Sterowanie nie jest skonfigurowane na serwerze.")
    now = int(time.time())
    payload = {
        "scope": "controller",
        "iat": now,
        "exp": now + TOKEN_TTL_SECONDS,
        "nonce": secrets.token_hex(8),
    }
    encoded = _b64encode(json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8"))
    signature = _b64encode(hmac.new(secret.encode("utf-8"), encoded.encode("ascii"), hashlib.sha256).digest())
    return f"{encoded}.{signature}", int(payload["exp"])


def verify_controller_token(token: str) -> dict[str, Any]:
    secret = _token_secret()
    if not secret or "." not in token:
        raise HTTPException(401, "Brak dostępu do sterowania.")
    encoded, signature = token.split(".", 1)
    expected = _b64encode(hmac.new(secret.encode("utf-8"), encoded.encode("ascii"), hashlib.sha256).digest())
    if not hmac.compare_digest(signature, expected):
        raise HTTPException(401, "Sesja sterowania jest nieprawidłowa.")
    try:
        payload = json.loads(_b64decode(encoded).decode("utf-8"))
    except Exception as exc:
        raise HTTPException(401, "Sesja sterowania jest nieprawidłowa.") from exc
    if payload.get("scope") != "controller" or int(payload.get("exp") or 0) <= int(time.time()):
        raise HTTPException(401, "Sesja sterowania wygasła.")
    return payload


def require_controller(authorization: str | None = Header(default=None)) -> dict[str, Any]:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(401, "To urządzenie jest w trybie podglądu.")
    return verify_controller_token(authorization.split(" ", 1)[1].strip())


class ControllerLogin(BaseModel):
    password: str = Field(min_length=1, max_length=256)


class ScorerItem(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    goals: int = Field(ge=1, le=20)


class ScorerSide(BaseModel):
    team: str = Field(default="", max_length=120)
    items: list[ScorerItem] = Field(default_factory=list, max_length=8)


class ScorersPayload(BaseModel):
    home: ScorerSide | None = None
    away: ScorerSide | None = None


class ResultPayload(BaseModel):
    home_score: int = Field(ge=0, le=99)
    away_score: int = Field(ge=0, le=99)
    home_penalties: int | None = Field(default=None, ge=0, le=30)
    away_penalties: int | None = Field(default=None, ge=0, le=30)
    scorers: ScorersPayload | None = None


def stage_label(match: dict[str, Any]) -> str:
    stage = str(match.get("stage") or "")
    if stage == "GROUP":
        return f"GRUPA {match.get('group_name') or ''}".strip()
    return STAGE_LABELS.get(stage, stage)


def clean_match(match: dict[str, Any]) -> dict[str, Any]:
    return {
        "match_no": int(match.get("match_no") or 0),
        "stage": match.get("stage"),
        "stage_label": stage_label(match),
        "group_name": match.get("group_name"),
        "home_player_id": match.get("home_player_id"),
        "away_player_id": match.get("away_player_id"),
        "home_name": match.get("home_name"),
        "away_name": match.get("away_name"),
        "home_team": match.get("home_team"),
        "away_team": match.get("away_team"),
        "home_score": match.get("home_score"),
        "away_score": match.get("away_score"),
        "home_penalties": match.get("home_penalties"),
        "away_penalties": match.get("away_penalties"),
        "winner_player_id": match.get("winner_player_id"),
        "played_at": match.get("played_at"),
        "match_status": str(match.get("match_status") or "pending"),
        "ready": bool(match.get("home_player_id") and match.get("away_player_id") and match.get("home_score") is None and str(match.get("match_status") or "pending") != "skipped"),
    }


def live_payload() -> dict[str, Any]:
    tournament = db.current_tournament()
    if not tournament:
        return {"server_time": utc_now(), "api_version": API_VERSION, "tournament": None}

    tid = str(tournament["id"])
    bundle = db.bundle(tid)
    meta = bundle.get("meta") or {}
    extra = meta.get("extra") or {}
    matches = bundle.get("matches") or []
    schedule_raw = db.live_schedule_from(matches, extra)
    current_raw = db.current_match_from(matches, extra)
    current_context = None
    if current_raw and current_raw.get("home_player_id") and current_raw.get("away_player_id"):
        try:
            current_context = db.match_context(current_raw["home_player_id"], current_raw["away_player_id"])
        except Exception:
            current_context = None
    current_no = int(current_raw.get("match_no") or 0) if current_raw else 0
    next_raw = db.next_ready_match_from(matches, current_no, extra) if current_raw else None
    standings = db.standings(tid)
    scorers = db.tournament_live_scorers(tid, 5)
    fmt = str(meta.get("format_key") or tournament.get("format_key") or "")

    summary = None
    if str(tournament.get("status")) == "completed":
        try:
            s = db.tournament_summary(tid)
            summary = {
                "champion": s.get("champion"),
                "runner_up": s.get("runner_up"),
            }
        except Exception:
            summary = None

    return {
        "server_time": utc_now(),
        "api_version": API_VERSION,
        "tournament": {
            "id": tid,
            "status": tournament.get("status"),
            "phase": tournament.get("phase"),
            "is_test": bool(int(tournament.get("is_test") or 0)),
            "player_count": int(meta.get("player_count") or tournament.get("player_count") or 0),
            "format_key": fmt,
            "format_label": FORMAT_LABELS.get(fmt, fmt),
            "format_matches": FORMAT_MATCH_COUNTS.get(fmt, ""),
            "created_at": tournament.get("created_at"),
            "completed_at": tournament.get("completed_at"),
            "players": [
                {
                    "player_id": p.get("player_id"),
                    "name": p.get("name"),
                    "team": p.get("team"),
                    "group_name": p.get("group_name"),
                }
                for p in (bundle.get("players") or [])
            ],
            "current_match": clean_match(current_raw) if current_raw else None,
            "current_context": current_context,
            "next_match": clean_match(next_raw) if next_raw else None,
            "schedule": [clean_match(m) for m in schedule_raw],
            "standings": standings,
            "live_scorers": scorers,
            "summary": summary,
        },
    }


@app.get("/api/v1/health")
def health() -> dict[str, Any]:
    return {
        "ok": True,
        "api_version": API_VERSION,
        "database": "postgres" if db.is_postgres else "sqlite",
        "controller_configured": bool(_admin_password() and _token_secret()),
        "server_time": utc_now(),
    }


@app.post("/api/v1/auth/controller")
def controller_login(payload: ControllerLogin) -> dict[str, Any]:
    configured = _admin_password()
    if not configured:
        raise HTTPException(503, "ADMIN_PASSWORD nie jest ustawione na serwerze API.")
    if not hmac.compare_digest(payload.password, configured):
        raise HTTPException(401, "Nieprawidłowe hasło administratora.")
    token, expires_at = issue_controller_token()
    return {"token": token, "expires_at": expires_at, "scope": "controller"}


@app.get("/api/v1/auth/me")
def auth_me(_claims: dict[str, Any] = Depends(require_controller)) -> dict[str, Any]:
    return {"controller": True}


@app.get("/api/v1/live")
def get_live() -> dict[str, Any]:
    return live_payload()


@app.get("/api/v1/stats/players")
def get_player_stats() -> dict[str, Any]:
    return {"players": db.all_time_stats(), "server_time": utc_now()}


@app.get("/api/v1/stats/records")
def get_records() -> dict[str, Any]:
    return {"records": db.all_time_records(), "server_time": utc_now()}


@app.get("/api/v1/players/{player_id}")
def get_player_profile(player_id: str) -> dict[str, Any]:
    profile = db.player_profile(player_id)
    if not profile:
        raise HTTPException(404, "Nie znaleziono gracza.")
    try:
        center = db.achievement_center()
        achievement = next((p for p in center.get("players", []) if str(p.get("player_id")) == str(player_id)), None)
    except Exception:
        achievement = None
    try:
        awards = db.player_award_wins(player_id)
    except Exception:
        awards = []
    return {"profile": profile, "achievement": achievement, "awards": awards}


@app.get("/api/v1/awards/{year}")
def get_awards(year: int) -> dict[str, Any]:
    if year < 2020 or year > 2100:
        raise HTTPException(422, "Nieprawidłowy rok.")
    return db.annual_awards(int(year))


@app.get("/api/v1/tournaments/{tournament_id}/matches/{match_no}/scorer-options")
def scorer_options(tournament_id: str, match_no: int) -> dict[str, Any]:
    match = next((m for m in db.matches(tournament_id) if int(m.get("match_no") or 0) == int(match_no)), None)
    if not match:
        raise HTTPException(404, "Nie znaleziono meczu.")
    return {
        "home": {
            "team": match.get("home_team") or "",
            "options": db.team_scorer_options(match.get("home_team") or "") if match.get("home_team") else [],
        },
        "away": {
            "team": match.get("away_team") or "",
            "options": db.team_scorer_options(match.get("away_team") or "") if match.get("away_team") else [],
        },
    }


def _scorers_to_dict(payload: ScorersPayload | None, match: dict[str, Any]) -> dict[str, Any] | None:
    if payload is None:
        return None
    out: dict[str, Any] = {}
    for side in ("home", "away"):
        side_payload = getattr(payload, side)
        if side_payload is None:
            out[side] = {"team": match.get(f"{side}_team") or "", "items": []}
            continue
        team = side_payload.team.strip() or str(match.get(f"{side}_team") or "")
        out[side] = {"team": team, "items": [{"name": x.name.strip(), "goals": int(x.goals)} for x in side_payload.items if x.name.strip()]}
    return out


@app.post("/api/v1/tournaments/{tournament_id}/matches/{match_no}/result")
def save_match_result(
    tournament_id: str,
    match_no: int,
    payload: ResultPayload,
    _claims: dict[str, Any] = Depends(require_controller),
) -> dict[str, Any]:
    tournament = db.current_tournament()
    if not tournament or str(tournament.get("id")) != str(tournament_id):
        raise HTTPException(409, "Ten turniej nie jest aktualnie aktywny.")
    match = next((m for m in db.matches(tournament_id) if int(m.get("match_no") or 0) == int(match_no)), None)
    if not match:
        raise HTTPException(404, "Nie znaleziono meczu.")
    if match.get("home_score") is not None or str(match.get("match_status") or "pending") == "skipped":
        raise HTTPException(409, "Ten mecz jest już zakończony.")
    current = live_payload().get("tournament", {}).get("current_match")
    if not current or int(current.get("match_no") or 0) != int(match_no):
        raise HTTPException(409, "To nie jest aktualny mecz w kolejności LIVE.")

    scorers = _scorers_to_dict(payload.scorers, match)
    if scorers:
        fmt = str(tournament.get("format_key") or "")
        wb_bonus = fmt.startswith("double") and str(match.get("stage")) == "FINAL"
        expected_home = max(0, int(payload.home_score) - (1 if wb_bonus else 0))
        expected_away = int(payload.away_score)
        home_sum = sum(int(x["goals"]) for x in scorers.get("home", {}).get("items", []))
        away_sum = sum(int(x["goals"]) for x in scorers.get("away", {}).get("items", []))
        if home_sum > expected_home or away_sum > expected_away:
            raise HTTPException(422, "Suma wpisanych goli strzelców nie może przekraczać wyniku meczu.")

    try:
        db.save_result(
            tournament_id,
            int(match_no),
            int(payload.home_score),
            int(payload.away_score),
            payload.home_penalties,
            payload.away_penalties,
            scorers,
        )
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    return live_payload()


@app.post("/api/v1/tournaments/{tournament_id}/undo-last")
def undo_last(
    tournament_id: str,
    _claims: dict[str, Any] = Depends(require_controller),
) -> dict[str, Any]:
    tournament = db.current_tournament()
    if not tournament or str(tournament.get("id")) != str(tournament_id):
        raise HTTPException(409, "Ten turniej nie jest aktualnie aktywny.")
    match_no = db.undo_last_result(tournament_id)
    if match_no is None:
        raise HTTPException(409, "Nie ma wyniku do cofnięcia.")
    payload = live_payload()
    payload["undone_match_no"] = int(match_no)
    return payload

from __future__ import annotations

import base64
import io
import hashlib
import hmac
import json
import os
import re
import secrets
import time
from datetime import datetime, timezone
from typing import Any

import httpx
from fastapi import Depends, FastAPI, File, Form, Header, HTTPException, UploadFile, Query
from PIL import Image, ImageOps
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from pydantic import BaseModel, Field

from database import Database
from logic import (
    FORMAT_LABELS, FORMAT_MATCH_COUNTS, FIXED_TEAMS, BASE_TEAMS, SIX_TEAMS, SEVEN_TEAMS, EIGHT_TEAMS,
    WILDCARD_TEAM_SUGGESTIONS, allowed_teams,
)
from export_utils import generate_summary_png, generate_settlement_png, generate_awards_png, generate_year_summary_png

API_VERSION = "1.0.0"
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
    allow_methods=["GET", "POST", "DELETE"],
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


def _controller_claims_or_none(authorization: str | None) -> dict[str, Any] | None:
    if not authorization or not authorization.lower().startswith("bearer "):
        return None
    try:
        return verify_controller_token(authorization.split(" ", 1)[1].strip())
    except HTTPException:
        return None


def _require_controller_header(authorization: str | None) -> dict[str, Any]:
    claims=_controller_claims_or_none(authorization)
    if not claims:
        raise HTTPException(401, "Ta operacja wymaga sterowania na urządzeniu.")
    return claims


def _current_tournament_or_409(tid: str | None = None) -> dict[str, Any]:
    tournament=db.current_tournament()
    if not tournament:
        raise HTTPException(409, "Brak aktywnego FIFA Night.")
    if tid is not None and str(tournament.get("id")) != str(tid):
        raise HTTPException(409, "To nie jest aktualnie aktywny FIFA Night.")
    return tournament


def _require_game_control(tid: str, authorization: str | None = None) -> dict[str, Any]:
    tournament=_current_tournament_or_409(tid)
    fmt=str(tournament.get("format_key") or "")
    # Testowe turnieje oraz każde 1 VS 1 można prowadzić bez przejęcia sterowania.
    if bool(int(tournament.get("is_test") or 0)) or fmt=="duel1v1":
        return {"public": True}
    return _require_controller_header(authorization)


def _ensure_can_start(is_test: bool, authorization: str | None) -> None:
    current=db.current_tournament()
    if current and str(current.get("status") or "") == "active":
        raise HTTPException(409, "Najpierw zakończ albo zresetuj bieżący FIFA Night.")
    if current and str(current.get("status") or "") in {"completed","abandoned"}:
        db.start_new()
    if not is_test:
        _require_controller_header(authorization)


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
    events: list[dict[str, Any]] | None = None


class CreateTournamentPayload(BaseModel):
    player_names: list[str]
    player_count: int = Field(ge=3, le=8)
    format_key: str
    is_test: bool = True
    stake_per_player: float = Field(default=0.0, ge=0, le=100000)
    cash_flags: list[bool] = Field(default_factory=list)


class CreateDuelPayload(BaseModel):
    player_names: list[str]
    team_names: list[str]
    stake_per_player: float = Field(default=0.0, ge=0, le=100000)
    cash_flags: list[bool] = Field(default_factory=lambda:[True,True])


class TestModePayload(BaseModel):
    is_test: bool


class DraftPickPayload(BaseModel):
    player_id: str
    slot: str
    wildcard_name: str = ""


class WildcardPayload(BaseModel):
    player_id: str
    team_name: str


class AddScorerPayload(BaseModel):
    side: str
    name: str = Field(min_length=1, max_length=120)


class SettlementRequest(BaseModel):
    tournament_ids: list[str]


class SettledPayload(BaseModel):
    tournament_ids: list[str]
    settled: bool = True


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



@app.get("/api/v1/health")
def health() -> dict[str, Any]:
    return {
        "ok": True,
        "api_version": API_VERSION,
        "database": "postgres" if db.is_postgres else "sqlite",
        "controller_configured": bool(_admin_password() and _token_secret()),
        "server_time": utc_now(),
    }


VISION_ALLOWED_TYPES = {"image/jpeg", "image/png", "image/webp"}
VISION_MAX_IMAGE_BYTES = 12 * 1024 * 1024


def _google_vision_api_key() -> str:
    return str(os.getenv("GOOGLE_VISION_API_KEY") or "").strip()


def _openai_api_key() -> str:
    return str(os.getenv("OPENAI_API_KEY") or "").strip()


def _gemini_api_key() -> str:
    return str(os.getenv("GEMINI_API_KEY") or "").strip()


AI_EVENT_SCAN_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "left_label": {"type": ["string", "null"]},
        "right_label": {"type": ["string", "null"]},
        "score_left": {"type": ["integer", "null"], "minimum": 0, "maximum": 99},
        "score_right": {"type": ["integer", "null"], "minimum": 0, "maximum": 99},
        "match_clock": {"type": ["string", "null"]},
        "score_confidence": {"type": "string", "enum": ["high", "medium", "low"]},
        "events": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "image_indices": {"type": "array", "items": {"type": "integer", "minimum": 1}},
                    "minute": {"type": ["integer", "null"], "minimum": 0, "maximum": 130},
                    "stoppage": {"type": ["integer", "null"], "minimum": 0, "maximum": 30},
                    "minute_label": {"type": ["string", "null"]},
                    "side": {"type": "string", "enum": ["left", "right", "unknown"]},
                    "event_type": {
                        "type": "string",
                        "enum": [
                            "normal_goal", "penalty_goal", "own_goal",
                            "yellow_card", "red_card", "injury", "substitution",
                            "penalty_miss", "other", "unknown"
                        ],
                    },
                    "player": {"type": ["string", "null"]},
                    "own_goal_by": {"type": ["string", "null"]},
                    "related_player": {"type": ["string", "null"]},
                    "credited_side": {"type": "string", "enum": ["left", "right", "unknown"]},
                    "confidence": {"type": "string", "enum": ["high", "medium", "low"]},
                },
                "required": [
                    "image_indices", "minute", "stoppage", "minute_label", "side",
                    "event_type", "player", "own_goal_by", "related_player", "credited_side", "confidence"
                ],
            },
        },
        "event_list_complete": {"type": "boolean"},
        "needs_more_images": {"type": "boolean"},
        "notes": {"type": "array", "items": {"type": "string"}},
    },
    "required": [
        "left_label", "right_label", "score_left", "score_right", "match_clock",
        "score_confidence", "events", "event_list_complete", "needs_more_images", "notes"
    ],
}


AI_EVENT_SCAN_PROMPT = """You are a visual extraction engine for EA Sports FC post-match EVENT screens.
All supplied images belong to the SAME match. There may be any number of screenshots and adjacent screenshots may overlap.

Extract only facts that are actually visible. Do not invent missing goals or events from the final score.
Read the score and the two labels at the top when visible. Use left/right exactly as shown on screen.

CRITICAL: classify events from the VISUAL ICON, not from OCR text, player names, score arithmetic, or assumptions.
EA FC icon rules confirmed for FIFA Night from real EA FC event screens:
- plain WHITE football/ball icon = normal_goal
- GOAL/NET icon with a small CHECK/TICK badge at the bottom = penalty_goal (a scored penalty during normal/extra time)
- GOAL/NET icon with an X badge at the bottom = penalty_miss (a missed penalty during normal/extra time; it is NOT a goal)
- RED football/ball-style icon = own_goal. It is NOT a missed penalty.
- yellow rectangular card = yellow_card
- red rectangular card = red_card
- player names with green up / red down arrows = substitution, NOT a goal
- for substitution events, set player = the footballer COMING ON (green/up arrow) and related_player = the footballer GOING OFF (red/down arrow). side = that team's visible side; credited_side = unknown. Never swap these roles.
- injury/medical event = injury. FIFA Night treats all injury severities identically. EA FC may show more than one injury symbol, including a bandage/plaster-style medical icon with a plus/cross or an ambulance/medical icon with a plus/cross. If either medical injury icon is visibly present, classify it as injury. If the symbol is ambiguous, use unknown rather than guessing.
- if an icon cannot be identified reliably, use unknown

VERY IMPORTANT OWN-GOAL LAYOUT RULE:
EA FC displays an own-goal event on the SAME physical side/team as the footballer who committed the own goal. The match goal, however, belongs to the OPPOSING team. Do not infer own-goal credit from the side where the event row is drawn.

Goal/event field rules:
- normal_goal: player = scorer; side = scorer's visible side; credited_side = same side; own_goal_by = null
- penalty_goal: player = scorer; side = scorer's visible side; credited_side = same side; own_goal_by = null
- penalty_miss: player = the penalty taker shown next to the goal/net-with-X icon; side = that player's visible side; credited_side = unknown; own_goal_by = null
- own_goal: player MUST be null; own_goal_by = the footballer whose name is shown with the RED own-goal icon; side = that footballer's visible side; credited_side = the OPPOSITE side
- own goals count toward the match score but must never be credited as a scorer goal
- penalty misses never count toward the match score or scorer totals

For injury: player = the visibly injured footballer; side = that footballer's visible side; credited_side = unknown.
For substitution: player = player COMING ON; related_player = player GOING OFF; side = that team's visible side; credited_side = unknown.
A red card or injury is only an extracted event. FIFA Night's backend decides any next-match absence rule.

Different events can occur in the same minute on opposite sides.
Return each visible event once. If the same event appears on overlapping screenshots, merge it and include all matching image_indices.
Preserve player names as displayed. Do not guess full names.

The complete list of ALL events (cards/substitutions) is less important than the complete list of GOALS.
If the screenshots omit some cards or substitutions but all goals can still be accounted for, do not invent those missing events.
Set event_list_complete only for the whole event timeline. The server will independently validate goal completeness against the score.
A final score never authorizes you to invent a missing goal.
"""



# Context-aware schema used by the real match scanner.  It adds a mapping from the
# physical left/right EA FC layout to FIFA Night's internal bracket slots.  The
# internal slots are NOT assumed from the screen position; the model must identify
# them from the assigned club/team names supplied by the server.
MATCH_EVENT_SCAN_SCHEMA: dict[str, Any] = json.loads(json.dumps(AI_EVENT_SCAN_SCHEMA))
MATCH_EVENT_SCAN_SCHEMA["properties"].update({
    "left_participant_slot": {"type": "string", "enum": ["home", "away", "unknown"]},
    "right_participant_slot": {"type": "string", "enum": ["home", "away", "unknown"]},
    "mapping_confidence": {"type": "string", "enum": ["high", "medium", "low"]},
    "shootout_left": {"type": ["integer", "null"], "minimum": 0, "maximum": 30},
    "shootout_right": {"type": ["integer", "null"], "minimum": 0, "maximum": 30},
})
MATCH_EVENT_SCAN_SCHEMA["required"] += [
    "left_participant_slot", "right_participant_slot", "mapping_confidence",
    "shootout_left", "shootout_right",
]


def _match_event_scan_prompt(context: dict[str, Any]) -> str:
    participants = context.get("participants") or []
    home = next((p for p in participants if p.get("slot") == "home"), {})
    away = next((p for p in participants if p.get("slot") == "away"), {})
    de_note = ""
    if context.get("de_wb_bonus"):
        de_note = (
            "\nDOUBLE ELIMINATION GRAND FINAL CONTEXT:\n"
            f"- The Winners Bracket advantage belongs to FIFA Night player {context.get('de_wb_advantage_player_id')} "
            f"with assigned club/team {context.get('de_wb_advantage_team')}.\n"
            "- FIFA Night deliberately creates ONE own goal near the beginning of this match to implement the +1 Winners Bracket advantage.\n"
            "- Extract that event normally as own_goal. Do NOT invent it if it is not visible. The server, not you, will mark the first matching own goal as synthetic.\n"
        )
    return AI_EVENT_SCAN_PROMPT + f"""

AUTHORITATIVE FIFA NIGHT MATCH CONTEXT:
- Internal HOME bracket slot: FIFA Night player "{home.get('player_name','')}"; assigned club/team "{home.get('team','')}".
- Internal AWAY bracket slot: FIFA Night player "{away.get('player_name','')}"; assigned club/team "{away.get('team','')}".
- Tournament stage: {context.get('stage','')}; format: {context.get('format_key','')}.

IMPORTANT TEAM MAPPING RULE:
The physical EA FC screen may place either assigned club on the LEFT or RIGHT.
Identify which FIFA Night participant is on each screen side by the club/team name visible in the EA FC screen and event rows.
Never assume LEFT=HOME or RIGHT=AWAY.
Set left_participant_slot and right_participant_slot to "home" or "away" only when you can match them to the two assigned teams above.
If a team mapping is genuinely unclear, return "unknown" and lower mapping_confidence instead of guessing.

PENALTY SHOOT-OUT:
If a post-match shoot-out result is explicitly visible, return only the final shoot-out tally in shootout_left/shootout_right.
Do NOT add individual shoot-out kicks to events or goals.
If no shoot-out tally is visible, return null for both.
{de_note}
"""


def _participant_by_slot(context: dict[str, Any], slot: str) -> dict[str, Any] | None:
    return next((p for p in (context.get("participants") or []) if p.get("slot") == slot), None)


def _map_scan_to_fifa_context(result: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
    """Map visual left/right events to the FIFA Night players owning the assigned teams."""
    result = _normalize_and_validate_event_scan_result(result)
    left_slot = str(result.get("left_participant_slot") or "unknown")
    right_slot = str(result.get("right_participant_slot") or "unknown")

    # If exactly one side was recognized, the other side is deterministic because a
    # FIFA Night match has exactly two participants.
    if left_slot in {"home", "away"} and right_slot == "unknown":
        right_slot = "away" if left_slot == "home" else "home"
    elif right_slot in {"home", "away"} and left_slot == "unknown":
        left_slot = "away" if right_slot == "home" else "home"

    mapping_ok = left_slot in {"home", "away"} and right_slot in {"home", "away"} and left_slot != right_slot
    if not mapping_ok:
        left_slot = right_slot = "unknown"

    result["left_participant_slot"] = left_slot
    result["right_participant_slot"] = right_slot
    slot_for_visual = {"left": left_slot, "right": right_slot}

    # Translate scoreboard and shoot-out score from visual sides to the bracket slots
    # expected by the existing result engine.
    score_left, score_right = result.get("score_left"), result.get("score_right")
    shoot_left, shoot_right = result.get("shootout_left"), result.get("shootout_right")
    home_score = away_score = None
    home_pens = away_pens = None
    if mapping_ok:
        if left_slot == "home":
            home_score, away_score = score_left, score_right
            home_pens, away_pens = shoot_left, shoot_right
        else:
            home_score, away_score = score_right, score_left
            home_pens, away_pens = shoot_right, shoot_left

    mapped_events: list[dict[str, Any]] = []
    for idx, event in enumerate(result.get("events") or [], start=1):
        if not isinstance(event, dict):
            continue
        actor_visual = str(event.get("side") or "unknown")
        credited_visual = str(event.get("credited_side") or "unknown")
        actor_slot = slot_for_visual.get(actor_visual, "unknown")
        credited_slot = slot_for_visual.get(credited_visual, "unknown")
        actor = _participant_by_slot(context, actor_slot) if actor_slot in {"home", "away"} else None
        credited = _participant_by_slot(context, credited_slot) if credited_slot in {"home", "away"} else None
        event_type = str(event.get("event_type") or "unknown")
        footballer = event.get("own_goal_by") if event_type == "own_goal" else event.get("player")
        mapped_events.append({
            "event_order": idx,
            "event_type": event_type,
            "minute": event.get("minute"),
            "stoppage": event.get("stoppage"),
            "minute_label": event.get("minute_label"),
            "footballer_name": footballer,
            "related_footballer_name": event.get("related_player"),
            "actor_player_id": actor.get("player_id") if actor else None,
            "actor_player_name": actor.get("player_name") if actor else None,
            "actor_team_name": actor.get("team") if actor else None,
            "credited_player_id": credited.get("player_id") if credited else None,
            "credited_player_name": credited.get("player_name") if credited else None,
            "credited_team_name": credited.get("team") if credited else None,
            "synthetic_de": False,
            "confidence": event.get("confidence"),
            "source_images": list(event.get("image_indices") or []),
            "visual_side": actor_visual,
            "visual_credited_side": credited_visual,
        })

    # In a DE Grand Final the first own goal that credits the Winners Bracket player
    # is the deliberate technical +1. Minute does not matter (1', 2', 5' etc.).
    wb_pid = str(context.get("de_wb_advantage_player_id") or "")
    if context.get("de_wb_bonus") and wb_pid:
        for event in mapped_events:
            if event.get("event_type") == "own_goal" and str(event.get("credited_player_id") or "") == wb_pid:
                event["synthetic_de"] = True
                break

    # Hard validation in the internal HOME/AWAY slots. Own goals, including the DE
    # technical one, are real scoreboard events and therefore count here.
    goal_types = {"normal_goal", "penalty_goal", "own_goal"}
    home_goals = sum(1 for e in mapped_events if e.get("event_type") in goal_types and str(e.get("credited_player_id") or "") == str((_participant_by_slot(context,"home") or {}).get("player_id") or ""))
    away_goals = sum(1 for e in mapped_events if e.get("event_type") in goal_types and str(e.get("credited_player_id") or "") == str((_participant_by_slot(context,"away") or {}).get("player_id") or ""))
    unknown_goals = sum(1 for e in mapped_events if e.get("event_type") in goal_types and not e.get("credited_player_id"))
    validation = {
        "status": "mapping_unknown" if not mapping_ok else "score_unknown",
        "complete": False,
        "recognized_home": home_goals,
        "recognized_away": away_goals,
        "recognized_goal_events": home_goals + away_goals + unknown_goals,
        "recognized_unknown": unknown_goals,
        "expected_home": home_score,
        "expected_away": away_score,
        "missing_home": None,
        "missing_away": None,
    }
    if mapping_ok and isinstance(home_score, int) and isinstance(away_score, int):
        validation["missing_home"] = max(home_score - home_goals, 0)
        validation["missing_away"] = max(away_score - away_goals, 0)
        if unknown_goals:
            validation["status"] = "needs_review"
        elif home_goals == home_score and away_goals == away_score:
            validation["status"] = "complete"; validation["complete"] = True
        elif home_goals > home_score or away_goals > away_score:
            validation["status"] = "overcount"
        else:
            validation["status"] = "missing_goals"

    result["fifa_night"] = {
        "mapping_ok": mapping_ok,
        "home_score": home_score,
        "away_score": away_score,
        "home_penalties": home_pens,
        "away_penalties": away_pens,
        "left_slot": left_slot,
        "right_slot": right_slot,
        "participants": context.get("participants") or [],
        "events": mapped_events,
        "goal_validation": validation,
        "de_wb_bonus": int(context.get("de_wb_bonus") or 0),
        "de_wb_advantage_player_id": context.get("de_wb_advantage_player_id"),
    }
    return result

GOAL_EVENT_TYPES = {"normal_goal", "penalty_goal", "own_goal"}

def _opposite_side(side: str) -> str:
    return "right" if side == "left" else "left" if side == "right" else "unknown"

def _normalize_and_validate_event_scan_result(result: dict[str, Any]) -> dict[str, Any]:
    """Normalize goal semantics and derive hard goal-vs-score validation on the server."""
    events = [event for event in (result.get("events") or []) if isinstance(event, dict)]
    for event in events:
        event_type = str(event.get("event_type") or "unknown")
        side = str(event.get("side") or "unknown")
        if event_type == "own_goal":
            # A player shown next to the red own-goal ball is NOT a scorer.
            if not event.get("own_goal_by") and event.get("player"):
                event["own_goal_by"] = event.get("player")
            event["player"] = None
            event["credited_side"] = _opposite_side(side)
        elif event_type in {"normal_goal", "penalty_goal"}:
            event["own_goal_by"] = None
            event["credited_side"] = side if side in {"left", "right"} else "unknown"
        else:
            event["own_goal_by"] = None
            event["credited_side"] = "unknown"
        event["image_indices"] = sorted({int(x) for x in (event.get("image_indices") or []) if str(x).isdigit()})

    # Overlapping screenshots often contain the same row twice. Merge only when
    # otherwise-identical events originate from disjoint, non-empty image sets.
    # This keeps two legitimate rows from the same screenshot untouched.
    def dedupe_key(event: dict[str, Any]) -> tuple[Any, ...]:
        norm=lambda value: " ".join(str(value or "").casefold().split())
        return (
            str(event.get("event_type") or "unknown"), event.get("minute"), event.get("stoppage"),
            str(event.get("side") or "unknown"), norm(event.get("player")), norm(event.get("own_goal_by")),
            norm(event.get("related_player")),
        )
    deduped: list[dict[str, Any]] = []
    for event in events:
        images=set(event.get("image_indices") or [])
        existing=None
        if images:
            for candidate in deduped:
                candidate_images=set(candidate.get("image_indices") or [])
                if candidate_images and candidate_images.isdisjoint(images) and dedupe_key(candidate)==dedupe_key(event):
                    existing=candidate;break
        if existing is None:
            deduped.append(event)
        else:
            existing["image_indices"]=sorted(set(existing.get("image_indices") or [])|images)
            if str(event.get("confidence") or "").lower()=="high":
                existing["confidence"]="high"
    events=deduped
    result["events"]=events

    score_left = result.get("score_left")
    score_right = result.get("score_right")
    goal_events = [e for e in events if isinstance(e, dict) and e.get("event_type") in GOAL_EVENT_TYPES]
    recognized_left = sum(1 for e in goal_events if e.get("credited_side") == "left")
    recognized_right = sum(1 for e in goal_events if e.get("credited_side") == "right")
    recognized_unknown = sum(1 for e in goal_events if e.get("credited_side") not in {"left", "right"})

    validation: dict[str, Any] = {
        "recognized_goal_events": len(goal_events),
        "recognized_left": recognized_left,
        "recognized_right": recognized_right,
        "recognized_unknown": recognized_unknown,
        "expected_left": score_left,
        "expected_right": score_right,
        "complete": False,
        "status": "score_unknown",
        "missing_left": None,
        "missing_right": None,
        "extra_left": None,
        "extra_right": None,
    }
    if isinstance(score_left, int) and isinstance(score_right, int):
        validation["missing_left"] = max(score_left - recognized_left, 0)
        validation["missing_right"] = max(score_right - recognized_right, 0)
        validation["extra_left"] = max(recognized_left - score_left, 0)
        validation["extra_right"] = max(recognized_right - score_right, 0)
        exact = (recognized_left == score_left and recognized_right == score_right and recognized_unknown == 0)
        validation["complete"] = exact
        if exact:
            validation["status"] = "complete"
        elif recognized_left > score_left or recognized_right > score_right:
            validation["status"] = "overcount"
        elif recognized_unknown:
            validation["status"] = "needs_review"
        else:
            validation["status"] = "missing_goals"

    result["goal_validation"] = validation
    return result


def _extract_openai_output_text(payload: dict[str, Any]) -> str:
    for item in payload.get("output") or []:
        if not isinstance(item, dict) or item.get("type") != "message":
            continue
        for content in item.get("content") or []:
            if isinstance(content, dict) and content.get("type") == "output_text":
                text = str(content.get("text") or "").strip()
                if text:
                    return text
    return ""


def _extract_gemini_output_text(payload: dict[str, Any]) -> str:
    for candidate in payload.get("candidates") or []:
        content = candidate.get("content") or {}
        for part in content.get("parts") or []:
            if isinstance(part, dict) and str(part.get("text") or "").strip():
                return str(part.get("text") or "").strip()
    return ""


def _require_vision_test_admin(x_admin_password: str | None) -> None:
    configured = _admin_password()
    if not configured:
        raise HTTPException(503, "ADMIN_PASSWORD nie jest ustawione na serwerze API.")
    if not x_admin_password or not hmac.compare_digest(str(x_admin_password), configured):
        raise HTTPException(401, "Brak dostępu do testu OCR.")


def _annotation_box(item: dict[str, Any]) -> list[dict[str, int]]:
    vertices = ((item.get("boundingPoly") or {}).get("vertices") or [])
    return [
        {"x": int(v.get("x") or 0), "y": int(v.get("y") or 0)}
        for v in vertices
    ]


def _normalize_image_for_google(raw: bytes, index: int) -> tuple[bytes, str, int, int]:
    """Decode user upload with Pillow and re-encode as a standard RGB JPEG for Google Vision."""
    try:
        with Image.open(io.BytesIO(raw)) as img:
            img = ImageOps.exif_transpose(img)
            width, height = img.size
            if width < 1 or height < 1:
                raise ValueError("invalid dimensions")
            if img.mode != "RGB":
                # JPEG has no alpha channel; flatten transparent pixels onto white.
                if "A" in img.getbands():
                    rgba = img.convert("RGBA")
                    background = Image.new("RGB", rgba.size, "white")
                    background.paste(rgba, mask=rgba.getchannel("A"))
                    img = background
                else:
                    img = img.convert("RGB")
            out = io.BytesIO()
            img.save(out, format="JPEG", quality=92, optimize=True)
            return out.getvalue(), "image/jpeg", width, height
    except Exception as exc:
        raise HTTPException(422, f"Zdjęcie {index}: nie udało się odczytać pliku jako obrazu ({exc}).") from exc


@app.post("/api/v1/vision/test-scan")
async def vision_test_scan(
    images: list[UploadFile] = File(...),
    provider: str = Form(default="google_ocr"),
    x_admin_password: str | None = Header(default=None, alias="X-Admin-Password"),
) -> dict[str, Any]:
    """Temporary EA FC vision benchmark. Accepts one or more images and never writes to Neon."""
    _require_vision_test_admin(x_admin_password)
    provider = str(provider or "google_ocr").strip().lower()
    aliases = {
        "google": "google_ocr",
        "google_cloud_vision": "google_ocr",
        "ocr": "google_ocr",
        "openai": "openai_luna",
        "luna": "openai_luna",
        "gemini": "gemini_38_flash",
        "gemini_flash": "gemini_36_flash",
        "gemini_flash_lite": "gemini_35_flash_lite",
    }
    provider = aliases.get(provider, provider)
    if provider not in {
        "google_ocr",
        "openai_luna",
        "gemini_38_flash",
        "gemini_37_flash",
        "gemini_36_flash",
        "gemini_35_flash_lite",
    }:
        raise HTTPException(422, "Nieznany provider testu Vision.")
    if not images:
        raise HTTPException(422, "Dodaj co najmniej jedno zdjęcie.")

    prepared: list[dict[str, Any]] = []
    for index, image in enumerate(images, start=1):
        content_type = str(image.content_type or "").lower()
        if content_type not in VISION_ALLOWED_TYPES:
            raise HTTPException(415, f"Zdjęcie {index}: obsługiwane są JPG, PNG i WEBP.")
        raw = await image.read()
        if not raw:
            raise HTTPException(422, f"Zdjęcie {index} jest puste.")
        if len(raw) > VISION_MAX_IMAGE_BYTES:
            raise HTTPException(413, f"Zdjęcie {index} ma więcej niż 12 MB.")
        normalized, normalized_type, width, height = _normalize_image_for_google(raw, index)
        prepared.append({
            "image_index": index,
            "filename": image.filename or f"image_{index}",
            "content_type": content_type,
            "bytes": len(raw),
            "normalized": normalized,
            "normalized_content_type": normalized_type,
            "normalized_bytes": len(normalized),
            "width": width,
            "height": height,
        })

    if provider == "google_ocr":
        api_key = _google_vision_api_key()
        if not api_key:
            raise HTTPException(503, "GOOGLE_VISION_API_KEY nie jest ustawiony na serwerze API.")
        requests_payload = [
            {
                "image": {"content": base64.b64encode(item["normalized"]).decode("ascii")},
                "features": [{"type": "TEXT_DETECTION"}],
            }
            for item in prepared
        ]
        started = time.perf_counter()
        url = f"https://vision.googleapis.com/v1/images:annotate?key={api_key}"
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(30.0)) as client:
                response = await client.post(url, json={"requests": requests_payload})
        except httpx.TimeoutException as exc:
            raise HTTPException(504, "Google Vision nie odpowiedział w ciągu 30 sekund.") from exc
        except httpx.HTTPError as exc:
            raise HTTPException(502, f"Nie udało się połączyć z Google Vision: {exc}") from exc
        elapsed_ms = round((time.perf_counter() - started) * 1000)
        try:
            payload = response.json()
        except Exception:
            payload = {}
        if response.status_code >= 400:
            message = ((payload.get("error") or {}).get("message") if isinstance(payload, dict) else None) or response.text[:500]
            raise HTTPException(502, f"Google Vision API zwrócił błąd: {message}")
        google_responses = payload.get("responses") or []
        parsed_images: list[dict[str, Any]] = []
        for idx, meta in enumerate(prepared):
            item = google_responses[idx] if idx < len(google_responses) else {}
            google_error = item.get("error") or None
            annotations = item.get("textAnnotations") or []
            raw_text = str((annotations[0] or {}).get("description") or "") if annotations else ""
            text_items = [
                {"text": str(a.get("description") or ""), "box": _annotation_box(a)}
                for a in annotations[1:]
                if str(a.get("description") or "").strip()
            ]
            parsed_images.append({
                **{k: v for k, v in meta.items() if k != "normalized"},
                "ok": not bool(google_error),
                "raw_text": raw_text,
                "text_items": text_items,
                "detected_items": len(text_items),
                "google_error": google_error,
            })
        return {
            "provider": "google_ocr",
            "model": "Cloud Vision TEXT_DETECTION",
            "processing_time_ms": elapsed_ms,
            "image_count": len(parsed_images),
            "images": parsed_images,
            "saved_to_database": False,
        }

    if provider == "openai_luna":
        api_key = _openai_api_key()
        if not api_key:
            raise HTTPException(503, "OPENAI_API_KEY nie jest ustawiony na serwerze API.")
        content: list[dict[str, Any]] = [{"type": "input_text", "text": AI_EVENT_SCAN_PROMPT}]
        for item in prepared:
            encoded = base64.b64encode(item["normalized"]).decode("ascii")
            content.append({"type": "input_text", "text": f"IMAGE {item['image_index']}"})
            content.append({
                "type": "input_image",
                "image_url": f"data:image/jpeg;base64,{encoded}",
                "detail": "high",
            })
        body = {
            "model": "gpt-5.6-luna",
            "store": False,
            "reasoning": {"effort": "low"},
            "input": [{"role": "user", "content": content}],
            "text": {
                "verbosity": "low",
                "format": {
                    "type": "json_schema",
                    "name": "ea_fc_event_scan",
                    "strict": True,
                    "schema": AI_EVENT_SCAN_SCHEMA,
                },
            },
        }
        started = time.perf_counter()
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(60.0)) as client:
                response = await client.post(
                    "https://api.openai.com/v1/responses",
                    headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                    json=body,
                )
        except httpx.TimeoutException as exc:
            raise HTTPException(504, "OpenAI nie odpowiedział w ciągu 60 sekund.") from exc
        except httpx.HTTPError as exc:
            raise HTTPException(502, f"Nie udało się połączyć z OpenAI: {exc}") from exc
        elapsed_ms = round((time.perf_counter() - started) * 1000)
        try:
            payload = response.json()
        except Exception:
            payload = {}
        if response.status_code >= 400:
            message = ((payload.get("error") or {}).get("message") if isinstance(payload, dict) else None) or response.text[:800]
            raise HTTPException(502, f"OpenAI API zwrócił błąd: {message}")
        raw_text = _extract_openai_output_text(payload)
        try:
            result = json.loads(raw_text)
        except Exception as exc:
            raise HTTPException(502, f"OpenAI nie zwrócił poprawnego JSON: {raw_text[:800]}") from exc
        result = _normalize_and_validate_event_scan_result(result)
        usage = payload.get("usage") or {}
        input_tokens = int(usage.get("input_tokens") or 0)
        output_tokens = int(usage.get("output_tokens") or 0)
        estimated_cost = input_tokens * 0.20 / 1_000_000 + output_tokens * 1.20 / 1_000_000
        return {
            "provider": "openai_luna",
            "model": "gpt-5.6-luna",
            "processing_time_ms": elapsed_ms,
            "image_count": len(prepared),
            "result": result,
            "usage": {"input_tokens": input_tokens, "output_tokens": output_tokens, "total_tokens": int(usage.get("total_tokens") or input_tokens + output_tokens)},
            "estimated_cost_usd": round(estimated_cost, 8),
            "saved_to_database": False,
        }

    gemini_models = {
        "gemini_38_flash": "gemini-3.8-flash",
        "gemini_37_flash": "gemini-3.7-flash",
        "gemini_36_flash": "gemini-3.6-flash",
        "gemini_35_flash_lite": "gemini-3.5-flash-lite",
    }
    gemini_model = gemini_models[provider]

    api_key = _gemini_api_key()
    if not api_key:
        raise HTTPException(503, "GEMINI_API_KEY nie jest ustawiony na serwerze API.")
    parts: list[dict[str, Any]] = [{"text": AI_EVENT_SCAN_PROMPT}]
    for item in prepared:
        parts.append({"text": f"IMAGE {item['image_index']}"})
        parts.append({
            "inlineData": {
                "mimeType": "image/jpeg",
                "data": base64.b64encode(item["normalized"]).decode("ascii"),
            }
        })
    body = {
        "contents": [{"role": "user", "parts": parts}],
        "generationConfig": {
            "temperature": 0,
            # generateContent REST expects the legacy structured-output fields here.
            # responseFormat.text.mimeType uses enum values in the REST schema and
            # rejects the literal "application/json". responseMimeType +
            # responseJsonSchema accepts standard JSON Schema (including nullable types).
            "responseMimeType": "application/json",
            "responseJsonSchema": AI_EVENT_SCAN_SCHEMA,
        },
    }
    started = time.perf_counter()
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(60.0)) as client:
            response = await client.post(
                f"https://generativelanguage.googleapis.com/v1beta/models/{gemini_model}:generateContent",
                headers={"x-goog-api-key": api_key, "Content-Type": "application/json"},
                json=body,
            )
    except httpx.TimeoutException as exc:
        raise HTTPException(504, "Gemini nie odpowiedział w ciągu 60 sekund.") from exc
    except httpx.HTTPError as exc:
        raise HTTPException(502, f"Nie udało się połączyć z Gemini: {exc}") from exc
    elapsed_ms = round((time.perf_counter() - started) * 1000)
    try:
        payload = response.json()
    except Exception:
        payload = {}
    if response.status_code >= 400:
        message = ((payload.get("error") or {}).get("message") if isinstance(payload, dict) else None) or response.text[:800]
        raise HTTPException(502, f"Gemini API zwrócił błąd: {message}")
    raw_text = _extract_gemini_output_text(payload)
    try:
        result = json.loads(raw_text)
    except Exception as exc:
        raise HTTPException(502, f"Gemini nie zwrócił poprawnego JSON: {raw_text[:800]}") from exc
    result = _normalize_and_validate_event_scan_result(result)
    usage = payload.get("usageMetadata") or {}
    input_tokens = int(usage.get("promptTokenCount") or 0)
    answer_tokens = int(usage.get("candidatesTokenCount") or 0)
    thinking_tokens = int(usage.get("thoughtsTokenCount") or 0)
    output_tokens = answer_tokens + thinking_tokens

    # Current benchmark only needs a rough paid-tier estimate. Keep rates per model
    # isolated here so they are easy to refresh without touching the extraction logic.
    paid_rates = {
        "gemini_38_flash": (0.75, 3.75),
        "gemini_37_flash": (0.75, 3.75),
        "gemini_36_flash": (0.75, 3.75),
        "gemini_35_flash_lite": (0.30, 2.50),
    }
    input_rate, output_rate = paid_rates[provider]
    paid_estimate = input_tokens * input_rate / 1_000_000 + output_tokens * output_rate / 1_000_000
    return {
        "provider": provider,
        "model": gemini_model,
        "processing_time_ms": elapsed_ms,
        "image_count": len(prepared),
        "result": result,
        "usage": {
            "input_tokens": input_tokens,
            "answer_tokens": answer_tokens,
            "thinking_tokens": thinking_tokens,
            "total_tokens": int(usage.get("totalTokenCount") or input_tokens + output_tokens),
        },
        "paid_tier_estimated_cost_usd": round(paid_estimate, 8),
        "free_tier_may_apply": True,
        "saved_to_database": False,
    }



@app.post("/api/v1/tournaments/{tournament_id}/matches/{match_no}/scan-preview")
async def match_scan_preview(
    tournament_id: str,
    match_no: int,
    images: list[UploadFile] = File(...),
    authorization: str | None = Header(default=None),
    x_admin_password: str | None = Header(default=None, alias="X-Admin-Password"),
) -> dict[str, Any]:
    """Context-aware OpenAI scan for one real FIFA Night match. Never writes to Neon."""
    # Streamlit can keep using X-Admin-Password. The APK uses its controller token;
    # public test tournaments and 1 VS 1 are intentionally controllable without it.
    admin_ok=bool(x_admin_password and _admin_password() and hmac.compare_digest(str(x_admin_password), _admin_password()))
    if not admin_ok:
        _require_game_control(tournament_id, authorization)
    if not images:
        raise HTTPException(422, "Dodaj co najmniej jedno zdjęcie.")
    try:
        context = db.match_ai_context(tournament_id, int(match_no))
    except ValueError as exc:
        raise HTTPException(404, str(exc)) from exc

    prepared: list[dict[str, Any]] = []
    for index, image in enumerate(images, start=1):
        content_type = str(image.content_type or "").lower()
        if content_type not in VISION_ALLOWED_TYPES:
            raise HTTPException(415, f"Zdjęcie {index}: obsługiwane są JPG, PNG i WEBP.")
        raw = await image.read()
        if not raw:
            raise HTTPException(422, f"Zdjęcie {index} jest puste.")
        if len(raw) > VISION_MAX_IMAGE_BYTES:
            raise HTTPException(413, f"Zdjęcie {index} ma więcej niż 12 MB.")
        normalized, normalized_type, width, height = _normalize_image_for_google(raw, index)
        prepared.append({
            "image_index": index,
            "filename": image.filename or f"image_{index}",
            "content_type": content_type,
            "bytes": len(raw),
            "normalized": normalized,
            "normalized_content_type": normalized_type,
            "normalized_bytes": len(normalized),
            "width": width,
            "height": height,
        })

    api_key = _openai_api_key()
    if not api_key:
        raise HTTPException(503, "Odczyt zdjęć jest chwilowo niedostępny na serwerze.")
    content: list[dict[str, Any]] = [{"type": "input_text", "text": _match_event_scan_prompt(context)}]
    for item in prepared:
        encoded = base64.b64encode(item["normalized"]).decode("ascii")
        content.append({"type": "input_text", "text": f"IMAGE {item['image_index']}"})
        content.append({"type": "input_image", "image_url": f"data:image/jpeg;base64,{encoded}", "detail": "high"})
    body = {
        "model": "gpt-5.6-luna",
        "store": False,
        "reasoning": {"effort": "low"},
        "input": [{"role": "user", "content": content}],
        "text": {
            "verbosity": "low",
            "format": {"type": "json_schema", "name": "ea_fc_match_scan", "strict": True, "schema": MATCH_EVENT_SCAN_SCHEMA},
        },
    }
    started = time.perf_counter()
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(75.0)) as client:
            response = await client.post(
                "https://api.openai.com/v1/responses",
                headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                json=body,
            )
    except httpx.TimeoutException as exc:
        raise HTTPException(504, "Odczyt zdjęć nie odpowiedział w wymaganym czasie. Spróbuj ponownie.") from exc
    except httpx.HTTPError as exc:
        raise HTTPException(502, "Nie udało się połączyć z usługą odczytu zdjęć. Spróbuj ponownie.") from exc
    elapsed_ms = round((time.perf_counter() - started) * 1000)
    try:
        payload = response.json()
    except Exception:
        payload = {}
    if response.status_code >= 400:
        message = ((payload.get("error") or {}).get("message") if isinstance(payload, dict) else None) or response.text[:800]
        raise HTTPException(502, "Usługa odczytu zdjęć zwróciła błąd. Spróbuj ponownie.")
    raw_text = _extract_openai_output_text(payload)
    try:
        result = json.loads(raw_text)
    except Exception as exc:
        raise HTTPException(502, "Odczyt zdjęć zwrócił niepełne dane. Spróbuj ponownie.") from exc
    result = _map_scan_to_fifa_context(result, context)
    usage = payload.get("usage") or {}
    input_tokens = int(usage.get("input_tokens") or 0)
    output_tokens = int(usage.get("output_tokens") or 0)
    estimated_cost = input_tokens * 0.20 / 1_000_000 + output_tokens * 1.20 / 1_000_000
    return {
        "provider": "openai_luna",
        "model": "gpt-5.6-luna",
        "processing_time_ms": elapsed_ms,
        "image_count": len(prepared),
        "context": context,
        "result": result,
        "usage": {"input_tokens": input_tokens, "output_tokens": output_tokens, "total_tokens": int(usage.get("total_tokens") or input_tokens + output_tokens)},
        "estimated_cost_usd": round(estimated_cost, 8),
        "saved_to_database": False,
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


def _special_event_payload(tid: str, fmt: str) -> dict[str, Any] | None:
    """Return one normalized in-tournament draw/reveal card for the mobile clients."""
    try:
        if fmt == "double7":
            state = db.double7_combined_draw_state(tid)
            if state and not state.get("ack"):
                return {"kind": "double7_combined", "selected": bool(state.get("selected")), **state}
        if fmt == "double8":
            state = db.double_wb_draw_state(tid)
            if state and not state.get("ack"):
                return {"kind": "double8_wb", "selected": bool(state.get("selected")), **state}
        if fmt == "double5":
            state = db.double5_draw_state(tid)
            if state and not state.get("ack"):
                return {"kind": "double5_opponent", "selected": bool(state.get("selected")), **state}
        if fmt in ("groups6", "groups6_full", "groups7", "groups7_sf", "groups8_sf", "groups8_barrage"):
            state = db.group_playoff_reveal_state(tid)
            if state:
                # Pairings are already prepared by the scheduler; on mobile the user
                # only acknowledges the reveal before play continues.
                return {"kind": "group_playoffs", "selected": True, **state}
    except Exception:
        return None
    return None


def _setup_payload(tid: str) -> dict[str, Any]:
    b = db.setup_bundle(tid)
    t = b.get("tournament") or {}
    meta = b.get("meta") or {}
    extra = meta.get("extra") or {}
    players = b.get("players") or []
    fmt = str(meta.get("format_key") or "")
    player_rows = [{
        "player_id": p.get("player_id"), "name": p.get("name"), "team": p.get("team"),
        "team_reveal_order": int(p.get("team_reveal_order") or 0),
        "team_revealed": bool(int(p.get("team_revealed") or 0)),
        "group_name": p.get("group_name") or "",
    } for p in players]
    try:
        available = db.available_draft_teams(tid) if str(t.get("phase") or "") == "team_draft" else []
    except Exception:
        available = []
    try:
        wildcard_suggestions = db.available_wildcard_suggestions(tid)
    except Exception:
        wildcard_suggestions = list(WILDCARD_TEAM_SUGGESTIONS)
    tournament_payload = {
        "id": tid, "status": t.get("status"), "phase": t.get("phase"),
        "is_test": bool(int(t.get("is_test") or 0)), "player_count": int(meta.get("player_count") or len(players)),
        "format_key": fmt, "format_label": FORMAT_LABELS.get(fmt, fmt),
        "format_matches": FORMAT_MATCH_COUNTS.get(fmt, ""),
        "stake_per_player": float(extra.get("stake_per_player") or 0),
    }
    meta_payload = {
        "extra": {
            **extra,
            "draft_order_revealed": bool(extra.get("draft_order_revealed")),
            "draft_redraw_count": int(extra.get("draft_redraw_count") or 0),
            "pending_wildcard": extra.get("pending_wildcard"),
        },
        "draw": meta.get("draw") or {},
        "draw_revealed": bool(int(meta.get("draw_revealed") or 0)),
        "redraw_count": int(meta.get("redraw_count") or 0),
        "team_pool": list(meta.get("team_pool") or []),
    }
    # Hybrid response keeps the API convenient for the final app while remaining
    # easy to inspect from older/debug clients.
    return {
        "tournament": tournament_payload, "meta": meta_payload, "players": player_rows,
        "draft_available": available, "wildcard_suggestions": wildcard_suggestions,
        "pending_wildcard": extra.get("pending_wildcard"),
        **tournament_payload,
        "team_pool": meta_payload["team_pool"], "draw": meta_payload["draw"],
        "draw_revealed": meta_payload["draw_revealed"], "redraw_count": meta_payload["redraw_count"],
        "draft_order_revealed": bool(extra.get("draft_order_revealed")),
        "draft_redraw_count": int(extra.get("draft_redraw_count") or 0),
        "available_draft_teams": available,
    }


def live_payload() -> dict[str, Any]:
    tournament = db.current_tournament()
    if not tournament:
        return {"server_time": utc_now(), "api_version": API_VERSION, "tournament": None}

    tid = str(tournament["id"])
    phase=str(tournament.get("phase") or "")
    # During setup there are no playable matches yet; return the setup state directly.
    if phase in {"draft_order","team_draft","team_draw","structure_draw"}:
        setup=_setup_payload(tid)
        return {"server_time": utc_now(), "api_version": API_VERSION, "tournament": {
            "id":tid,"status":tournament.get("status"),"phase":phase,"is_test":bool(int(tournament.get("is_test") or 0)),
            "player_count":setup["player_count"],"format_key":setup["format_key"],"format_label":setup["format_label"],
            "format_matches":setup["format_matches"],"created_at":tournament.get("created_at"),"completed_at":tournament.get("completed_at"),
            "players":setup["players"],"current_match":None,"current_context":None,"next_match":None,"schedule":[],"standings":{},
            "live_scorers":[],"summary":None,"setup":setup,"special_event":None,"special_draw":None,
            "controls":{},"defer":{"allowed":False},"skip":{"allowed":False},"active_absences":[],
        }}

    bundle = db.bundle(tid)
    meta = bundle.get("meta") or {}
    extra = meta.get("extra") or {}
    matches = bundle.get("matches") or []
    schedule_raw = db.live_schedule_from(matches, extra)
    current_raw = db.current_match_from(matches, extra)
    current_context = None
    if current_raw and current_raw.get("home_player_id") and current_raw.get("away_player_id"):
        try: current_context = db.match_context(current_raw["home_player_id"], current_raw["away_player_id"])
        except Exception: current_context = None
    current_no = int(current_raw.get("match_no") or 0) if current_raw else 0
    next_raw = db.next_ready_match_from(matches, current_no, extra) if current_raw else None
    try: standings = db.standings(tid)
    except Exception: standings = {}
    try: scorers = db.tournament_live_scorers(tid, 5)
    except Exception: scorers=[]
    fmt = str(meta.get("format_key") or tournament.get("format_key") or "")
    summary = None
    if str(tournament.get("status")) == "completed":
        try: summary=db.tournament_summary(tid)
        except Exception: summary=None
    controls={}
    if current_raw:
        try: controls["defer"]=db.can_defer_match(tid,current_no)
        except Exception: controls["defer"]={"allowed":False}
        try: controls["skip"]=db.can_skip_match(tid,current_no)
        except Exception: controls["skip"]={"allowed":False}
    try: absences=db.active_absences(tid)
    except Exception: absences=[]
    special=_special_event_payload(tid,fmt) if str(tournament.get("status"))=="active" else None
    return {
        "server_time": utc_now(), "api_version": API_VERSION,
        "tournament": {
            "id": tid, "status": tournament.get("status"), "phase": tournament.get("phase"),
            "is_test": bool(int(tournament.get("is_test") or 0)), "player_count": int(meta.get("player_count") or tournament.get("player_count") or 0),
            "format_key": fmt, "format_label": FORMAT_LABELS.get(fmt, fmt), "format_matches": FORMAT_MATCH_COUNTS.get(fmt, ""),
            "created_at": tournament.get("created_at"), "completed_at": tournament.get("completed_at"),
            "players": [{"player_id":p.get("player_id"),"name":p.get("name"),"team":p.get("team"),"group_name":p.get("group_name")} for p in (bundle.get("players") or [])],
            "current_match": clean_match(current_raw) if current_raw else None,
            "current_context": current_context,
            "next_match": clean_match(next_raw) if next_raw else None,
            "schedule": [clean_match(m) for m in schedule_raw], "standings": standings, "live_scorers": scorers,
            "summary": summary, "setup": None, "special_event": special, "special_draw": special,
            "stake_per_player": float(extra.get("stake_per_player") or 0),
            "cash_player_ids": [str(x) for x in (extra.get("cash_player_ids") or [])],
            "cash_player_names": list(extra.get("cash_player_names") or []),
            "jackpot_cents": db.current_jackpot_cents(),
            "controls": controls, "defer": controls.get("defer") or {"allowed": False},
            "skip": controls.get("skip") or {"allowed": False}, "active_absences": absences,
        },
    }


@app.get("/api/v1/live")
def get_live() -> dict[str, Any]:
    return live_payload()


@app.get("/api/v1/config")
def get_config() -> dict[str, Any]:
    formats: dict[str, list[dict[str, str]]] = {}
    format_keys = {
        3: ["league3_final"], 4: ["league4_final", "double4"], 5: ["double5", "league5_final"],
        6: ["groups6", "groups6_full", "double6"], 7: ["double7", "groups7", "groups7_sf"],
        8: ["groups8_sf", "double8", "groups8_barrage"],
    }
    for count, keys in format_keys.items():
        formats[str(count)] = [{"key": k, "label": FORMAT_LABELS.get(k, k), "matches": FORMAT_MATCH_COUNTS.get(k, "")} for k in keys]
    return {
        "api_version": API_VERSION,
        "players": db.official_player_names(),
        "official_names": db.official_player_names(),
        "last_player_count": db.last_player_count(),
        "last_lineups": {str(n): db.last_lineup(n) for n in range(3, 9)},
        "last_stake": db.last_stake(),
        "jackpot_cents": db.current_jackpot_cents(),
        "fixed_teams": list(FIXED_TEAMS),
        "wildcard_suggestions": db.wildcard_team_suggestions(),
        "formats": formats,
        "format_labels": FORMAT_LABELS,
        "format_match_counts": FORMAT_MATCH_COUNTS,
    }


@app.post("/api/v1/tournaments")
def create_tournament(payload: CreateTournamentPayload, authorization: str | None = Header(default=None)) -> dict[str, Any]:
    _ensure_can_start(bool(payload.is_test), authorization)
    try:
        teams=allowed_teams(int(payload.player_count))
        tid=db.create_tournament(payload.player_names,int(payload.player_count),payload.format_key,teams,bool(payload.is_test),float(payload.stake_per_player),payload.cash_flags or None)
    except ValueError as exc: raise HTTPException(422,str(exc)) from exc
    return {"id":tid,"live":live_payload()}


@app.post("/api/v1/duels")
def create_duel(payload: CreateDuelPayload) -> dict[str, Any]:
    current=db.current_tournament()
    if current and str(current.get("status") or "") == "active": raise HTTPException(409,"Najpierw zakończ albo zresetuj bieżący FIFA Night.")
    if current: db.start_new()
    try: tid=db.create_duel(payload.player_names,payload.team_names,False,float(payload.stake_per_player),payload.cash_flags or None)
    except ValueError as exc: raise HTTPException(422,str(exc)) from exc
    return {"id":tid,"live":live_payload()}


@app.get("/api/v1/tournaments/{tournament_id}/setup")
def get_setup(tournament_id: str) -> dict[str, Any]:
    _current_tournament_or_409(tournament_id)
    return _setup_payload(tournament_id)


@app.post("/api/v1/tournaments/{tournament_id}/test-mode")
def set_test_mode(tournament_id: str, payload: TestModePayload, authorization: str | None = Header(default=None)) -> dict[str, Any]:
    _require_controller_header(authorization)
    _current_tournament_or_409(tournament_id)
    try: db.set_test_mode(tournament_id,bool(payload.is_test))
    except ValueError as exc: raise HTTPException(422,str(exc)) from exc
    return live_payload()


def _setup_action_control(tid: str, authorization: str | None) -> None:
    _require_game_control(tid,authorization)


@app.post("/api/v1/tournaments/{tournament_id}/draft/reveal")
def draft_reveal(tournament_id: str, authorization: str | None = Header(default=None)) -> dict[str, Any]:
    _setup_action_control(tournament_id,authorization)
    try: db.reveal_draft_order(tournament_id)
    except ValueError as exc: raise HTTPException(422,str(exc)) from exc
    return _setup_payload(tournament_id)


@app.post("/api/v1/tournaments/{tournament_id}/draft/reroll")
def draft_reroll(tournament_id: str, authorization: str | None = Header(default=None)) -> dict[str, Any]:
    _setup_action_control(tournament_id,authorization)
    try: db.reroll_draft_order(tournament_id)
    except ValueError as exc: raise HTTPException(422,str(exc)) from exc
    return _setup_payload(tournament_id)


@app.post("/api/v1/tournaments/{tournament_id}/draft/confirm")
def draft_confirm(tournament_id: str, authorization: str | None = Header(default=None)) -> dict[str, Any]:
    _setup_action_control(tournament_id,authorization)
    try: db.confirm_draft_order(tournament_id)
    except ValueError as exc: raise HTTPException(422,str(exc)) from exc
    return _setup_payload(tournament_id)


@app.post("/api/v1/tournaments/{tournament_id}/draft/pick")
def draft_pick(tournament_id: str, payload: DraftPickPayload, authorization: str | None = Header(default=None)) -> dict[str, Any]:
    _setup_action_control(tournament_id,authorization)
    try: db.draft_pick(tournament_id,payload.player_id,payload.slot,payload.wildcard_name)
    except ValueError as exc: raise HTTPException(422,str(exc)) from exc
    return _setup_payload(tournament_id)


@app.post("/api/v1/tournaments/{tournament_id}/teams/reveal")
def teams_reveal(tournament_id: str, authorization: str | None = Header(default=None)) -> dict[str, Any]:
    _setup_action_control(tournament_id,authorization)
    try: revealed=db.reveal_next_team(tournament_id)
    except ValueError as exc: raise HTTPException(422,str(exc)) from exc
    return {"revealed":revealed,"setup":_setup_payload(tournament_id)}


@app.post("/api/v1/tournaments/{tournament_id}/wildcard/confirm")
def wildcard_confirm(tournament_id: str, payload: WildcardPayload, authorization: str | None = Header(default=None)) -> dict[str, Any]:
    _setup_action_control(tournament_id,authorization)
    try: team=db.confirm_wildcard_team(tournament_id,payload.player_id,payload.team_name)
    except ValueError as exc: raise HTTPException(422,str(exc)) from exc
    return {"team":team,"setup":_setup_payload(tournament_id)}


@app.post("/api/v1/tournaments/{tournament_id}/teams/finish")
def teams_finish(tournament_id: str, authorization: str | None = Header(default=None)) -> dict[str, Any]:
    _setup_action_control(tournament_id,authorization)
    try: db.start_structure_draw(tournament_id)
    except ValueError as exc: raise HTTPException(422,str(exc)) from exc
    return _setup_payload(tournament_id)


@app.post("/api/v1/tournaments/{tournament_id}/structure/reveal")
def structure_reveal(tournament_id: str, authorization: str | None = Header(default=None)) -> dict[str, Any]:
    _setup_action_control(tournament_id,authorization)
    try: db.reveal_structure(tournament_id)
    except ValueError as exc: raise HTTPException(422,str(exc)) from exc
    return _setup_payload(tournament_id)


@app.post("/api/v1/tournaments/{tournament_id}/structure/reroll")
def structure_reroll(tournament_id: str, authorization: str | None = Header(default=None)) -> dict[str, Any]:
    _setup_action_control(tournament_id,authorization)
    try: db.reroll_structure(tournament_id)
    except ValueError as exc: raise HTTPException(422,str(exc)) from exc
    return _setup_payload(tournament_id)


@app.post("/api/v1/tournaments/{tournament_id}/structure/confirm")
def structure_confirm(tournament_id: str, authorization: str | None = Header(default=None)) -> dict[str, Any]:
    _setup_action_control(tournament_id,authorization)
    try: db.confirm_structure(tournament_id)
    except ValueError as exc: raise HTTPException(422,str(exc)) from exc
    return live_payload()


@app.post("/api/v1/tournaments/{tournament_id}/special/{kind}/reveal")
def special_reveal(tournament_id: str, kind: str, authorization: str | None = Header(default=None)) -> dict[str, Any]:
    _require_game_control(tournament_id,authorization)
    try:
        if kind=="double7_combined": db.reveal_double7_combined_draw(tournament_id)
        elif kind=="double8_wb": db.reveal_double_wb_draw(tournament_id)
        elif kind=="double5_opponent": db.reveal_double5_opponent(tournament_id)
        else: raise ValueError("To losowanie nie ma osobnej akcji losuj.")
    except ValueError as exc: raise HTTPException(422,str(exc)) from exc
    return live_payload()


@app.post("/api/v1/tournaments/{tournament_id}/special/{kind}/ack")
def special_ack(tournament_id: str, kind: str, authorization: str | None = Header(default=None)) -> dict[str, Any]:
    _require_game_control(tournament_id,authorization)
    try:
        if kind=="double7_combined": db.ack_double7_combined_draw(tournament_id)
        elif kind=="double8_wb": db.ack_double_wb_draw(tournament_id)
        elif kind=="double5_opponent": db.ack_double5_draw(tournament_id)
        elif kind=="group_playoffs": db.ack_group_playoffs(tournament_id)
        else: raise ValueError("Nieznany etap specjalny.")
    except ValueError as exc: raise HTTPException(422,str(exc)) from exc
    return live_payload()


@app.post("/api/v1/tournaments/{tournament_id}/new")
def start_new_tournament(tournament_id: str) -> dict[str, Any]:
    current = db.current_tournament()
    if current and str(current.get("id")) != str(tournament_id):
        raise HTTPException(409, "Na serwerze jest już inna bieżąca rozgrywka.")
    if current and str(current.get("status") or "") == "active":
        raise HTTPException(409, "Najpierw zakończ albo zresetuj bieżącą rozgrywkę.")
    db.start_new()
    return live_payload()


@app.get("/api/v1/stats/players")
def get_player_stats() -> dict[str, Any]:
    return {"players": db.all_time_stats(), "server_time": utc_now()}


@app.get("/api/v1/stats/records")
def get_records() -> dict[str, Any]:
    return {"records": db.all_time_records(), "server_time": utc_now()}


@app.get("/api/v1/stats/teams-scorers")
def get_teams_scorers() -> dict[str, Any]:
    return {"teams":db.team_stats(),"scorers":db.scorer_stats(),"event_stats":db.player_event_stats(),"server_time":utc_now()}


@app.get("/api/v1/stats/finance")
def get_finance_stats() -> dict[str, Any]:
    return {"ranking":db.financial_ranking(),"tournaments":db.settlement_tournaments(200),"jackpot_cents":db.current_jackpot_cents()}


@app.get("/api/v1/stats/teams")
def get_team_stats() -> dict[str, Any]:
    return {"teams": db.team_stats(), "server_time": utc_now()}

@app.get("/api/v1/stats/scorers")
def get_scorer_stats() -> dict[str, Any]:
    return {"scorers": db.scorer_stats(), "server_time": utc_now()}

@app.get("/api/v1/finance/tournaments")
def get_finance_tournaments() -> dict[str, Any]:
    data = get_finance_stats()
    return {"items": data.get("tournaments") or [], "ranking": data.get("ranking") or [], "jackpot_cents": data.get("jackpot_cents") or 0}


@app.get("/api/v1/players/{player_id}")
def get_player_profile(player_id: str) -> dict[str, Any]:
    profile = db.player_profile(player_id)
    if not profile: raise HTTPException(404, "Nie znaleziono gracza.")
    try:
        center = db.achievement_center()
        achievement = next((p for p in center.get("players", []) if str(p.get("player_id")) == str(player_id)), None)
    except Exception: achievement = None
    try: awards = db.player_award_wins(player_id)
    except Exception: awards = []
    try: trophy=db.player_trophy_case(player_id)
    except Exception: trophy={}
    try: event_stats=db.player_detailed_event_stats(player_id)
    except Exception: event_stats={}
    return {"profile": profile, "achievement": achievement, "awards": awards, "trophy_case":trophy,"event_stats":event_stats}


@app.get("/api/v1/awards/{year}")
def get_awards(year: int) -> dict[str, Any]:
    if year < 2020 or year > 2100: raise HTTPException(422, "Nieprawidłowy rok.")
    return db.annual_awards(int(year))


@app.get("/api/v1/milestones")
def get_milestones() -> dict[str, Any]:
    return db.global_milestones()


@app.get("/api/v1/tournaments/{tournament_id}/matches/{match_no}/scorer-options")
def scorer_options(tournament_id: str, match_no: int) -> dict[str, Any]:
    match = next((m for m in db.matches(tournament_id) if int(m.get("match_no") or 0) == int(match_no)), None)
    if not match: raise HTTPException(404, "Nie znaleziono meczu.")
    return {
        "home":{"team":match.get("home_team") or "","options":db.team_scorer_options(match.get("home_team") or "") if match.get("home_team") else []},
        "away":{"team":match.get("away_team") or "","options":db.team_scorer_options(match.get("away_team") or "") if match.get("away_team") else []},
    }


@app.post("/api/v1/tournaments/{tournament_id}/matches/{match_no}/scorers")
def add_match_scorer(tournament_id: str, match_no: int, payload: AddScorerPayload, authorization: str | None = Header(default=None)) -> dict[str, Any]:
    _require_game_control(tournament_id,authorization)
    match=next((m for m in db.matches(tournament_id) if int(m.get("match_no") or 0)==int(match_no)),None)
    if not match: raise HTTPException(404,"Nie znaleziono meczu.")
    side=payload.side.lower().strip()
    if side not in {"home","away"}: raise HTTPException(422,"Strona musi być home albo away.")
    team=str(match.get(f"{side}_team") or "").strip()
    if not team: raise HTTPException(422,"Brak drużyny dla tej strony meczu.")
    try: db.add_team_scorers(team,[payload.name.strip()])
    except ValueError as exc: raise HTTPException(422,str(exc)) from exc
    return scorer_options(tournament_id,match_no)


def _scorers_to_dict(payload: ScorersPayload | None, match: dict[str, Any]) -> dict[str, Any] | None:
    if payload is None: return None
    out: dict[str, Any] = {}
    for side in ("home", "away"):
        side_payload = getattr(payload, side)
        if side_payload is None:
            out[side] = {"team": match.get(f"{side}_team") or "", "items": []}; continue
        team = side_payload.team.strip() or str(match.get(f"{side}_team") or "")
        out[side] = {"team": team, "items": [{"name": x.name.strip(), "goals": int(x.goals)} for x in side_payload.items if x.name.strip()]}
    return out


def _normalize_events_for_save(match: dict[str, Any], fmt: str, hs: int, ass: int, events: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Canonicalize user-corrected scan events and prove that all match goals are accounted for.

    The client may edit event type, footballer and FIFA Night side after scan-preview.
    Never trust credited_player_id/synthetic_de from the client: derive both again here.
    """
    allowed={"normal_goal","penalty_goal","own_goal","penalty_miss","yellow_card","red_card","injury","substitution"}
    home_pid=str(match.get("home_player_id") or "")
    away_pid=str(match.get("away_player_id") or "")
    participant_ids={home_pid,away_pid}
    participant_ids.discard("")
    if len(participant_ids)!=2:
        raise ValueError("Ten mecz nie ma dwóch ustalonych graczy.")
    info={
        home_pid:{"name":match.get("home_name"),"team":str(match.get("home_team") or "")},
        away_pid:{"name":match.get("away_name"),"team":str(match.get("away_team") or "")},
    }
    normalized=[]
    for original_order,raw in enumerate(events,1):
        if not isinstance(raw,dict):
            continue
        typ=str(raw.get("event_type") or "unknown").strip()
        if typ not in allowed:
            # Same behaviour as the Streamlit editor: unknown/unsupported rows are ignored.
            continue
        actor_pid=str(raw.get("actor_player_id") or "").strip()
        if actor_pid not in participant_ids:
            raise ValueError(f"Wydarzenie {original_order}: wybierz gracza FIFA Night, którego dotyczy zdarzenie.")
        credited_pid=None
        if typ in {"normal_goal","penalty_goal"}:
            credited_pid=actor_pid
        elif typ=="own_goal":
            credited_pid=away_pid if actor_pid==home_pid else home_pid
        footballer=" ".join(str(raw.get("footballer_name") or "").strip().split())
        related=" ".join(str(raw.get("related_footballer_name") or "").strip().split())
        minute=raw.get("minute");stoppage=raw.get("stoppage")
        try:minute=int(minute) if minute is not None and str(minute)!="" else None
        except Exception:minute=None
        try:stoppage=int(stoppage) if stoppage is not None and str(stoppage)!="" else None
        except Exception:stoppage=None
        # User corrections may arrive as a display label such as 90+2. Store a
        # punctuation-free canonical label; the UI adds the minute mark exactly once.
        raw_minute_label=str(raw.get("minute_label") or "").strip().replace("’","").replace("′","").replace("'","")
        label_match=re.fullmatch(r"(\d{1,3})(?:\s*\+\s*(\d{1,2}))?",raw_minute_label) if raw_minute_label else None
        if label_match:
            minute=int(label_match.group(1))
            stoppage=int(label_match.group(2)) if label_match.group(2) else None
        minute_label=(f"{minute}+{stoppage}" if minute is not None and stoppage is not None else str(minute) if minute is not None else "")
        actor=info[actor_pid];credited=info.get(str(credited_pid or ""))
        normalized.append({
            "_original_order":original_order,"event_type":typ,"minute":minute,"stoppage":stoppage,
            "minute_label":minute_label,
            "footballer_name":footballer,"related_footballer_name":related,
            "actor_player_id":actor_pid,"actor_player_name":actor.get("name"),"actor_team_name":actor.get("team"),
            "credited_player_id":credited_pid,"credited_player_name":credited.get("name") if credited else None,
            "credited_team_name":credited.get("team") if credited else None,
            "synthetic_de":False,"confidence":raw.get("confidence") or "manual",
            "source_images":list(raw.get("source_images") or []),
        })
    normalized.sort(key=lambda e:(999 if e.get("minute") is None else int(e["minute"]),-1 if e.get("stoppage") is None else int(e["stoppage"]),int(e.get("_original_order") or 9999)))
    for idx,e in enumerate(normalized,1):
        e["event_order"]=idx
        e.pop("_original_order",None)
    # The Winners Bracket bonus is implemented as the first visible own goal credited to HOME.
    if fmt.startswith("double") and str(match.get("stage") or "")=="FINAL":
        for e in normalized:
            if e.get("event_type")=="own_goal" and str(e.get("credited_player_id") or "")==home_pid:
                e["synthetic_de"]=True
                break
    goal_types={"normal_goal","penalty_goal","own_goal"}
    hg=sum(1 for e in normalized if e.get("event_type") in goal_types and str(e.get("credited_player_id") or "")==home_pid)
    ag=sum(1 for e in normalized if e.get("event_type") in goal_types and str(e.get("credited_player_id") or "")==away_pid)
    missing_names=sum(1 for e in normalized if e.get("event_type") in {"normal_goal","penalty_goal"} and not str(e.get("footballer_name") or "").strip())
    validation={
        "home_goals":hg,"away_goals":ag,"missing_home":max(int(hs)-hg,0),"missing_away":max(int(ass)-ag,0),
        "over":hg>int(hs) or ag>int(ass),"missing_goal_names":missing_names,
        "complete":hg==int(hs) and ag==int(ass) and missing_names==0,
    }
    if not validation["complete"]:
        details=[]
        if validation["missing_home"]:details.append(f"HOME: brakuje {validation['missing_home']} gola/goli")
        if validation["missing_away"]:details.append(f"AWAY: brakuje {validation['missing_away']} gola/goli")
        if validation["over"]:details.append(f"wydarzenia dają {hg}:{ag}, a wynik to {int(hs)}:{int(ass)}")
        if missing_names:details.append("gol lub gol z karnego nie ma wpisanego piłkarza")
        raise ValueError("Odczyt wydarzeń wymaga korekty: "+("; ".join(details) or "sprawdź gole i ich przypisanie."))
    return normalized,validation


@app.post("/api/v1/tournaments/{tournament_id}/matches/{match_no}/result")
def save_match_result(tournament_id: str, match_no: int, payload: ResultPayload, authorization: str | None = Header(default=None)) -> dict[str, Any]:
    tournament=_current_tournament_or_409(tournament_id)
    _require_game_control(tournament_id,authorization)
    match=next((m for m in db.matches(tournament_id) if int(m.get("match_no") or 0)==int(match_no)),None)
    if not match: raise HTTPException(404,"Nie znaleziono meczu.")
    if match.get("home_score") is not None or str(match.get("match_status") or "pending")=="skipped":
        raise HTTPException(409,"Ten mecz został już zapisany na innym urządzeniu. Odświeżono stan FIFA Night.")
    current=(live_payload().get("tournament") or {}).get("current_match")
    if not current or int(current.get("match_no") or 0)!=int(match_no):
        raise HTTPException(409,"Kolejność FIFA Night zmieniła się na innym urządzeniu. Odśwież ekran.")
    scorers=_scorers_to_dict(payload.scorers,match)
    fmt=str(tournament.get("format_key") or "")
    events=payload.events
    if scorers and events is None:
        wb_bonus=fmt.startswith("double") and str(match.get("stage"))=="FINAL"
        expected_home=max(0,int(payload.home_score)-(1 if wb_bonus else 0));expected_away=int(payload.away_score)
        home_sum=sum(int(x["goals"]) for x in scorers.get("home",{}).get("items",[]));away_sum=sum(int(x["goals"]) for x in scorers.get("away",{}).get("items",[]))
        if home_sum>expected_home or away_sum>expected_away: raise HTTPException(422,"Suma wpisanych goli strzelców nie może przekraczać wyniku meczu.")
    if events is not None:
        try:events,_=_normalize_events_for_save(match,fmt,int(payload.home_score),int(payload.away_score),events)
        except ValueError as exc:raise HTTPException(422,str(exc)) from exc
    try:
        db.save_result(tournament_id,int(match_no),int(payload.home_score),int(payload.away_score),payload.home_penalties,payload.away_penalties,scorers,events)
    except ValueError as exc: raise HTTPException(422,str(exc)) from exc
    return live_payload()


@app.post("/api/v1/tournaments/{tournament_id}/undo-last")
def undo_last(tournament_id: str, authorization: str | None = Header(default=None)) -> dict[str, Any]:
    _require_game_control(tournament_id,authorization)
    match_no=db.undo_last_result(tournament_id)
    if match_no is None: raise HTTPException(409,"Nie ma wyniku ani pominięcia do cofnięcia.")
    payload=live_payload();payload["undone_match_no"]=int(match_no);return payload


@app.post("/api/v1/tournaments/{tournament_id}/matches/{match_no}/defer")
def defer_match(tournament_id: str, match_no: int, authorization: str | None = Header(default=None)) -> dict[str, Any]:
    _require_game_control(tournament_id,authorization)
    try: db.defer_match(tournament_id,int(match_no))
    except ValueError as exc: raise HTTPException(422,str(exc)) from exc
    return live_payload()


@app.post("/api/v1/tournaments/{tournament_id}/matches/{match_no}/skip")
def skip_match(tournament_id: str, match_no: int, authorization: str | None = Header(default=None)) -> dict[str, Any]:
    _require_game_control(tournament_id,authorization)
    try: db.skip_match(tournament_id,int(match_no))
    except ValueError as exc: raise HTTPException(422,str(exc)) from exc
    return live_payload()


@app.post("/api/v1/tournaments/{tournament_id}/abandon")
def abandon_tournament(tournament_id: str, authorization: str | None = Header(default=None)) -> dict[str, Any]:
    _require_controller_header(authorization)
    _current_tournament_or_409(tournament_id)
    try: result=db.abandon_tournament(tournament_id)
    except ValueError as exc: raise HTTPException(422,str(exc)) from exc
    return {"result":result,"live":live_payload()}


@app.post("/api/v1/tournaments/{tournament_id}/reset")
def reset_tournament(tournament_id: str, authorization: str | None = Header(default=None)) -> dict[str, Any]:
    _require_game_control(tournament_id,authorization)
    try: db.reset_current(tournament_id)
    except ValueError as exc: raise HTTPException(422,str(exc)) from exc
    return live_payload()


@app.get("/api/v1/history")
def get_history(include_tests: bool = Query(default=False)) -> dict[str, Any]:
    items=[]
    for row in db.completed_tournaments(include_tests=bool(include_tests),limit=500):
        item=dict(row)
        fmt=str(item.get("format_key") or "")
        item["format_label"]=FORMAT_LABELS.get(fmt,fmt)
        item["unfinished"]=str(item.get("status") or "")=="abandoned"
        item["is_duel"]=fmt=="duel1v1"
        items.append(item)
    return {"items":items}


@app.get("/api/v1/history/{tournament_id}")
def get_history_detail(tournament_id: str) -> dict[str, Any]:
    rows=db.completed_tournaments(include_tests=True,limit=500)
    row=next((x for x in rows if str(x.get("id"))==str(tournament_id)),None)
    if not row: raise HTTPException(404,"Nie znaleziono pozycji w Historii.")
    b=db.bundle(tournament_id);t=b.get("tournament") or {};fmt=str((b.get("meta") or {}).get("format_key") or row.get("format_key") or "")
    player_names={str(p.get("id") or p.get("player_id") or ""):str(p.get("name") or "") for p in (b.get("players") or [])}
    detailed=[]
    for m in b.get("matches") or []:
        item=clean_match(m)
        try:item["scorers"]=db.match_scorers(tournament_id,int(m.get("match_no") or 0))
        except Exception:item["scorers"]=[]
        try:
            item["events"]=db.match_events(tournament_id,int(m.get("match_no") or 0))
            for event in item["events"]:
                event["actor_player_name"]=player_names.get(str(event.get("actor_player_id") or "")) or event.get("actor_player_name")
                event["credited_player_name"]=player_names.get(str(event.get("credited_player_id") or "")) or event.get("credited_player_name")
        except Exception:item["events"]=[]
        detailed.append(item)
    try: standings=db.standings(tournament_id)
    except Exception: standings={}
    summary=None
    if str(t.get("status") or "")=="completed":
        try: summary=db.tournament_summary(tournament_id)
        except Exception: summary=None
    try:finance=db.finance_event(tournament_id)
    except Exception:finance=None
    try:unlocked=db.achievements_unlocked_in_tournament(tournament_id)
    except Exception:unlocked=[]
    try:milestones=db.milestones_in_tournament(tournament_id)
    except Exception:milestones=[]
    tournament_payload=dict(t)
    tournament_payload["unfinished"]=str(tournament_payload.get("status") or "")=="abandoned"
    tournament_payload["format_label"]=FORMAT_LABELS.get(fmt,fmt)
    archive_payload=dict(row)
    archive_payload["unfinished"]=str(archive_payload.get("status") or "")=="abandoned"
    archive_payload["format_label"]=FORMAT_LABELS.get(fmt,fmt)
    return {"archive":archive_payload,"tournament":tournament_payload,"meta":b.get("meta") or {},"players":b.get("players") or [],"matches":detailed,"standings":standings,"summary":summary,"finance":finance,"achievements":unlocked,"milestones":milestones,"format_label":FORMAT_LABELS.get(fmt,fmt)}


@app.delete("/api/v1/history/{tournament_id}")
def delete_history_item(tournament_id: str, authorization: str | None = Header(default=None)) -> dict[str, Any]:
    _require_controller_header(authorization)
    try:deleted=db.delete_archived_tournament(tournament_id)
    except ValueError as exc: raise HTTPException(422,str(exc)) from exc
    return {"deleted":deleted}


@app.post("/api/v1/finance/settlement")
def settlement(payload: SettlementRequest) -> dict[str, Any]:
    return db.settlement_summary(payload.tournament_ids)


@app.post("/api/v1/finance/settled")
def set_settled(payload: SettledPayload, authorization: str | None = Header(default=None)) -> dict[str, Any]:
    _require_controller_header(authorization)
    count=db.set_tournaments_settled(payload.tournament_ids,bool(payload.settled))
    return {"updated":count,"finance":get_finance_stats()}


@app.get("/api/v1/exports/tournament/{tournament_id}/summary.png")
def export_tournament_png(tournament_id: str) -> Response:
    rows=db.completed_tournaments(include_tests=True,limit=500)
    row=next((x for x in rows if str(x.get("id"))==str(tournament_id)),None)
    if not row: raise HTTPException(404,"Nie znaleziono turnieju.")
    if str(row.get("status") or "")!="completed": raise HTTPException(422,"Niedokończony turniej nie ma końcowego podsumowania PNG.")
    b=db.bundle(tournament_id);summary=db.tournament_summary(tournament_id)
    png=generate_summary_png(b,summary,FORMAT_LABELS,row.get("official_no"))
    return Response(content=png,media_type="image/png",headers={"Content-Disposition":f'inline; filename="fifa-night-{row.get("official_no") or "test"}.png"'})


@app.get("/api/v1/exports/settlement.png")
def export_settlement_png(ids: str = Query(default="")) -> Response:
    tids=[x.strip() for x in ids.split(",") if x.strip()]
    if not tids: raise HTTPException(422,"Wybierz co najmniej jeden turniej.")
    data=db.settlement_summary(tids)
    labels=[]
    for e in data.get("tournaments") or []:
        labels.append(f"{FORMAT_LABELS.get(str(e.get('format_key') or ''),str(e.get('format_key') or ''))} • {str(e.get('completed_at') or e.get('created_at') or '')[:10]}")
    return Response(content=generate_settlement_png(data,labels),media_type="image/png")


@app.get("/api/v1/exports/year/{year}/summary.png")
def export_year_png(year: int) -> Response:
    data=db.annual_awards(year);overview=data.get("overview") or {};cats=data.get("categories") or []
    highlights=[]
    if overview.get("top_player"):highlights.append({"label":"Lider klasyfikacji Gracza Roku","value":overview.get("top_player")})
    if overview.get("top_team"):highlights.append({"label":"Najwyżej sklasyfikowana drużyna","value":overview.get("top_team")})
    match_cat=next((c for c in cats if c.get("key")=="match_year"),None)
    if match_cat and match_cat.get("candidates"):highlights.append({"label":"Mecz Roku — lider na teraz","value":match_cat["candidates"][0].get("name")})
    return Response(content=generate_year_summary_png(year,overview,highlights),media_type="image/png")


@app.get("/api/v1/exports/year/{year}/awards.png")
def export_awards_png(year: int) -> Response:
    data=db.annual_awards(year);sels=data.get("selections") or {};rows=[]
    for cat in data.get("categories") or []:
        sel=sels.get(cat.get("key")) or {}
        if sel.get("name"):
            title=str(cat.get("title") or "");title=title.split(" ",1)[1] if " " in title else title
            rows.append({"title":title,"name":sel.get("name")})
    return Response(content=generate_awards_png(year,rows),media_type="image/png")

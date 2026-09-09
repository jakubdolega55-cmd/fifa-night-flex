from __future__ import annotations

import base64
import io
import hashlib
import hmac
import json
import os
import secrets
import time
from datetime import datetime, timezone
from typing import Any

import httpx
from fastapi import Depends, FastAPI, File, Form, Header, HTTPException, UploadFile
from PIL import Image, ImageOps
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

CRITICAL: classify events from the VISUAL ICON, not from OCR text or assumptions.
EA FC icon rules used by FIFA Night:
- plain WHITE football/ball icon = normal_goal
- WHITE football/ball icon with a small CHECK/TICK badge = penalty_goal (a scored penalty during the match)
- RED football/ball icon = own_goal. It is NOT a missed penalty.
- yellow rectangular card = yellow_card
- red rectangular card = red_card
- injury/medical event (injury symbol, medical/cross icon or explicit injury indication) = injury
- classify injury ONLY when the event is visibly an injury; until the exact EA FC icon is confirmed, use unknown when uncertain
- player names with green up / red down arrows = substitution, NOT a goal
- use penalty_miss only when the screen visibly shows a missed-penalty event distinct from the RED own-goal ball
- if an icon cannot be identified reliably, use unknown

Goal field rules:
- normal_goal: player = scorer; side = scorer's visible side; credited_side = same side; own_goal_by = null
- penalty_goal: player = scorer; side = scorer's visible side; credited_side = same side; own_goal_by = null
- own_goal: player MUST be null; own_goal_by = the player whose name is shown with the red-ball icon; side = that player's visible side; credited_side = the OPPOSITE side
- own goals count toward the match score but must never be credited as a scorer goal

For injury: player = the visibly injured footballer; side = that footballer's visible side; credited_side = unknown.
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
    events = result.get("events") or []
    for event in events:
        if not isinstance(event, dict):
            continue
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
    x_admin_password: str | None = Header(default=None, alias="X-Admin-Password"),
) -> dict[str, Any]:
    """Context-aware OpenAI scan for one real FIFA Night match. Never writes to Neon."""
    _require_vision_test_admin(x_admin_password)
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
        raise HTTPException(503, "OPENAI_API_KEY nie jest ustawiony na serwerze API.")
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
        raise HTTPException(504, "OpenAI nie odpowiedział w ciągu 75 sekund.") from exc
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

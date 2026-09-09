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
VISION_MAX_IMAGES = 5


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
                    "image_indices": {"type": "array", "items": {"type": "integer", "minimum": 1, "maximum": 5}},
                    "minute": {"type": ["integer", "null"], "minimum": 0, "maximum": 130},
                    "stoppage": {"type": ["integer", "null"], "minimum": 0, "maximum": 30},
                    "minute_label": {"type": ["string", "null"]},
                    "side": {"type": "string", "enum": ["left", "right", "unknown"]},
                    "event_type": {
                        "type": "string",
                        "enum": ["goal", "yellow_card", "red_card", "substitution", "penalty_miss", "other", "unknown"],
                    },
                    "player": {"type": ["string", "null"]},
                    "related_player": {"type": ["string", "null"]},
                    "confidence": {"type": "string", "enum": ["high", "medium", "low"]},
                },
                "required": [
                    "image_indices", "minute", "stoppage", "minute_label", "side",
                    "event_type", "player", "related_player", "confidence"
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
All supplied images belong to the SAME match. There may be 1 to 5 screenshots and adjacent screenshots may overlap.

Extract only facts that are actually visible. Do not invent missing goals or events from the final score.
Read the score and the two labels at the top when visible. Use left/right exactly as shown on screen.

Most important: classify events using the VISUAL ICON and layout, not only OCR text.
- football/ball icon = goal
- yellow rectangular card = yellow_card
- red rectangular card = red_card
- a pair of player names with green up / red down arrows = substitution, NOT a goal
- if an icon or event cannot be identified reliably, use unknown
Different events can occur in the same minute on opposite sides.

Return each visible event once. If the same event appears on overlapping screenshots, merge it and include all matching image_indices.
Preserve player names as displayed. Do not guess full names.
If the screenshots clearly show only a scrolled fragment of the event timeline, set event_list_complete=false and needs_more_images=true.
If the full event list is visible across all supplied screenshots, set event_list_complete=true and needs_more_images=false.
A final score such as 6:5 does NOT mean that 11 goal events must be visible in the supplied images.
"""


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
    """Temporary EA FC vision benchmark. Accepts 1-5 images and never writes to Neon."""
    _require_vision_test_admin(x_admin_password)
    provider = str(provider or "google_ocr").strip().lower()
    aliases = {
        "google": "google_ocr",
        "google_cloud_vision": "google_ocr",
        "ocr": "google_ocr",
        "openai": "openai_luna",
        "luna": "openai_luna",
        "gemini": "gemini_38_flash",
    }
    provider = aliases.get(provider, provider)
    if provider not in {"google_ocr", "openai_luna", "gemini_38_flash"}:
        raise HTTPException(422, "Nieznany provider testu Vision.")
    if not 1 <= len(images) <= VISION_MAX_IMAGES:
        raise HTTPException(422, f"Wyślij od 1 do {VISION_MAX_IMAGES} zdjęć.")

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
                "https://generativelanguage.googleapis.com/v1beta/models/gemini-3.8-flash:generateContent",
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
    usage = payload.get("usageMetadata") or {}
    input_tokens = int(usage.get("promptTokenCount") or 0)
    answer_tokens = int(usage.get("candidatesTokenCount") or 0)
    thinking_tokens = int(usage.get("thoughtsTokenCount") or 0)
    output_tokens = answer_tokens + thinking_tokens
    paid_estimate = input_tokens * 0.75 / 1_000_000 + output_tokens * 3.75 / 1_000_000
    return {
        "provider": "gemini_38_flash",
        "model": "gemini-3.8-flash",
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

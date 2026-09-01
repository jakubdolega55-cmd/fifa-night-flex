from __future__ import annotations

from datetime import datetime
from io import BytesIO
from textwrap import wrap

from PIL import Image, ImageDraw, ImageFont

WIDTH = 1080
HEIGHT = 1080
BG = "#0b1020"
CARD = "#121a2b"
CARD_ALT = "#18233b"
ACCENT = "#23c55e"
ACCENT_2 = "#38bdf8"
TEXT = "#f8fafc"
MUTED = "#94a3b8"
GOLD = "#facc15"
SILVER = "#cbd5e1"


_FONT_CACHE: dict[tuple[int, bool], ImageFont.FreeTypeFont | ImageFont.ImageFont] = {}


def _font(size: int, bold: bool = False):
    key = (size, bold)
    if key in _FONT_CACHE:
        return _FONT_CACHE[key]
    candidates = []
    if bold:
        candidates = [
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
            "/usr/share/fonts/dejavu/DejaVuSans-Bold.ttf",
        ]
    else:
        candidates = [
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            "/usr/share/fonts/dejavu/DejaVuSans.ttf",
        ]
    for path in candidates:
        try:
            f = ImageFont.truetype(path, size)
            _FONT_CACHE[key] = f
            return f
        except Exception:
            pass
    f = ImageFont.load_default()
    _FONT_CACHE[key] = f
    return f


def _fit_text(draw: ImageDraw.ImageDraw, text: str, max_width: int, start_size: int, min_size: int = 24, bold: bool = False):
    text = str(text or "—")
    size = start_size
    while size >= min_size:
        f = _font(size, bold=bold)
        bbox = draw.textbbox((0, 0), text, font=f)
        if bbox[2] - bbox[0] <= max_width:
            return f
        size -= 2
    return _font(min_size, bold=bold)


def _line(draw: ImageDraw.ImageDraw, xy, fill, width=2):
    draw.line(xy, fill=fill, width=width)


def _round_rect(draw: ImageDraw.ImageDraw, box, fill, outline=None, radius=28, width=2):
    draw.rounded_rectangle(box, radius=radius, fill=fill, outline=outline, width=width)


def _draw_wrapped(draw: ImageDraw.ImageDraw, text: str, box: tuple[int, int, int, int], font, fill=TEXT, line_gap: int = 6, max_lines: int = 3):
    x1, y1, x2, y2 = box
    width = max(1, x2 - x1)
    words = (text or "—").split()
    lines: list[str] = []
    current = ""
    for w in words:
        trial = (current + " " + w).strip()
        bbox = draw.textbbox((0, 0), trial, font=font)
        if bbox[2] - bbox[0] <= width:
            current = trial
        else:
            if current:
                lines.append(current)
            current = w
            if len(lines) >= max_lines - 1:
                break
    if current and len(lines) < max_lines:
        lines.append(current)
    if len(lines) == max_lines and len(words) > 0:
        remainder = " ".join(words)
        flat = " ".join(lines)
        if len(remainder) > len(flat):
            last = lines[-1]
            while last and draw.textbbox((0, 0), last + "…", font=font)[2] > width:
                last = last[:-1]
            lines[-1] = last.rstrip() + "…"
    y = y1
    for line in lines:
        draw.text((x1, y), line, font=font, fill=fill)
        bbox = draw.textbbox((0, 0), line, font=font)
        y += (bbox[3] - bbox[1]) + line_gap


def _date_text(value: str | None) -> str:
    if not value:
        return "bez daty"
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).strftime("%d.%m.%Y")
    except Exception:
        return str(value)[:10]


def _final_score(bundle: dict) -> tuple[str, str, str]:
    matches = [m for m in bundle.get("matches", []) if m.get("home_score") is not None]
    finals = [m for m in matches if m.get("stage") in ("FINAL", "RESET_FINAL")]
    if not finals:
        return "—", "—", "—"
    m = finals[-1]
    home = str(m.get("home_name") or "—")
    away = str(m.get("away_name") or "—")
    score = f"{m.get('home_score', 0)}:{m.get('away_score', 0)}"
    if m.get("home_penalties") is not None and m.get("away_penalties") is not None:
        score += f"  (k. {m['home_penalties']}:{m['away_penalties']})"
    return home, away, score


def generate_summary_png(bundle: dict, summary: dict, format_labels: dict[str, str], official_no: int | None = None) -> bytes:
    img = Image.new("RGB", (WIDTH, HEIGHT), BG)
    draw = ImageDraw.Draw(img)

    # subtle background panels
    _round_rect(draw, (28, 28, WIDTH - 28, HEIGHT - 28), fill="#0f172a", outline="#1e293b", radius=36, width=2)
    _round_rect(draw, (48, 48, WIDTH - 48, 240), fill="#101826", outline="#1f2b40", radius=30, width=2)

    t = bundle.get("tournament", {})
    meta = bundle.get("meta", {})
    title = f"TURNIEJ #{official_no}" if official_no else ("TURNIEJ TESTOWY" if int(t.get("is_test") or 0) else "TURNIEJ")
    date_txt = _date_text(t.get("completed_at") or t.get("created_at"))
    sub_1 = f"{date_txt}  •  {meta.get('player_count', '?')} graczy"
    sub_2 = format_labels.get(str(meta.get("format_key") or ""), str(meta.get("format_key") or ""))

    draw.text((80, 82), title, font=_font(54, True), fill=TEXT)
    draw.text((80, 152), sub_1, font=_font(26, False), fill=MUTED)
    _draw_wrapped(draw, sub_2, (80, 186, WIDTH - 100, 228), _font(28, True), fill="#dbeafe", max_lines=2)

    if int(t.get("is_test") or 0):
        _round_rect(draw, (815, 82, 980, 132), fill="#3f2f0d", outline="#7c5a10", radius=22, width=2)
        draw.text((842, 94), "TRYB TESTOWY", font=_font(22, True), fill=GOLD)

    # champion hero card
    _round_rect(draw, (60, 272, WIDTH - 60, 510), fill=CARD, outline="#20304a", radius=32, width=2)
    draw.text((96, 302), "MISTRZ", font=_font(30, True), fill=GOLD)
    champion = str(summary.get("champion") or "—")
    champ_font = _fit_text(draw, champion, 650, 78, 42, bold=True)
    draw.text((96, 352), champion, font=champ_font, fill=TEXT)

    runner = str(summary.get("runner_up") or "—")
    draw.text((96, 442), f"Finalista: {runner}", font=_fit_text(draw, f"Finalista: {runner}", 700, 30, 22, bold=False), fill=SILVER)

    f_home, f_away, f_score = _final_score(bundle)
    # right score box
    _round_rect(draw, (730, 324, 970, 466), fill=CARD_ALT, outline="#27466a", radius=28, width=2)
    draw.text((760, 346), "FINAŁ", font=_font(24, True), fill=ACCENT_2)
    score_font = _fit_text(draw, f_score, 180, 42, 26, bold=True)
    draw.text((760, 386), f_score, font=score_font, fill=TEXT)
    draw.text((760, 430), f"{f_home} vs {f_away}", font=_fit_text(draw, f"{f_home} vs {f_away}", 185, 18, 14, bold=False), fill=MUTED)

    # stats cards
    boxes = [
        (60, 548, 500, 712),
        (540, 548, 1020, 712),
        (60, 744, 500, 960),
        (540, 744, 1020, 960),
    ]
    for box in boxes:
        _round_rect(draw, box, fill=CARD, outline="#20304a", radius=28, width=2)

    # top scorer
    top_scorer = summary.get("real_top_scorer") or {}
    draw.text((86, 574), "STRZELEC TURNIEJU", font=_font(24, True), fill=ACCENT)
    scorer_line = str(top_scorer.get("name") or summary.get("top_goals", {}).get("name") or "—")
    scorer_goals = top_scorer.get("goals") if top_scorer.get("goals") is not None else summary.get("top_goals", {}).get("value", 0)
    draw.text((86, 618), scorer_line, font=_fit_text(draw, scorer_line, 380, 36, 24, bold=True), fill=TEXT)
    draw.text((86, 666), f"{int(scorer_goals or 0)} goli", font=_font(26, False), fill=MUTED)

    # match of tournament
    mot = summary.get("match_of_tournament") or {}
    draw.text((566, 574), "MECZ TURNIEJU", font=_font(24, True), fill=ACCENT_2)
    mot_title = "—"
    mot_detail = ""
    if mot:
        mot_score = str(mot.get("score") or "—")
        if mot.get("home_penalties") is not None and mot.get("away_penalties") is not None:
            mot_score += f" (k. {mot['home_penalties']}:{mot['away_penalties']})"
        mot_title = f"{mot.get('home', '—')} {mot_score} {mot.get('away', '—')}"
        stage = str(mot.get("stage") or "")
        stage_map = {
            "GROUP": "Grupa",
            "LEAGUE": "Liga",
            "QF": "Ćwierćfinał",
            "BARRAGE": "Baraż",
            "SF": "Półfinał",
            "FINAL": "Finał",
            "WB": "Winners",
            "LB": "Losers",
            "WB_FINAL": "Finał Winners",
            "LB_FINAL": "Finał Losers",
            "RESET_FINAL": "Reset Final",
        }
        mot_detail = stage_map.get(stage, stage or "")
        if mot.get("group_name"):
            mot_detail += f" • grupa {mot['group_name']}"
    _draw_wrapped(draw, mot_title, (566, 618, 986, 678), _font(28, True), fill=TEXT, max_lines=2)
    draw.text((566, 676), mot_detail or "—", font=_font(22, False), fill=MUTED)

    # offense / defense
    best_off = summary.get("top_goals") or {}
    draw.text((86, 770), "OFENSYWA", font=_font(24, True), fill="#fb7185")
    off_name = str(best_off.get("name") or "—")
    draw.text((86, 816), off_name, font=_fit_text(draw, off_name, 380, 36, 24, bold=True), fill=TEXT)
    draw.text((86, 864), f"{int(best_off.get('value') or 0)} bramek w turnieju", font=_font(24, False), fill=MUTED)
    if summary.get("biggest"):
        bg = summary["biggest"]
        _draw_wrapped(draw, f"Największe zwycięstwo: {bg['home']} {bg['score']} {bg['away']}", (86, 898, 470, 944), _font(18, False), fill="#cbd5e1", max_lines=2)

    best_def = summary.get("best_defense") or {}
    draw.text((566, 770), "DEFENSYWA", font=_font(24, True), fill="#a78bfa")
    def_name = str(best_def.get("name") or "—")
    draw.text((566, 816), def_name, font=_fit_text(draw, def_name, 400, 36, 24, bold=True), fill=TEXT)
    draw.text((566, 864), f"{int(best_def.get('value') or 0)} straconych goli", font=_font(24, False), fill=MUTED)
    if summary.get("rivalry_match"):
        rv = summary["rivalry_match"]
        _draw_wrapped(draw, f"Rivalry match: {rv['home']} {rv['score']} {rv['away']}", (566, 898, 988, 944), _font(18, False), fill="#cbd5e1", max_lines=2)

    # footer
    draw.text((80, 993), "Wygenerowano z podsumowania turnieju", font=_font(20, False), fill="#64748b")

    bio = BytesIO()
    img.save(bio, format="PNG", optimize=True)
    return bio.getvalue()

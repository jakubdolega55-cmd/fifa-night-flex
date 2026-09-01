from __future__ import annotations

import os
import subprocess
from datetime import datetime
from io import BytesIO
from PIL import Image, ImageDraw, ImageFont

WIDTH = 1080
HEIGHT = 1080
BG = "#0a1020"
PANEL = "#111a2b"
PANEL2 = "#162238"
BORDER = "#2b3a55"
TEXT = "#f8fafc"
MUTED = "#a8b3c7"
GOLD = "#facc15"
CYAN = "#38bdf8"
GREEN = "#22c55e"
PINK = "#fb7185"
PURPLE = "#a78bfa"
_FONT_CACHE = {}
_BASE_DIR = os.path.dirname(__file__)


def _font(size: int, bold: bool = False):
    key = (size, bold)
    if key in _FONT_CACHE:
        return _FONT_CACHE[key]
    name = "DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf"
    paths = [
        name,
        f"/usr/share/fonts/truetype/dejavu/{name}",
        f"/usr/share/fonts/dejavu/{name}",
        "/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf",
        "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf" if bold else "/usr/share/fonts/truetype/freefont/FreeSans.ttf",
    ]
    # On Streamlit Cloud the exact font path varies. fontconfig can resolve a
    # Unicode-capable system font without bundling any font files with the app.
    for family in (["DejaVu Sans", "Liberation Sans", "FreeSans"]):
        try:
            style = ":style=Bold" if bold else ":style=Regular"
            found = subprocess.check_output(["fc-match", "-f", "%{file}", family + style], text=True, timeout=1).strip()
            if found: paths.insert(0, found)
        except Exception:
            pass
    for path in paths:
        try:
            f = ImageFont.truetype(path, size)
            _FONT_CACHE[key] = f
            return f
        except Exception:
            pass
    # Matplotlib also ships a Unicode-capable DejaVu Sans fallback.
    # a DejaVu Sans font with full Polish glyph support, so use it as a free fallback.
    try:
        from matplotlib import font_manager
        mpl_path = font_manager.findfont("DejaVu Sans", fallback_to_default=True)
        f = ImageFont.truetype(mpl_path, size)
        _FONT_CACHE[key] = f
        return f
    except Exception:
        pass
    try:
        f = ImageFont.load_default(size=size)
    except TypeError:
        f = ImageFont.load_default()
    _FONT_CACHE[key] = f
    return f


def _fit(draw, text, maxw, start, minsize=22, bold=False):
    text = str(text or "—")
    for size in range(start, minsize - 1, -2):
        f = _font(size, bold)
        if draw.textbbox((0, 0), text, font=f)[2] <= maxw:
            return f
    return _font(minsize, bold)


def _rr(draw, box, fill=PANEL, outline=BORDER, r=28, w=2):
    draw.rounded_rectangle(box, radius=r, fill=fill, outline=outline, width=w)


def _date(value):
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")).strftime("%d.%m.%Y")
    except Exception:
        return str(value or "")[:10] or "—"


def _team_for(bundle, name):
    for p in bundle.get("players", []):
        if str(p.get("name")) == str(name):
            return str(p.get("team") or "—")
    return "—"


def _final(bundle):
    finals = [m for m in bundle.get("matches", []) if m.get("home_score") is not None and m.get("stage") in ("FINAL", "RESET_FINAL")]
    if not finals:
        return None
    return finals[-1]


def _champion_record(bundle, champ):
    rec = {"w": 0, "d": 0, "l": 0, "gf": 0, "ga": 0}
    for m in bundle.get("matches", []):
        if m.get("home_score") is None:
            continue
        h, a = m.get("home_name"), m.get("away_name")
        hs, aw = int(m.get("home_score") or 0), int(m.get("away_score") or 0)
        if champ not in (h, a):
            continue
        if champ == h:
            gf, ga = hs, aw
            win = m.get("winner_player_id") == m.get("home_player_id")
        else:
            gf, ga = aw, hs
            win = m.get("winner_player_id") == m.get("away_player_id")
        rec["gf"] += gf
        rec["ga"] += ga
        if hs == aw and m.get("winner_player_id") is None:
            rec["d"] += 1
        elif win:
            rec["w"] += 1
        else:
            rec["l"] += 1
    return rec


def _mot_text(mot):
    if not mot:
        return "—", "—"
    score = str(mot.get("score") or "—")
    if mot.get("home_penalties") is not None and mot.get("away_penalties") is not None:
        score += f" (k. {mot['home_penalties']}:{mot['away_penalties']})"
    title = f"{mot.get('home', '—')} {score} {mot.get('away', '—')}"
    labels = {
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
    }
    detail = labels.get(str(mot.get("stage") or ""), str(mot.get("stage") or "—"))
    if mot.get("group_name"):
        detail += f" • grupa {mot['group_name']}"
    return title, detail


def _wrap(draw, text, x, y, maxw, font, fill=TEXT, max_lines=2, gap=6):
    words = str(text or "—").split()
    lines, cur = [], ""
    for word in words:
        trial = (cur + " " + word).strip()
        if draw.textbbox((0, 0), trial, font=font)[2] <= maxw:
            cur = trial
        else:
            if cur:
                lines.append(cur)
            cur = word
            if len(lines) >= max_lines - 1:
                break
    if cur and len(lines) < max_lines:
        lines.append(cur)
    for line in lines:
        draw.text((x, y), line, font=font, fill=fill)
        y += font.size + gap
    return y


def _classification_line(draw, x, y, place_no, name, team, maxw):
    line=f"{place_no}. {name or '—'}  •  {team or '—'}"
    draw.text((x,y),line,font=_fit(draw,line,maxw,23,15,True),fill=TEXT)
    return y+43


def generate_summary_png(bundle: dict, summary: dict, format_labels: dict[str, str], official_no: int | None = None) -> bytes:
    img = Image.new("RGB", (WIDTH, HEIGHT), BG)
    draw = ImageDraw.Draw(img)
    _rr(draw, (24, 24, 1056, 1056), fill="#0e1728", outline="#25334b", r=38)

    t = bundle.get("tournament", {})
    meta = bundle.get("meta", {})
    title = f"TURNIEJ #{official_no}" if official_no else "TURNIEJ TESTOWY"
    draw.text((72, 66), title, font=_font(58, True), fill=TEXT)
    date_line = f"{_date(t.get('completed_at') or t.get('created_at'))}  •  {meta.get('player_count', '?')} graczy"
    draw.text((74, 137), date_line, font=_font(28), fill=MUTED)
    fmt = format_labels.get(str(meta.get("format_key") or ""), str(meta.get("format_key") or "—"))
    draw.text((74, 180), fmt, font=_fit(draw, fmt, 900, 30, 22, True), fill="#dbeafe")

    champ = str(summary.get("champion") or "—")
    runner = str(summary.get("runner_up") or "—")
    champ_team = _team_for(bundle, champ)
    runner_team = _team_for(bundle, runner)
    final = _final(bundle)
    final_score = "—"
    if final:
        final_score = f"{final.get('home_score')}:{final.get('away_score')}"
        if final.get("home_penalties") is not None:
            final_score += f"  k. {final.get('home_penalties')}:{final.get('away_penalties')}"

    rec = _champion_record(bundle, champ)

    # Main result
    _rr(draw, (58, 250, 1022, 500), fill=PANEL, outline="#334563", r=32)
    draw.text((92, 280), "MISTRZ", font=_font(29, True), fill=GOLD)
    draw.text((92, 325), champ, font=_fit(draw, champ, 560, 70, 38, True), fill=TEXT)
    draw.text((94, 402), champ_team, font=_fit(draw, champ_team, 520, 30, 22), fill=MUTED)
    record = f"Bilans {rec['w']}W • {rec['d']}R • {rec['l']}P   |   Bramki {rec['gf']}:{rec['ga']}"
    draw.text((94, 440), record, font=_fit(draw, record, 540, 24, 18), fill="#d1d9e8")

    _rr(draw, (728, 298, 970, 455), fill=PANEL2, outline="#2d5b82", r=28)
    draw.text((758, 320), "FINAŁ", font=_font(25, True), fill=CYAN)
    draw.text((758, 359), final_score, font=_fit(draw, final_score, 180, 46, 28, True), fill=TEXT)
    if final:
        pair = f"{final.get('home_name', '—')} vs {final.get('away_name', '—')}"
        draw.text((758, 414), pair, font=_fit(draw, pair, 185, 18, 14), fill=MUTED)

    # Row 1
    _rr(draw, (58, 530, 515, 715))
    _rr(draw, (545, 530, 1022, 715))
    scorer = summary.get("real_top_scorer") or {}
    draw.text((86, 558), "STRZELEC TURNIEJU", font=_font(25, True), fill=GREEN)
    if scorer:
        scorer_name = str(scorer.get("name") or "—")
        goals = int(scorer.get("goals") or 0)
        draw.text((86, 608), scorer_name, font=_fit(draw, scorer_name, 390, 39, 25, True), fill=TEXT)
        draw.text((86, 661), f"{goals} goli", font=_font(27), fill=MUTED)
    else:
        msg="Nie uzupełniono strzelców"
        draw.text((86, 610), msg, font=_fit(draw, msg, 390, 29, 21, True), fill=TEXT)
        draw.text((86, 657), "Pole opcjonalne", font=_font(21), fill=MUTED)

    mot_title, mot_detail = _mot_text(summary.get("match_of_tournament"))
    draw.text((573, 558), "MECZ TURNIEJU", font=_font(25, True), fill=CYAN)
    _wrap(draw, mot_title, 573, 608, 410, _font(29, True), max_lines=2)
    draw.text((573, 672), mot_detail, font=_font(22), fill=MUTED)

    # Row 2: compact final classification + tournament numbers
    _rr(draw, (58, 745, 515, 938))
    _rr(draw, (545, 745, 1022, 938))

    draw.text((86, 774), "KLASYFIKACJA", font=_font(25, True), fill=PINK)
    y=814
    y=_classification_line(draw,86,y,2,runner,runner_team,390)
    third=summary.get("third_place") or {}
    fourth=summary.get("fourth_place") or {}
    if third:y=_classification_line(draw,86,y,3,third.get("name"),third.get("team"),390)
    if fourth:y=_classification_line(draw,86,y,4,fourth.get("name"),fourth.get("team"),390)

    played = [m for m in bundle.get("matches", []) if m.get("home_score") is not None]
    total_goals = sum(int(m.get("home_score") or 0) + int(m.get("away_score") or 0) for m in played)
    avg = (total_goals / len(played)) if played else 0
    draw.text((573, 774), "TURNIEJ W LICZBACH", font=_font(25, True), fill=PURPLE)
    draw.text((573, 818), f"{len(played)} meczów  •  {total_goals} goli", font=_font(31, True), fill=TEXT)
    draw.text((573, 860), f"Średnio {avg:.1f} gola / mecz", font=_font(25), fill=MUTED)

    # Footer facts
    facts = []
    if summary.get("biggest"):
        x = summary["biggest"]
        facts.append(f"Największe zwycięstwo: {x['home']} {x['score']} {x['away']}")
    if summary.get("highest"):
        x = summary["highest"]
        facts.append(f"Najwięcej goli w meczu: {x['home']} {x['score']} {x['away']}")
    if summary.get("rivalry_match"):
        x = summary["rivalry_match"]
        facts.append(f"Rivalry match: {x['home']} {x['score']} {x['away']}")
    y = 965
    for fact in facts[:3]:
        draw.text((74, y), fact, font=_fit(draw, fact, 930, 21, 17), fill="#cbd5e1")
        y += 29

    bio = BytesIO()
    img.save(bio, "PNG", optimize=True)
    return bio.getvalue()

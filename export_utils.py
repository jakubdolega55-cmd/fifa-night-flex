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


def _money(cents: int) -> str:
    return f"{int(cents or 0) / 100:.2f}".replace(".", ",") + " zł"


def generate_settlement_png(settlement: dict, event_labels: list[str] | None = None) -> bytes:
    """Square share card for a multi-event cash settlement."""
    img = Image.new("RGB", (WIDTH, HEIGHT), BG)
    draw = ImageDraw.Draw(img)
    _rr(draw, (24, 24, 1056, 1056), fill="#0e1728", outline="#25334b", r=38)
    draw.text((68, 62), "FIFA NIGHT — ROZLICZENIE", font=_font(50, True), fill=TEXT)
    draw.text((70, 126), datetime.now().strftime("%d.%m.%Y"), font=_font(24), fill=MUTED)

    total = int(settlement.get("total_pot_cents") or 0)
    pending = int(settlement.get("pending_jackpot_cents") or 0)
    current = int(settlement.get("current_jackpot_cents") or 0)
    _rr(draw, (58, 182, 1022, 300), fill=PANEL, outline="#334563", r=28)
    draw.text((88, 205), "WPISOWE W WYBRANYCH GRACH", font=_font(21, True), fill=CYAN)
    draw.text((88, 242), _money(total), font=_font(37, True), fill=TEXT)
    if pending:
        jp = f"Jackpot bez laureata: {_money(pending)}"
        draw.text((528, 220), jp, font=_fit(draw, jp, 440, 27, 18, True), fill=GOLD)
    elif current:
        jp = f"Aktualny jackpot: {_money(current)}"
        draw.text((528, 220), jp, font=_fit(draw, jp, 440, 27, 18, True), fill=GOLD)

    transfers = settlement.get("transfers") or []
    _rr(draw, (58, 328, 1022, 700), fill=PANEL, outline=BORDER, r=28)
    draw.text((88, 354), "KTO KOMU PRZELEWA", font=_font(26, True), fill=GREEN)
    y = 404
    if transfers:
        for tr in transfers[:6]:
            line = f"{tr.get('from_name', '—')} → {tr.get('to_name', '—')}   {_money(tr.get('amount_cents', 0))}"
            draw.text((92, y), line, font=_fit(draw, line, 870, 31, 20, True), fill=TEXT)
            y += 48
        if len(transfers) > 6:
            draw.text((92, y), f"+ {len(transfers)-6} kolejnych przelewów", font=_font(22), fill=MUTED)
    else:
        draw.text((92, 418), "Nikt nikomu nic nie jest winien.", font=_font(31, True), fill=TEXT)

    balances = settlement.get("balances") or []
    _rr(draw, (58, 728, 1022, 966), fill=PANEL, outline=BORDER, r=28)
    draw.text((88, 752), "BILANS", font=_font(25, True), fill=PURPLE)
    y = 798
    # Arrange up to eight balances in two columns.
    for i, row in enumerate(balances[:8]):
        col = i % 2; rr_idx = i // 2
        x = 92 + col * 455; yy = y + rr_idx * 39
        amount = int(row.get("balance_cents") or 0); sign = "+" if amount > 0 else ""
        text = f"{row.get('name', '—')}: {sign}{_money(amount)}"
        draw.text((x, yy), text, font=_fit(draw, text, 410, 23, 17, True), fill=TEXT)

    labels = event_labels or []
    if labels:
        footer = f"{len(labels)} rozgrywek • kompensacja wzajemnych należności"
    else:
        footer = "Kompensacja wzajemnych należności"
    draw.text((70, 1002), footer, font=_fit(draw, footer, 930, 20, 16), fill=MUTED)
    bio = BytesIO(); img.save(bio, "PNG", optimize=True); return bio.getvalue()


def generate_awards_png(year: int, winners: list[dict] | dict) -> bytes:
    """Final Awards card: category + selected winner only, without ranking reasons."""
    if isinstance(winners, dict):
        rows = [{"title": k, "name": (v or {}).get("name", "—")} for k, v in winners.items()]
    else:
        rows = list(winners or [])
    img = Image.new("RGB", (WIDTH, HEIGHT), BG); draw = ImageDraw.Draw(img)
    _rr(draw, (24, 24, 1056, 1056), fill="#0e1728", outline="#25334b", r=38)
    draw.text((66, 58), "FIFA NIGHT AWARDS", font=_font(55, True), fill=GOLD)
    draw.text((70, 126), str(int(year)), font=_font(33, True), fill=TEXT)
    if not rows:
        draw.text((70, 220), "Laureaci nie zostali jeszcze wybrani.", font=_font(29, True), fill=MUTED)
    else:
        # Fit up to 19 categories on a single 1080 card.
        top = 184; bottom = 1005; available = bottom - top
        h = max(38, min(58, available // max(1, len(rows))))
        title_size = max(14, min(20, h // 2)); name_size = max(17, min(25, h // 2 + 3))
        y = top
        for row in rows[:19]:
            title = str(row.get("title") or row.get("category") or "Nagroda")
            name = str(row.get("name") or "—")
            draw.text((74, y), title, font=_fit(draw, title, 510, title_size, 12, True), fill=MUTED)
            draw.text((590, y-2), name, font=_fit(draw, name, 405, name_size, 14, True), fill=TEXT)
            y += h
    bio = BytesIO(); img.save(bio, "PNG", optimize=True); return bio.getvalue()


def generate_year_summary_png(year: int, overview: dict, highlights: list[dict] | None = None) -> bytes:
    """Annual 'Rok w liczbach' share card."""
    img = Image.new("RGB", (WIDTH, HEIGHT), BG); draw = ImageDraw.Draw(img)
    _rr(draw, (24, 24, 1056, 1056), fill="#0e1728", outline="#25334b", r=38)
    draw.text((66, 58), f"FIFA NIGHT {int(year)}", font=_font(57, True), fill=TEXT)
    draw.text((70, 130), "ROK W LICZBACH", font=_font(29, True), fill=CYAN)

    metrics = [
        ("TURNIEJE", overview.get("tournaments", 0)),
        ("1 VS 1", overview.get("duels", 0)),
        ("MECZE", overview.get("matches", 0)),
        ("GOLE", overview.get("goals", 0)),
        ("GRACZE", overview.get("players", 0)),
        ("TYTUŁY", overview.get("titles", overview.get("tournaments", 0))),
    ]
    x0, y0, w, h = 60, 205, 300, 145
    for i, (label, value) in enumerate(metrics):
        row, col = divmod(i, 3); x = x0 + col * 330; y = y0 + row * 168
        _rr(draw, (x, y, x+w, y+h), fill=PANEL, outline=BORDER, r=25)
        draw.text((x+25, y+25), label, font=_font(21, True), fill=MUTED)
        draw.text((x+25, y+63), str(value), font=_font(49, True), fill=TEXT)

    _rr(draw, (60, 565, 1020, 926), fill=PANEL, outline=BORDER, r=28)
    draw.text((90, 594), "NAJWAŻNIEJSZE", font=_font(26, True), fill=GOLD)
    items = list(highlights or [])
    if not items:
        if overview.get("top_player"): items.append({"label":"Lider roku","value":overview.get("top_player")})
        if overview.get("top_team"): items.append({"label":"Drużyna roku — ranking live","value":overview.get("top_team")})
    y = 650
    for row in items[:5]:
        label = str(row.get("label") or row.get("title") or "—")
        value = str(row.get("value") or row.get("name") or "—")
        draw.text((92, y), label, font=_fit(draw, label, 360, 21, 15, True), fill=MUTED)
        draw.text((440, y-2), value, font=_fit(draw, value, 520, 30, 18, True), fill=TEXT)
        y += 54
    draw.text((70, 1002), "Oficjalne rozgrywki • testy nie są uwzględniane", font=_font(19), fill=MUTED)
    bio = BytesIO(); img.save(bio, "PNG", optimize=True); return bio.getvalue()

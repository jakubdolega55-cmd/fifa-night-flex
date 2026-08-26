from __future__ import annotations

from itertools import combinations
import random
from typing import Iterable

BASE_TEAMS = [
    "Bayern Monachium",
    "FC Barcelona",
    "PSG",
    "Liverpool",
    "Manchester City",
    "Dowolna drużyna (Real Madryt banned)",
]

SEVEN_TEAMS = [
    "Bayern Monachium",
    "FC Barcelona",
    "PSG",
    "Liverpool",
    "Manchester City",
    "Dowolna drużyna #1 (Real Madryt banned)",
    "Dowolna drużyna #2 (Real Madryt banned)",
]

FORMAT_LABELS = {
    "league4_final": "Liga każdy z każdym + finał",
    "double5": "Double elimination",
    "groups6": "2 grupy po 3 + półfinały + finał",
    "double7": "Double elimination",
    "groups7": "Grupy 4+3 + ćwierćfinały + półfinały + finał",
}


def allowed_teams(player_count: int) -> list[str]:
    if player_count == 7:
        return SEVEN_TEAMS.copy()
    return BASE_TEAMS.copy()


def shuffled_assignments(player_ids: list[str], teams: list[str], rng: random.Random) -> dict[str, str]:
    if len(player_ids) != len(teams):
        raise ValueError("Liczba drużyn musi odpowiadać liczbie graczy.")
    pool = teams.copy()
    rng.shuffle(pool)
    return dict(zip(player_ids, pool, strict=True))


def build_draw(player_ids: list[str], format_key: str, rng: random.Random) -> dict:
    ids = player_ids.copy()
    rng.shuffle(ids)
    if format_key == "league4_final":
        return {"slots": dict(zip(["A", "B", "C", "D"], ids, strict=True))}
    if format_key == "double5":
        return {"slots": dict(zip(["A", "B", "C", "D", "E"], ids, strict=True))}
    if format_key == "groups6":
        seq = ["A1", "B1", "A2", "B2", "A3", "B3"]
        return {"slots": dict(zip(seq, ids, strict=True))}
    if format_key == "double7":
        return {"slots": dict(zip(["A", "B", "C", "D", "E", "F", "G"], ids, strict=True))}
    if format_key == "groups7":
        seq = ["A1", "B1", "A2", "B2", "A3", "B3", "A4"]
        return {"slots": dict(zip(seq, ids, strict=True))}
    raise ValueError(f"Nieznany format: {format_key}")


def draw_signature(draw: dict) -> tuple:
    slots = draw.get("slots", {})
    return tuple((k, slots[k]) for k in sorted(slots))


def group_members(draw: dict, group_name: str) -> list[str]:
    slots = draw["slots"]
    keys = sorted([k for k in slots if k.startswith(group_name)], key=lambda x: int(x[1:]))
    return [slots[k] for k in keys]


def _round_robin_pairs(ids: list[str]) -> list[list[tuple[str, str]]]:
    """Circle-method rounds. For even n each round contains disjoint pairs."""
    work = ids.copy()
    if len(work) % 2:
        work.append("__BYE__")
    n = len(work)
    rounds: list[list[tuple[str, str]]] = []
    for _ in range(n - 1):
        pairs: list[tuple[str, str]] = []
        for i in range(n // 2):
            a, b = work[i], work[n - 1 - i]
            if "__BYE__" not in (a, b):
                pairs.append((a, b))
        rounds.append(pairs)
        work = [work[0]] + [work[-1]] + work[1:-1]
    return rounds


def schedule_league4(draw: dict, rng: random.Random) -> list[dict]:
    s = draw["slots"]
    # Purposefully arranged as disjoint pairs in each mini-round.
    pairs = [
        (s["A"], s["B"]),
        (s["C"], s["D"]),
        (s["A"], s["C"]),
        (s["B"], s["D"]),
        (s["A"], s["D"]),
        (s["B"], s["C"]),
    ]
    out = []
    for no, (h, a) in enumerate(pairs, 1):
        if rng.choice([True, False]):
            h, a = a, h
        out.append({"match_no": no, "stage": "LEAGUE", "group_name": "L", "home": f"P:{h}", "away": f"P:{a}"})
    out.append({"match_no": 7, "stage": "FINAL", "group_name": None, "home": "POS:L:1", "away": "POS:L:2"})
    return out


def schedule_groups6(draw: dict, rng: random.Random) -> list[dict]:
    a = group_members(draw, "A")
    b = group_members(draw, "B")
    pairs = {"A": list(combinations(a, 2)), "B": list(combinations(b, 2))}
    rng.shuffle(pairs["A"]); rng.shuffle(pairs["B"])
    out: list[dict] = []
    idx = {"A": 0, "B": 0}
    for no, group in enumerate(["A", "B"] * 3, 1):
        h, aw = pairs[group][idx[group]]; idx[group] += 1
        if rng.choice([True, False]): h, aw = aw, h
        out.append({"match_no": no, "stage": "GROUP", "group_name": group, "home": f"P:{h}", "away": f"P:{aw}"})
    out += [
        {"match_no": 7, "stage": "SF", "group_name": None, "home": "POS:A:1", "away": "POS:B:2"},
        {"match_no": 8, "stage": "SF", "group_name": None, "home": "POS:B:1", "away": "POS:A:2"},
        {"match_no": 9, "stage": "FINAL", "group_name": None, "home": "W:7", "away": "W:8"},
    ]
    return out


def schedule_groups7(draw: dict, rng: random.Random) -> list[dict]:
    a = group_members(draw, "A")
    b = group_members(draw, "B")
    # A has 4 players. Keep the two matches from each round together: they are disjoint.
    ar = _round_robin_pairs(a)
    # B has 3 players; one match per round.
    br = _round_robin_pairs(b)
    # A,A,B / A,A,B / A,B,A spreads B games while preserving rest for A.
    ordered: list[tuple[str, tuple[str, str]]] = [
        ("A", ar[0][0]), ("A", ar[0][1]), ("B", br[0][0]),
        ("A", ar[1][0]), ("A", ar[1][1]), ("B", br[1][0]),
        ("A", ar[2][0]), ("B", br[2][0]), ("A", ar[2][1]),
    ]
    out: list[dict] = []
    for no, (group, pair) in enumerate(ordered, 1):
        h, aw = pair
        if rng.choice([True, False]): h, aw = aw, h
        out.append({"match_no": no, "stage": "GROUP", "group_name": group, "home": f"P:{h}", "away": f"P:{aw}"})
    out += [
        {"match_no": 10, "stage": "QF", "group_name": None, "home": "POS:A:2", "away": "POS:B:3"},
        {"match_no": 11, "stage": "QF", "group_name": None, "home": "POS:B:2", "away": "POS:A:3"},
        # QF1 winner gets one match of rest before SF2; QF2 winner gets one match before SF1.
        {"match_no": 12, "stage": "SF", "group_name": None, "home": "POS:B:1", "away": "W:10"},
        {"match_no": 13, "stage": "SF", "group_name": None, "home": "POS:A:1", "away": "W:11"},
        {"match_no": 14, "stage": "FINAL", "group_name": None, "home": "W:12", "away": "W:13"},
    ]
    return out


def schedule_double5(draw: dict, extra: dict) -> list[dict]:
    s = draw["slots"]
    bye_winner_match = int(extra["bye_winner_match"])  # 1 or 2; never E, so E cannot get two byes.
    other = 2 if bye_winner_match == 1 else 1
    return [
        {"match_no": 1, "stage": "WB", "group_name": None, "home": f"P:{s['A']}", "away": f"P:{s['B']}"},
        {"match_no": 2, "stage": "WB", "group_name": None, "home": f"P:{s['C']}", "away": f"P:{s['D']}"},
        # E plays as soon as both preliminary winners are known; this keeps the initial bye from becoming a long wait.
        {"match_no": 3, "stage": "WB", "group_name": None, "home": f"P:{s['E']}", "away": f"W:{other}"},
        {"match_no": 4, "stage": "LB", "group_name": None, "home": "L:1", "away": "L:2"},
        {"match_no": 5, "stage": "WB_FINAL", "group_name": None, "home": f"W:{bye_winner_match}", "away": "W:3"},
        {"match_no": 6, "stage": "LB", "group_name": None, "home": "W:4", "away": "L:3"},
        {"match_no": 7, "stage": "LB_FINAL", "group_name": None, "home": "W:6", "away": "L:5"},
        {"match_no": 8, "stage": "FINAL", "group_name": None, "home": "W:5", "away": "W:7"},
        {"match_no": 9, "stage": "RESET_FINAL", "group_name": None, "home": "W:5", "away": "W:7"},
    ]


def schedule_double7(draw: dict, extra: dict) -> list[dict]:
    s = draw["slots"]
    # The bracket draw is random. Slot G receives the winners-bracket bye.
    # Loser of M3 receives the first losers-bracket bye; because M3 participants are random,
    # the benefit is still random while avoiding a 5–6 match wait for someone who lost M1.
    lb_bye_match = 3
    return [
        {"match_no": 1, "stage": "WB", "group_name": None, "home": f"P:{s['A']}", "away": f"P:{s['B']}"},
        {"match_no": 2, "stage": "WB", "group_name": None, "home": f"P:{s['C']}", "away": f"P:{s['D']}"},
        {"match_no": 3, "stage": "WB", "group_name": None, "home": f"P:{s['E']}", "away": f"P:{s['F']}"},
        # Put the initial-bye player into action immediately after round one.
        {"match_no": 4, "stage": "WB", "group_name": None, "home": "W:3", "away": f"P:{s['G']}"},
        {"match_no": 5, "stage": "LB", "group_name": None, "home": "L:1", "away": "L:2"},
        {"match_no": 6, "stage": "WB", "group_name": None, "home": "W:1", "away": "W:2"},
        {"match_no": 7, "stage": "LB", "group_name": None, "home": f"L:{lb_bye_match}", "away": "L:4"},
        {"match_no": 8, "stage": "LB", "group_name": None, "home": "W:5", "away": "L:6"},
        {"match_no": 9, "stage": "WB_FINAL", "group_name": None, "home": "W:4", "away": "W:6"},
        {"match_no": 10, "stage": "LB", "group_name": None, "home": "W:7", "away": "W:8"},
        {"match_no": 11, "stage": "LB_FINAL", "group_name": None, "home": "W:10", "away": "L:9"},
        {"match_no": 12, "stage": "FINAL", "group_name": None, "home": "W:9", "away": "W:11"},
        {"match_no": 13, "stage": "RESET_FINAL", "group_name": None, "home": "W:9", "away": "W:11"},
    ]


def schedule_for_format(draw: dict, format_key: str, extra: dict, rng: random.Random) -> list[dict]:
    if format_key == "league4_final": return schedule_league4(draw, rng)
    if format_key == "double5": return schedule_double5(draw, extra)
    if format_key == "groups6": return schedule_groups6(draw, rng)
    if format_key == "double7": return schedule_double7(draw, extra)
    if format_key == "groups7": return schedule_groups7(draw, rng)
    raise ValueError(format_key)


def group_table(group_player_ids: Iterable[str], matches: list[dict], tie_orders: dict[str, int]) -> list[dict]:
    ids = list(group_player_ids)
    stats = {pid: {"player_id": pid, "m": 0, "w": 0, "d": 0, "l": 0, "gf": 0, "ga": 0, "gd": 0, "pts": 0} for pid in ids}
    played: list[dict] = []
    for m in matches:
        if m.get("home_score") is None or m.get("away_score") is None: continue
        h, a = m.get("home_player_id"), m.get("away_player_id")
        if h not in stats or a not in stats: continue
        hs, ass = int(m["home_score"]), int(m["away_score"])
        stats[h]["m"] += 1; stats[a]["m"] += 1
        stats[h]["gf"] += hs; stats[h]["ga"] += ass
        stats[a]["gf"] += ass; stats[a]["ga"] += hs
        if hs > ass:
            stats[h]["w"] += 1; stats[a]["l"] += 1; stats[h]["pts"] += 3
        elif hs < ass:
            stats[a]["w"] += 1; stats[h]["l"] += 1; stats[a]["pts"] += 3
        else:
            stats[h]["d"] += 1; stats[a]["d"] += 1; stats[h]["pts"] += 1; stats[a]["pts"] += 1
        played.append(m)
    for row in stats.values(): row["gd"] = row["gf"] - row["ga"]
    rows = list(stats.values())
    rows.sort(key=lambda r: (r["pts"], r["gd"], r["gf"]), reverse=True)
    i = 0
    while i < len(rows):
        key = (rows[i]["pts"], rows[i]["gd"], rows[i]["gf"])
        j = i + 1
        while j < len(rows) and (rows[j]["pts"], rows[j]["gd"], rows[j]["gf"]) == key: j += 1
        block = rows[i:j]
        if len(block) == 2:
            p1, p2 = block[0]["player_id"], block[1]["player_id"]
            h2h = next((m for m in played if {m["home_player_id"], m["away_player_id"]} == {p1, p2}), None)
            if h2h and h2h["home_score"] != h2h["away_score"]:
                win = h2h["home_player_id"] if h2h["home_score"] > h2h["away_score"] else h2h["away_player_id"]
                if block[1]["player_id"] == win: rows[i], rows[i+1] = rows[i+1], rows[i]
            else: rows[i:j] = sorted(block, key=lambda r: tie_orders.get(r["player_id"], 9999))
        elif len(block) > 1:
            rows[i:j] = sorted(block, key=lambda r: tie_orders.get(r["player_id"], 9999))
        i = j
    for pos, row in enumerate(rows, 1): row["position"] = pos
    return rows


def winner_from_result(home_score: int, away_score: int, home_id: str, away_id: str, home_pen: int | None = None, away_pen: int | None = None) -> str | None:
    if home_score > away_score: return home_id
    if away_score > home_score: return away_id
    if home_pen is None or away_pen is None or home_pen == away_pen: return None
    return home_id if home_pen > away_pen else away_id

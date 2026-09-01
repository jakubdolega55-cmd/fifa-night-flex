from __future__ import annotations

from itertools import combinations
import random
from typing import Iterable

WILDCARD_TEAM_SUGGESTIONS = [
    "Inter",
    "Atletico",
    "BVB",
    "Man United",
    "Arsenal",
    "Chelsea",
    "Bayer Leverkusen",
    "Tottenham",
    "AC Milan",
    "Napoli",
]

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

EIGHT_TEAMS = [
    "Bayern Monachium",
    "FC Barcelona",
    "PSG",
    "Liverpool",
    "Manchester City",
    "Dowolna drużyna #1 (Real Madryt banned)",
    "Dowolna drużyna #2 (Real Madryt banned)",
    "Dowolna drużyna #3 (Real Madryt banned)",
]

FORMAT_LABELS = {
    "league4_final": "Liga każdy z każdym + finał",
    "double5": "Double elimination",
    "league5_final": "Liga każdy z każdym + finał",
    "groups6": "Klasyczny: 2 grupy po 3 + półfinały + finał",
    "groups6_full": "Rozszerzony: 2 grupy po 3 + ćwierćfinały + półfinały + finał",
    "double7": "Double elimination",
    "groups7": "Grupy 4+3 + ćwierćfinały + półfinały + finał",
    "groups7_sf": "Grupy 4+3 + półfinały + finał",
    "groups8_sf": "Grupy 4+4 + półfinały + finał",
    "double8": "Double elimination",
    "groups8_barrage": "Grupy 4+4 + baraże + półfinały + finał",
}

FORMAT_MATCH_COUNTS = {
    "league4_final": "7 meczów",
    "double5": "8 meczów",
    "league5_final": "11 meczów",
    "groups6": "9 meczów",
    "groups6_full": "11 meczów",
    "double7": "12 meczów",
    "groups7": "14 meczów",
    "groups7_sf": "12 meczów",
    "groups8_sf": "15 meczów",
    "double8": "14 meczów",
    "groups8_barrage": "17 meczów",
}


def allowed_teams(player_count: int) -> list[str]:
    if player_count == 8: return EIGHT_TEAMS.copy()
    if player_count == 7: return SEVEN_TEAMS.copy()
    return BASE_TEAMS.copy()


def shuffled_assignments(player_ids: list[str], teams: list[str], rng: random.Random) -> dict[str, str]:
    if len(player_ids) != len(teams):
        raise ValueError("Liczba drużyn musi odpowiadać liczbie graczy.")
    pool = teams.copy(); rng.shuffle(pool)
    return dict(zip(player_ids, pool, strict=True))


def build_draw(player_ids: list[str], format_key: str, rng: random.Random) -> dict:
    ids = player_ids.copy(); rng.shuffle(ids)
    if format_key == "league4_final":
        return {"slots": dict(zip(["A", "B", "C", "D"], ids, strict=True))}
    if format_key in ("double5", "league5_final"):
        return {"slots": dict(zip(["A", "B", "C", "D", "E"], ids, strict=True))}
    if format_key in ("groups6", "groups6_full"):
        seq = ["A1", "B1", "A2", "B2", "A3", "B3"]
        return {"slots": dict(zip(seq, ids, strict=True))}
    if format_key == "double7":
        return {"slots": dict(zip(["A", "B", "C", "D", "E", "F", "G"], ids, strict=True))}
    if format_key in ("groups7", "groups7_sf"):
        seq = ["A1", "B1", "A2", "B2", "A3", "B3", "A4"]
        return {"slots": dict(zip(seq, ids, strict=True))}
    if format_key == "double8":
        return {"slots": dict(zip(["A", "B", "C", "D", "E", "F", "G", "H"], ids, strict=True))}
    if format_key in ("groups8_sf", "groups8_barrage"):
        seq = ["A1", "B1", "A2", "B2", "A3", "B3", "A4", "B4"]
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
    if len(work) % 2: work.append("__BYE__")
    n = len(work); rounds: list[list[tuple[str, str]]] = []
    for _ in range(n - 1):
        pairs: list[tuple[str, str]] = []
        for i in range(n // 2):
            a, b = work[i], work[n - 1 - i]
            if "__BYE__" not in (a, b): pairs.append((a, b))
        rounds.append(pairs)
        work = [work[0]] + [work[-1]] + work[1:-1]
    return rounds


def schedule_league4(draw: dict, rng: random.Random) -> list[dict]:
    s = draw["slots"]
    # Disjoint pairs alternate; nobody plays back-to-back during the league phase.
    pairs = [(s["A"],s["B"]),(s["C"],s["D"]),(s["A"],s["C"]),(s["B"],s["D"]),(s["A"],s["D"]),(s["B"],s["C"])]
    out=[]
    for no,(h,a) in enumerate(pairs,1):
        if rng.choice([True,False]): h,a=a,h
        out.append({"match_no":no,"stage":"LEAGUE","group_name":"L","home":f"P:{h}","away":f"P:{a}"})
    out.append({"match_no":7,"stage":"FINAL","group_name":None,"home":"POS:L:1","away":"POS:L:2"})
    return out


def schedule_league5(draw: dict, rng: random.Random) -> list[dict]:
    """K5 edge ordering where adjacent matches are disjoint."""
    s=draw["slots"]
    pairs=[(s["A"],s["B"]),(s["C"],s["D"]),(s["A"],s["E"]),(s["B"],s["C"]),(s["D"],s["E"]),(s["A"],s["C"]),(s["B"],s["D"]),(s["C"],s["E"]),(s["A"],s["D"]),(s["B"],s["E"])]
    out=[]
    for no,(h,a) in enumerate(pairs,1):
        if rng.choice([True,False]): h,a=a,h
        out.append({"match_no":no,"stage":"LEAGUE","group_name":"L","home":f"P:{h}","away":f"P:{a}"})
    out.append({"match_no":11,"stage":"FINAL","group_name":None,"home":"POS:L:1","away":"POS:L:2"})
    return out


def _three_player_group_schedule(members: list[str], rng: random.Random) -> list[tuple[str,str]]:
    pairs=list(combinations(members,2)); rng.shuffle(pairs)
    return pairs


def schedule_groups6(draw: dict, rng: random.Random) -> list[dict]:
    a=group_members(draw,"A"); b=group_members(draw,"B")
    pairs={"A":_three_player_group_schedule(a,rng),"B":_three_player_group_schedule(b,rng)}; idx={"A":0,"B":0}; out=[]
    for no,group in enumerate(["A","B"]*3,1):
        h,aw=pairs[group][idx[group]]; idx[group]+=1
        if rng.choice([True,False]): h,aw=aw,h
        out.append({"match_no":no,"stage":"GROUP","group_name":group,"home":f"P:{h}","away":f"P:{aw}"})
    # Pair order is finalized dynamically after the last group match to reduce back-to-back games.
    out += [
        {"match_no":7,"stage":"SF","group_name":None,"home":"G6:SF7H","away":"G6:SF7A"},
        {"match_no":8,"stage":"SF","group_name":None,"home":"G6:SF8H","away":"G6:SF8A"},
        {"match_no":9,"stage":"FINAL","group_name":None,"home":"W:7","away":"W:8"},
    ]
    return out


def schedule_groups6_full(draw: dict, rng: random.Random) -> list[dict]:
    a=group_members(draw,"A"); b=group_members(draw,"B")
    pairs={"A":_three_player_group_schedule(a,rng),"B":_three_player_group_schedule(b,rng)}; idx={"A":0,"B":0}; out=[]
    for no,group in enumerate(["A","B"]*3,1):
        h,aw=pairs[group][idx[group]]; idx[group]+=1
        if rng.choice([True,False]): h,aw=aw,h
        out.append({"match_no":no,"stage":"GROUP","group_name":group,"home":f"P:{h}","away":f"P:{aw}"})
    out += [
        {"match_no":7,"stage":"QF","group_name":None,"home":"G6F:QF7H","away":"G6F:QF7A"},
        {"match_no":8,"stage":"QF","group_name":None,"home":"G6F:QF8H","away":"G6F:QF8A"},
        # Whoever wins QF7 rests during QF8; whoever wins QF8 rests during SF9.
        {"match_no":9,"stage":"SF","group_name":None,"home":"G6F:SF9H","away":"W:7"},
        {"match_no":10,"stage":"SF","group_name":None,"home":"G6F:SF10H","away":"W:8"},
        {"match_no":11,"stage":"FINAL","group_name":None,"home":"W:9","away":"W:10"},
    ]
    return out


def schedule_groups7(draw: dict, rng: random.Random) -> list[dict]:
    a=group_members(draw,"A"); b=group_members(draw,"B")
    ar=_round_robin_pairs(a); br=_round_robin_pairs(b)
    # A-round pairs are disjoint. B games are spread through the schedule. Max idle run in the group phase is kept small.
    # Balanced A/B rhythm. Everyone gets a first match by M5, while no B player finishes the group absurdly early.
    # M3/M4 are one complete A round, so those consecutive matches are disjoint.
    ordered=[("A",ar[0][0]),("B",br[0][0]),("A",ar[1][0]),("A",ar[1][1]),("B",br[1][0]),("A",ar[0][1]),("A",ar[2][0]),("B",br[2][0]),("A",ar[2][1])]
    out=[]
    for no,(group,pair) in enumerate(ordered,1):
        h,aw=pair
        if rng.choice([True,False]): h,aw=aw,h
        out.append({"match_no":no,"stage":"GROUP","group_name":group,"home":f"P:{h}","away":f"P:{aw}"})
    # QF order is finalized dynamically after M9. Semifinals then give each QF winner one full match of rest.
    out += [
        {"match_no":10,"stage":"QF","group_name":None,"home":"G7:QF10H","away":"G7:QF10A"},
        {"match_no":11,"stage":"QF","group_name":None,"home":"G7:QF11H","away":"G7:QF11A"},
        {"match_no":12,"stage":"SF","group_name":None,"home":"G7:SF12H","away":"W:10"},
        {"match_no":13,"stage":"SF","group_name":None,"home":"G7:SF13H","away":"W:11"},
        {"match_no":14,"stage":"FINAL","group_name":None,"home":"W:12","away":"W:13"},
    ]
    return out



def schedule_groups7_sf(draw: dict, rng: random.Random) -> list[dict]:
    """7 graczy: grupy 4+3, następnie półfinały i finał."""
    a=group_members(draw,"A"); b=group_members(draw,"B")
    ar=_round_robin_pairs(a); br=_round_robin_pairs(b)
    ordered=[("A",ar[0][0]),("B",br[0][0]),("A",ar[1][0]),("A",ar[1][1]),("B",br[1][0]),("A",ar[0][1]),("A",ar[2][0]),("B",br[2][0]),("A",ar[2][1])]
    out=[]
    for no,(group,pair) in enumerate(ordered,1):
        h,aw=pair
        if rng.choice([True,False]): h,aw=aw,h
        out.append({"match_no":no,"stage":"GROUP","group_name":group,"home":f"P:{h}","away":f"P:{aw}"})
    out += [
        {"match_no":10,"stage":"SF","group_name":None,"home":"G7S:SF10H","away":"G7S:SF10A"},
        {"match_no":11,"stage":"SF","group_name":None,"home":"G7S:SF11H","away":"G7S:SF11A"},
        {"match_no":12,"stage":"FINAL","group_name":None,"home":"W:10","away":"W:11"},
    ]
    return out


def _schedule_groups8_phase(draw: dict, rng: random.Random) -> list[dict]:
    """12 meczów grupowych dla dwóch grup po 4, bez grania mecz po meczu przez tę samą osobę."""
    a=group_members(draw,"A"); b=group_members(draw,"B")
    ar=_round_robin_pairs(a); br=_round_robin_pairs(b)
    ordered=[]
    for rnd in range(3):
        ordered += [("A",ar[rnd][0]),("B",br[rnd][0]),("A",ar[rnd][1]),("B",br[rnd][1])]
    out=[]
    for no,(group,pair) in enumerate(ordered,1):
        h,aw=pair
        if rng.choice([True,False]): h,aw=aw,h
        out.append({"match_no":no,"stage":"GROUP","group_name":group,"home":f"P:{h}","away":f"P:{aw}"})
    return out


def schedule_groups8_sf(draw: dict, rng: random.Random) -> list[dict]:
    out=_schedule_groups8_phase(draw,rng)
    out += [
        {"match_no":13,"stage":"SF","group_name":None,"home":"G8S:SF13H","away":"G8S:SF13A"},
        {"match_no":14,"stage":"SF","group_name":None,"home":"G8S:SF14H","away":"G8S:SF14A"},
        {"match_no":15,"stage":"FINAL","group_name":None,"home":"W:13","away":"W:14"},
    ]
    return out


def schedule_groups8_barrage(draw: dict, rng: random.Random) -> list[dict]:
    out=_schedule_groups8_phase(draw,rng)
    # Kolejność obu ścieżek ustalamy dopiero po grupach. Zwycięzca każdego barażu
    # dostaje jeden pełny mecz odpoczynku przed swoim półfinałem.
    out += [
        {"match_no":13,"stage":"BARRAGE","group_name":None,"home":"G8B:B13H","away":"G8B:B13A"},
        {"match_no":14,"stage":"BARRAGE","group_name":None,"home":"G8B:B14H","away":"G8B:B14A"},
        {"match_no":15,"stage":"SF","group_name":None,"home":"G8B:SF15H","away":"W:13"},
        {"match_no":16,"stage":"SF","group_name":None,"home":"G8B:SF16H","away":"W:14"},
        {"match_no":17,"stage":"FINAL","group_name":None,"home":"W:15","away":"W:16"},
    ]
    return out


def schedule_double8(draw: dict, extra: dict) -> list[dict]:
    """Pełna drabinka Double Elimination dla 8 graczy, bez BYE."""
    s=draw["slots"]
    return [
        {"match_no":1,"stage":"WB","group_name":None,"home":f"P:{s['A']}","away":f"P:{s['B']}"},
        {"match_no":2,"stage":"WB","group_name":None,"home":f"P:{s['C']}","away":f"P:{s['D']}"},
        {"match_no":3,"stage":"WB","group_name":None,"home":f"P:{s['E']}","away":f"P:{s['F']}"},
        {"match_no":4,"stage":"WB","group_name":None,"home":f"P:{s['G']}","away":f"P:{s['H']}"},
        {"match_no":5,"stage":"WB","group_name":None,"home":"D8W:M5H","away":"D8W:M5A"},
        {"match_no":6,"stage":"WB","group_name":None,"home":"D8W:M6H","away":"D8W:M6A"},
        {"match_no":7,"stage":"LB","group_name":None,"home":"L:1","away":"L:2"},
        {"match_no":8,"stage":"LB","group_name":None,"home":"L:3","away":"L:4"},
        # Skrzyżowanie połówek ogranicza szybkie rewanże za pierwszy mecz.
        {"match_no":9,"stage":"LB","group_name":None,"home":"W:7","away":"L:6"},
        {"match_no":10,"stage":"LB","group_name":None,"home":"W:8","away":"L:5"},
        {"match_no":11,"stage":"WB_FINAL","group_name":None,"home":"W:5","away":"W:6"},
        {"match_no":12,"stage":"LB","group_name":None,"home":"W:9","away":"W:10"},
        {"match_no":13,"stage":"LB_FINAL","group_name":None,"home":"W:12","away":"L:11"},
        {"match_no":14,"stage":"FINAL","group_name":None,"home":"W:11","away":"W:13"},
    ]

def schedule_double5(draw: dict, extra: dict) -> list[dict]:
    s=draw["slots"]
    # The opponent for E is a real mid-tournament draw after M1 and M2.
    return [
        {"match_no":1,"stage":"WB","group_name":None,"home":f"P:{s['A']}","away":f"P:{s['B']}"},
        {"match_no":2,"stage":"WB","group_name":None,"home":f"P:{s['C']}","away":f"P:{s['D']}"},
        {"match_no":3,"stage":"WB","group_name":None,"home":f"P:{s['E']}","away":"D5:E_OPP"},
        {"match_no":4,"stage":"LB","group_name":None,"home":"L:1","away":"L:2"},
        {"match_no":5,"stage":"WB_FINAL","group_name":None,"home":"D5:OTHER","away":"W:3"},
        {"match_no":6,"stage":"LB","group_name":None,"home":"W:4","away":"L:3"},
        {"match_no":7,"stage":"LB_FINAL","group_name":None,"home":"W:6","away":"L:5"},
        {"match_no":8,"stage":"FINAL","group_name":None,"home":"W:5","away":"W:7"},
    ]


def schedule_double7(draw: dict, extra: dict) -> list[dict]:
    s=draw["slots"]
    # G has the winners-bracket bye. The first losers-bracket bye is drawn *after* M1-M3.
    # Order: both WB semifinals get sensible rest, then LB round 1, then crossed LB round 2.
    return [
        {"match_no":1,"stage":"WB","group_name":None,"home":f"P:{s['A']}","away":f"P:{s['B']}"},
        {"match_no":2,"stage":"WB","group_name":None,"home":f"P:{s['C']}","away":f"P:{s['D']}"},
        {"match_no":3,"stage":"WB","group_name":None,"home":f"P:{s['E']}","away":f"P:{s['F']}"},
        {"match_no":4,"stage":"WB","group_name":None,"home":"D7W:M4H","away":"D7W:M4A"},
        {"match_no":5,"stage":"WB","group_name":None,"home":"D7W:M5H","away":"D7W:M5A"},
        {"match_no":6,"stage":"LB","group_name":None,"home":"D7:LB1A","away":"D7:LB1B"},
        {"match_no":7,"stage":"LB","group_name":None,"home":"D7:LB_BYE","away":"D7:PAIR_BYE"},
        {"match_no":8,"stage":"LB","group_name":None,"home":"W:6","away":"D7:PAIR_W6"},
        {"match_no":9,"stage":"WB_FINAL","group_name":None,"home":"W:4","away":"W:5"},
        {"match_no":10,"stage":"LB","group_name":None,"home":"W:7","away":"W:8"},
        {"match_no":11,"stage":"LB_FINAL","group_name":None,"home":"W:10","away":"L:9"},
        {"match_no":12,"stage":"FINAL","group_name":None,"home":"W:9","away":"W:11"},
    ]


def schedule_for_format(draw: dict, format_key: str, extra: dict, rng: random.Random) -> list[dict]:
    if format_key=="league4_final": return schedule_league4(draw,rng)
    if format_key=="double5": return schedule_double5(draw,extra)
    if format_key=="league5_final": return schedule_league5(draw,rng)
    if format_key=="groups6": return schedule_groups6(draw,rng)
    if format_key=="groups6_full": return schedule_groups6_full(draw,rng)
    if format_key=="double7": return schedule_double7(draw,extra)
    if format_key=="groups7": return schedule_groups7(draw,rng)
    if format_key=="groups7_sf": return schedule_groups7_sf(draw,rng)
    if format_key=="groups8_sf": return schedule_groups8_sf(draw,rng)
    if format_key=="double8": return schedule_double8(draw,extra)
    if format_key=="groups8_barrage": return schedule_groups8_barrage(draw,rng)
    raise ValueError(format_key)


def group_table(group_player_ids: Iterable[str], matches: list[dict], tie_orders: dict[str,int]) -> list[dict]:
    ids=list(group_player_ids)
    stats={pid:{"player_id":pid,"m":0,"w":0,"d":0,"l":0,"gf":0,"ga":0,"gd":0,"pts":0} for pid in ids}; played=[]
    for m in matches:
        if m.get("home_score") is None or m.get("away_score") is None: continue
        h,a=m.get("home_player_id"),m.get("away_player_id")
        if h not in stats or a not in stats: continue
        hs,ass=int(m["home_score"]),int(m["away_score"])
        stats[h]["m"]+=1; stats[a]["m"]+=1; stats[h]["gf"]+=hs; stats[h]["ga"]+=ass; stats[a]["gf"]+=ass; stats[a]["ga"]+=hs
        if hs>ass: stats[h]["w"]+=1; stats[a]["l"]+=1; stats[h]["pts"]+=3
        elif hs<ass: stats[a]["w"]+=1; stats[h]["l"]+=1; stats[a]["pts"]+=3
        else: stats[h]["d"]+=1; stats[a]["d"]+=1; stats[h]["pts"]+=1; stats[a]["pts"]+=1
        played.append(m)
    for row in stats.values(): row["gd"]=row["gf"]-row["ga"]
    rows=list(stats.values()); rows.sort(key=lambda r:(r["pts"],r["gd"],r["gf"]),reverse=True)
    i=0
    while i<len(rows):
        key=(rows[i]["pts"],rows[i]["gd"],rows[i]["gf"]); j=i+1
        while j<len(rows) and (rows[j]["pts"],rows[j]["gd"],rows[j]["gf"])==key: j+=1
        block=rows[i:j]
        if len(block)==2:
            p1,p2=block[0]["player_id"],block[1]["player_id"]
            h2h=next((m for m in played if {m["home_player_id"],m["away_player_id"]}=={p1,p2}),None)
            if h2h and h2h["home_score"]!=h2h["away_score"]:
                win=h2h["home_player_id"] if h2h["home_score"]>h2h["away_score"] else h2h["away_player_id"]
                if block[1]["player_id"]==win: rows[i],rows[i+1]=rows[i+1],rows[i]
            else: rows[i:j]=sorted(block,key=lambda r:tie_orders.get(r["player_id"],9999))
        elif len(block)>1: rows[i:j]=sorted(block,key=lambda r:tie_orders.get(r["player_id"],9999))
        i=j
    for pos,row in enumerate(rows,1): row["position"]=pos
    return rows


def winner_from_result(home_score:int,away_score:int,home_id:str,away_id:str,home_pen:int|None=None,away_pen:int|None=None)->str|None:
    if home_score>away_score:return home_id
    if away_score>home_score:return away_id
    if home_pen is None or away_pen is None or home_pen==away_pen:return None
    return home_id if home_pen>away_pen else away_id


def optimize_opening_order(plan: list[dict], start_priority: dict[str, int] | None, rng: random.Random) -> list[dict]:
    """Reorder only the independent opening phase without changing pairings.

    start_priority maps player_id -> number of matches that player waited after their
    last appearance in the immediately previous tournament. Higher means they should
    get an earlier first match now. The optimizer also strongly avoids back-to-back
    games and discourages long gaps inside the opening phase.
    """
    priority = {str(k): max(0, int(v or 0)) for k, v in (start_priority or {}).items()}
    if not plan:
        return plan

    opening_idx = []
    for i, item in enumerate(plan):
        if item.get("stage") not in ("LEAGUE", "GROUP", "WB"):
            break
        home = str(item.get("home") or "")
        away = str(item.get("away") or "")
        if not (home.startswith("P:") and away.startswith("P:")):
            break
        opening_idx.append(i)
    if len(opening_idx) <= 1:
        return plan

    original = [dict(plan[i]) for i in opening_idx]
    slots = [int(plan[i]["match_no"]) for i in opening_idx]

    def pids(item):
        return (str(item["home"])[2:], str(item["away"])[2:])

    # Tiny random tie-breaks retain variety when two schedules are equally fair.
    noise = {i: rng.random() * 0.001 for i in range(len(original))}
    beam = [(0.0, [], frozenset(), {}, None, frozenset(range(len(original))))]
    beam_width = 420 if len(original) >= 9 else 160

    for pos in range(1, len(original) + 1):
        nxt = []
        for score, seq, seen, last_pos, prev_players, remaining in beam:
            for idx in remaining:
                item = original[idx]
                a, b = pids(item)
                players = frozenset((a, b))
                add = noise[idx]

                # Absolute priority: never intentionally schedule the same person
                # in consecutive matches when another reasonable order exists.
                if prev_players and players & prev_players:
                    add += 100000.0

                for pid in (a, b):
                    if pid not in seen:
                        # Waiting in the previous tournament increases the cost of
                        # making this player's first match late in the new one.
                        weight = 1.0 + (priority.get(pid, 0) * 8.0)
                        add += (pos - 1) * weight
                    else:
                        gap = pos - int(last_pos[pid]) - 1
                        if gap == 0:
                            add += 100000.0
                        elif gap == 1:
                            add += 8.0
                        elif gap > 3:
                            add += (gap - 3) * 5.0

                new_seen = set(seen); new_seen.update((a, b))
                new_last = dict(last_pos); new_last[a] = pos; new_last[b] = pos
                new_remaining = frozenset(x for x in remaining if x != idx)
                nxt.append((score + add, seq + [idx], frozenset(new_seen), new_last, players, new_remaining))

        nxt.sort(key=lambda x: x[0])
        beam = nxt[:beam_width]

    beam_best = min(beam, key=lambda x: x[0])[1]

    # Safety guard: compare the free-form optimizer with rotations of the already
    # hand-tuned schedule. We never accept more back-to-back games or a larger
    # maximum idle gap merely to honor cross-tournament priority.
    base_seq=list(range(len(original)))
    candidates=[base_seq,beam_best]
    for k in range(1,len(original)):
        candidates.append(base_seq[k:]+base_seq[:k])
    rev=list(reversed(base_seq))
    for k in range(len(original)):
        candidates.append(rev[k:]+rev[:k])

    def quality(seq):
        prev=None; back=0; first={}; positions={}
        for pos,idx in enumerate(seq,1):
            a,b=pids(original[idx]);players={a,b}
            if prev and players & prev:back+=1
            for pid in players:
                first.setdefault(pid,pos);positions.setdefault(pid,[]).append(pos)
            prev=players
        gaps=[b-a-1 for arr in positions.values() for a,b in zip(arr,arr[1:])]
        max_gap=max(gaps) if gaps else 0
        priority_cost=sum((first.get(pid,len(seq)+1)-1)*(1+priority.get(pid,0)*8) for pid in first)
        max_first=max(first.values()) if first else 0
        return (back,max_gap,priority_cost,max_first)

    best=min(candidates,key=quality)
    reordered=[]
    for match_no,idx in zip(slots,best):
        item=dict(original[idx]);item["match_no"]=match_no;reordered.append(item)

    out=[dict(x) for x in plan]
    for target_i,item in zip(opening_idx,reordered):out[target_i]=item
    return out


def apply_cross_tournament_bye_priority(draw: dict, format_key: str, start_priority: dict[str, int] | None, rng: random.Random) -> dict:
    """Avoid giving a delayed-entry/BYE slot to the player who already waited longest.

    Pairings remain random except for this one fairness correction. If all players have
    the same carry-over priority, the original random draw is untouched.
    """
    if format_key not in ("double5", "double7") or not start_priority:
        return draw
    bye_slot = "E" if format_key == "double5" else "G"
    slots = dict(draw.get("slots") or {})
    bye_pid = slots.get(bye_slot)
    if not bye_pid:
        return draw
    priority = {str(k): max(0, int(v or 0)) for k, v in start_priority.items()}
    bye_score = priority.get(str(bye_pid), 0)
    other_slots = [k for k in slots if k != bye_slot]
    if not other_slots:
        return draw
    min_score = min(priority.get(str(slots[k]), 0) for k in other_slots)
    if bye_score <= min_score:
        return draw
    candidates = [k for k in other_slots if priority.get(str(slots[k]), 0) == min_score]
    chosen = rng.choice(candidates)
    slots[bye_slot], slots[chosen] = slots[chosen], slots[bye_slot]
    return {**draw, "slots": slots}

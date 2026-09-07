from __future__ import annotations

from itertools import combinations
import random
from typing import Iterable

WILDCARD_TEAM_SUGGESTIONS = [
    "Manchester City",
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

FIXED_TEAMS = [
    "Bayern Monachium",
    "FC Barcelona",
    "PSG",
    "Liverpool",
]

# Draft 3–5: fixed clubs plus a reusable Wild Card choice. The Wild Card option may
# be used by more than one player as long as the concrete clubs are different.
BASE_TEAMS = FIXED_TEAMS + ["Dowolna drużyna (Real Madryt banned)"]

# 6+ wheel: four fixed clubs and enough Wild Card slots to fill the field.
SIX_TEAMS = FIXED_TEAMS + [
    "Dowolna drużyna #1 (Real Madryt banned)",
    "Dowolna drużyna #2 (Real Madryt banned)",
]
SEVEN_TEAMS = FIXED_TEAMS + [
    "Dowolna drużyna #1 (Real Madryt banned)",
    "Dowolna drużyna #2 (Real Madryt banned)",
    "Dowolna drużyna #3 (Real Madryt banned)",
]
EIGHT_TEAMS = FIXED_TEAMS + [
    "Dowolna drużyna #1 (Real Madryt banned)",
    "Dowolna drużyna #2 (Real Madryt banned)",
    "Dowolna drużyna #3 (Real Madryt banned)",
    "Dowolna drużyna #4 (Real Madryt banned)",
]

FORMAT_LABELS = {
    "duel1v1": "Mecz 1 vs 1",
    "league3_final": "Liga każdy z każdym + finał",
    "league4_final": "Liga każdy z każdym + finał",
    "double4": "Double elimination",
    "double5": "Double elimination",
    "league5_final": "Liga każdy z każdym + finał",
    "groups6": "Klasyczny: 2 grupy po 3 + półfinały + finał",
    "groups6_full": "Rozszerzony: 2 grupy po 3 + ćwierćfinały + półfinały + finał",
    "double6": "Double elimination",
    "double7": "Double elimination",
    "groups7": "Grupy 4+3 + ćwierćfinały + półfinały + finał",
    "groups7_sf": "Grupy 4+3 + półfinały + finał",
    "groups8_sf": "Grupy 4+4 + półfinały + finał",
    "double8": "Double elimination",
    "groups8_barrage": "Grupy 4+4 + baraże + półfinały + finał",
}

FORMAT_MATCH_COUNTS = {
    "duel1v1": "1 mecz",
    "league3_final": "4 mecze",
    "league4_final": "7 meczów",
    "double4": "6 meczów",
    "double5": "8 meczów",
    "league5_final": "11 meczów",
    "groups6": "9 meczów",
    "groups6_full": "11 meczów",
    "double6": "10 meczów",
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
    if player_count == 6: return SIX_TEAMS.copy()
    return BASE_TEAMS.copy()


def shuffled_assignments(player_ids: list[str], teams: list[str], rng: random.Random) -> dict[str, str]:
    if len(player_ids) != len(teams):
        raise ValueError("Liczba drużyn musi odpowiadać liczbie graczy.")
    pool = teams.copy(); rng.shuffle(pool)
    return dict(zip(player_ids, pool, strict=True))



def _weighted_pick(items: list[str], weights: dict[str, float], rng: random.Random) -> str:
    if not items:
        raise ValueError("Brak elementów do losowania.")
    vals=[max(0.0001,float(weights.get(str(item),1.0))) for item in items]
    total=sum(vals); pick=rng.random()*total; acc=0.0
    for item,weight in zip(items,vals):
        acc+=weight
        if pick<=acc:
            return item
    return items[-1]


def weighted_sample_without_replacement(items: list[str], weights: dict[str, float], rng: random.Random) -> list[str]:
    """Weighted random permutation. Every player always keeps a non-zero chance for every position."""
    remaining=[str(x) for x in items]; out=[]
    while remaining:
        chosen=_weighted_pick(remaining,weights,rng)
        out.append(chosen); remaining.remove(chosen)
    return out


def draft_order_weights(placement_by_player_id: dict[str,int] | None, previous_player_count: int | None, current_player_count: int) -> dict[str,float]:
    """Soft catch-up weights for 4/5-player draft order.

    First place is slightly less likely to choose early, last place slightly more likely.
    A linear percentile keeps the same behavior when the previous tournament had a
    different number of players. Unknown/new players stay neutral at 1.0.
    """
    placements={str(k):int(v) for k,v in (placement_by_player_id or {}).items() if v}
    prev_n=max(2,int(previous_player_count or 0)) if previous_player_count else 0
    if current_player_count==3:
        low,high=0.75,1.30
    elif current_player_count==4:
        low,high=0.70,1.35
    else:
        low,high=0.65,1.40
    out={}
    for pid,place in placements.items():
        if prev_n<2:
            out[pid]=1.0; continue
        pct=max(0.0,min(1.0,(place-1)/(prev_n-1)))
        out[pid]=low+(high-low)*pct
    return out


def weighted_draft_order(player_ids: list[str], placement_by_player_id: dict[str,int] | None, previous_player_count: int | None, current_player_count: int, rng: random.Random) -> list[str]:
    weights=draft_order_weights(placement_by_player_id,previous_player_count,current_player_count)
    return weighted_sample_without_replacement([str(x) for x in player_ids],weights,rng)


def wildcard_assignment_weights(placement_by_player_id: dict[str,int] | None) -> dict[str,float]:
    """Soft handicap for Wild Card assignment: 1st=1.40, 2nd=1.25, 3rd=1.10, others=1.00."""
    rank_weight={1:1.40,2:1.25,3:1.10}
    return {str(pid):rank_weight.get(int(place),1.0) for pid,place in (placement_by_player_id or {}).items()}


def _weighted_choice_pairs(options: list[tuple[object,float]], rng: random.Random):
    total=sum(max(0.000001,float(w)) for _,w in options)
    pick=rng.random()*total; acc=0.0
    for item,w in options:
        acc+=max(0.000001,float(w))
        if pick<=acc: return item
    return options[-1][0]


def weighted_fixed_team_matching(player_ids: list[str], fixed_teams: list[str], placement_by_player_id: dict[str,int] | None,
                                 team_ratings: dict[str,float] | None, previous_team_by_player_id: dict[str,str] | None,
                                 rng: random.Random) -> dict[str,str]:
    """Assign the four fixed clubs with soft live-strength handicap + anti-repeat.

    All 4! permutations remain possible. Previous champions/finalists are gently nudged
    toward currently weaker clubs. Repeating exactly the same club as the immediately
    previous tournament keeps 35% of normal weight, never zero.
    """
    import itertools, math
    pids=[str(x) for x in player_ids]
    if len(pids)!=len(fixed_teams):
        pool=fixed_teams.copy(); rng.shuffle(pool); return dict(zip(pids,pool))
    placements={str(k):int(v) for k,v in (placement_by_player_id or {}).items() if v}
    ratings={str(k):float(v) for k,v in (team_ratings or {}).items()}
    previous={str(k):str(v) for k,v in (previous_team_by_player_id or {}).items() if v}
    strength={1:0.018,2:0.012,3:0.006}
    opts=[]
    for perm in itertools.permutations(fixed_teams):
        w=1.0
        for pid,team in zip(pids,perm):
            rating=float(ratings.get(team,50.0))
            coef=strength.get(placements.get(pid),0.0)
            # rating >50 means stronger; top finishers are slightly less likely to get it.
            w*=math.exp((50.0-rating)*coef)
            if previous.get(pid) and previous.get(pid).casefold()==str(team).casefold():
                w*=0.35
        opts.append((perm,w))
    chosen=_weighted_choice_pairs(opts,rng)
    return dict(zip(pids,chosen))


def reveal_order_with_previous_finalists(player_ids: list[str], placement_by_player_id: dict[str,int] | None, rng: random.Random) -> list[str]:
    """For 6+ wheels reveal non-finalists first, runner-up next, champion last.

    This affects only who gets to choose a concrete Wild Card first; team-slot assignment
    itself remains random/weighted. Missing/new players are treated as non-finalists.
    """
    placements={str(k):int(v) for k,v in (placement_by_player_id or {}).items() if v}
    normal=[str(pid) for pid in player_ids if placements.get(str(pid)) not in (1,2)]
    rng.shuffle(normal)
    runner=[str(pid) for pid in player_ids if placements.get(str(pid))==2]
    champ=[str(pid) for pid in player_ids if placements.get(str(pid))==1]
    rng.shuffle(runner); rng.shuffle(champ)
    return normal+runner+champ

def weighted_team_assignments(player_ids: list[str], teams: list[str], placement_by_player_id: dict[str,int] | None, rng: random.Random,
                              team_ratings: dict[str,float] | None = None, previous_team_by_player_id: dict[str,str] | None = None) -> dict[str,str]:
    """Assign Wild Card slots softly by prior finish, then fixed clubs intelligently.

    Wild Card: 1st=1.40, 2nd=1.25, 3rd=1.10.
    Fixed clubs: live strength is a soft handicap for top finishers and exact previous-team
    repeats are reduced to 35% normal weight. Every valid assignment remains possible.
    """
    if len(player_ids)!=len(teams):
        raise ValueError("Liczba drużyn musi odpowiadać liczbie graczy.")
    pids=[str(x) for x in player_ids]
    wild=[t for t in teams if "Dowolna drużyna" in str(t)]
    fixed=[t for t in teams if "Dowolna drużyna" not in str(t)]
    if not wild:
        return weighted_fixed_team_matching(pids,fixed,placement_by_player_id,team_ratings,previous_team_by_player_id,rng)
    weights=wildcard_assignment_weights(placement_by_player_id)
    weighted_order=weighted_sample_without_replacement(pids,weights,rng)
    wild_players=weighted_order[:len(wild)]
    wild_set=set(wild_players)
    remaining=[pid for pid in pids if pid not in wild_set]
    wild_pool=wild.copy(); rng.shuffle(wild_pool)
    out={pid:team for pid,team in zip(wild_players,wild_pool,strict=True)}
    out.update(weighted_fixed_team_matching(remaining,fixed,placement_by_player_id,team_ratings,previous_team_by_player_id,rng))
    return out

def build_draw(player_ids: list[str], format_key: str, rng: random.Random) -> dict:
    ids = player_ids.copy(); rng.shuffle(ids)
    if format_key == "duel1v1":
        return {"slots": dict(zip(["A", "B"], ids, strict=True))}
    if format_key == "league3_final":
        return {"slots": dict(zip(["A", "B", "C"], ids, strict=True))}
    if format_key in ("league4_final","double4"):
        return {"slots": dict(zip(["A", "B", "C", "D"], ids, strict=True))}
    if format_key in ("double5", "league5_final"):
        return {"slots": dict(zip(["A", "B", "C", "D", "E"], ids, strict=True))}
    if format_key in ("groups6", "groups6_full"):
        seq = ["A1", "B1", "A2", "B2", "A3", "B3"]
        return {"slots": dict(zip(seq, ids, strict=True))}
    if format_key == "double6":
        return {"slots": dict(zip(["A","B","C","D","E","F"],ids,strict=True))}
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


def schedule_league3(draw: dict, rng: random.Random) -> list[dict]:
    s=draw["slots"]
    pairs=[(s["A"],s["B"]),(s["C"],s["A"]),(s["B"],s["C"])]
    out=[]
    for no,(h,a) in enumerate(pairs,1):
        if rng.choice([True,False]): h,a=a,h
        out.append({"match_no":no,"stage":"LEAGUE","group_name":"L","home":f"P:{h}","away":f"P:{a}"})
    out.append({"match_no":4,"stage":"FINAL","group_name":None,"home":"POS:L:1","away":"POS:L:2"})
    return out


def schedule_double4(draw: dict, extra: dict) -> list[dict]:
    s=draw["slots"]
    return [
        {"match_no":1,"stage":"WB","group_name":None,"home":f"P:{s['A']}","away":f"P:{s['B']}"},
        {"match_no":2,"stage":"WB","group_name":None,"home":f"P:{s['C']}","away":f"P:{s['D']}"},
        {"match_no":3,"stage":"LB","group_name":None,"home":"L:1","away":"L:2"},
        {"match_no":4,"stage":"WB_FINAL","group_name":None,"home":"W:1","away":"W:2"},
        {"match_no":5,"stage":"LB_FINAL","group_name":None,"home":"W:3","away":"L:4"},
        {"match_no":6,"stage":"FINAL","group_name":None,"home":"W:4","away":"W:5"},
    ]

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


def schedule_double6(draw: dict, extra: dict) -> list[dict]:
    """6-player double elimination with two initial Winners lucky passes, 10 matches.

    E/F enter the WB semifinals. The bracket keeps a single Grand Final with our 1:0
    Winners bonus, so the total stays at 10 matches.
    """
    s=draw["slots"]
    return [
        {"match_no":1,"stage":"WB","group_name":None,"home":f"P:{s['A']}","away":f"P:{s['B']}"},
        {"match_no":2,"stage":"WB","group_name":None,"home":f"P:{s['C']}","away":f"P:{s['D']}"},
        {"match_no":3,"stage":"WB","group_name":None,"home":"W:1","away":f"P:{s['E']}"},
        {"match_no":4,"stage":"WB","group_name":None,"home":"W:2","away":f"P:{s['F']}"},
        {"match_no":5,"stage":"LB","group_name":None,"home":"L:1","away":"L:2"},
        {"match_no":6,"stage":"LB","group_name":None,"home":"W:5","away":"L:3"},
        {"match_no":7,"stage":"WB_FINAL","group_name":None,"home":"W:3","away":"W:4"},
        {"match_no":8,"stage":"LB","group_name":None,"home":"W:6","away":"L:4"},
        {"match_no":9,"stage":"LB_FINAL","group_name":None,"home":"W:8","away":"L:7"},
        {"match_no":10,"stage":"FINAL","group_name":None,"home":"W:7","away":"W:9"},
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
    if format_key=="duel1v1":
        s=draw["slots"]; return [{"match_no":1,"stage":"DUEL","group_name":None,"home":f"P:{s['A']}","away":f"P:{s['B']}"}]
    if format_key=="league3_final": return schedule_league3(draw,rng)
    if format_key=="league4_final": return schedule_league4(draw,rng)
    if format_key=="double4": return schedule_double4(draw,extra)
    if format_key=="double5": return schedule_double5(draw,extra)
    if format_key=="league5_final": return schedule_league5(draw,rng)
    if format_key=="groups6": return schedule_groups6(draw,rng)
    if format_key=="groups6_full": return schedule_groups6_full(draw,rng)
    if format_key=="double6": return schedule_double6(draw,extra)
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


def optimize_opening_order(plan: list[dict], start_priority: dict[str, int] | None, rng: random.Random, new_player_ids: list[str] | None = None) -> list[dict]:
    """Reorder only the independent opening games; never change the drawn pairings.

    Logical match numbers stay attached to their original pairings. The returned list
    only describes the preferred *play order*. Higher carry-over wait means an earlier
    first game is preferred, while back-to-back games and very long gaps are penalized.
    A player who did not take part in the immediately previous tournament gets an
    additional opening priority, so a newcomer/returning-after-a-break player is not
    left waiting until match 5 or 6 when an equally safe earlier order exists.
    """
    priority = {str(k): max(0, int(v or 0)) for k, v in (start_priority or {}).items()}
    newcomers = {str(x) for x in (new_player_ids or []) if x}
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
        return [dict(x) for x in plan]

    opening = [dict(plan[i]) for i in opening_idx]

    def pids(item):
        return (str(item["home"])[2:], str(item["away"])[2:])

    # Random tie-breaks keep schedules varied when fairness scores are equal.
    noise = {i: rng.random() * 0.001 for i in range(len(opening))}
    beam = [(0.0, [], frozenset(), {}, None, frozenset(range(len(opening))))]
    beam_width = 420 if len(opening) >= 9 else 180

    for pos in range(1, len(opening) + 1):
        nxt = []
        for score, seq, seen, last_pos, prev_players, remaining in beam:
            for idx in remaining:
                item = opening[idx]
                a, b = pids(item)
                players = frozenset((a, b))
                add = noise[idx]
                if prev_players and players & prev_players:
                    add += 100000.0
                for pid in (a, b):
                    if pid not in seen:
                        # Cross-tournament waiting only influences *when* this already
                        # drawn match is played, never who plays whom.
                        weight = 1.0 + (priority.get(pid, 0) * 4.0)
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
    base_seq = list(range(len(opening)))
    candidates = [base_seq, beam_best]
    for k in range(1, len(opening)):
        candidates.append(base_seq[k:] + base_seq[:k])
    rev = list(reversed(base_seq))
    for k in range(len(opening)):
        candidates.append(rev[k:] + rev[:k])

    def quality(seq):
        prev = None; back = 0; first = {}; positions = {}
        for pos, idx in enumerate(seq, 1):
            a, b = pids(opening[idx]); players = {a, b}
            if prev and players & prev:
                back += 1
            for pid in players:
                first.setdefault(pid, pos); positions.setdefault(pid, []).append(pos)
            prev = players
        gaps = [b-a-1 for arr in positions.values() for a, b in zip(arr, arr[1:])]
        max_gap = max(gaps) if gaps else 0
        max_first = max(first.values()) if first else 0

        # Players absent from the immediately previous tournament should start early.
        # We minimise both the latest newcomer debut and their total waiting time.
        newcomer_positions = [first.get(pid, len(seq)+1) for pid in newcomers if pid in first]
        newcomer_latest = max(newcomer_positions) if newcomer_positions else 0
        newcomer_delay = sum(max(0, pos-1) for pos in newcomer_positions)

        # A player from the very last match of the previous tournament should ideally
        # get one complete match of rest before starting again.
        just_finished = {pid for pid,wait in priority.items() if wait == 0 and pid not in newcomers}
        immediate_restart = sum(1 for pid in just_finished if first.get(pid) == 1)

        # Long-waiting players are gently pulled towards an earlier opener.
        priority_cost = sum((first.get(pid, len(seq)+1)-1) * (1 + priority.get(pid, 0)*4) for pid in first)
        return (back, max_gap, max_first, newcomer_latest, newcomer_delay, immediate_restart, priority_cost)

    # Never buy cross-tournament fairness by making the current tournament's opening
    # schedule worse. The original schedule is always a candidate, so this set cannot
    # be empty. Among equally safe orders, first avoid an immediate restart for someone
    # who just played the previous final, then favour players who waited longer.
    base_q = quality(base_seq)
    safe = [seq for seq in candidates if quality(seq)[0] <= base_q[0] and quality(seq)[1] <= base_q[1] and quality(seq)[2] <= base_q[2]]
    best = min(safe, key=lambda seq:(quality(seq)[0], quality(seq)[3], quality(seq)[4], quality(seq)[5], quality(seq)[1], quality(seq)[2], quality(seq)[6]))
    reordered_opening = [opening[idx] for idx in best]
    out = [dict(x) for x in plan]
    # Only list order changes. Every item keeps its original match_no and sources.
    for target_i, item in zip(opening_idx, reordered_opening):
        out[target_i] = item
    return out


def weighted_bye_choice(candidates: list[str], start_priority: dict[str, int] | None, rng: random.Random, new_player_ids: list[str] | None = None) -> str | None:
    """Random BYE draw with a soft handicap for at most two longest-waiting players.

    Nobody is excluded. Among the actual BYE candidates, the longest-waiting player
    gets 25% of normal weight and the second-longest gets 50%. Ties are randomized,
    so at most two people are discounted and the draw always remains genuinely random.
    """
    vals = [str(x) for x in candidates if x]
    if not vals:
        return None
    priority = {str(k): max(0, int(v or 0)) for k, v in (start_priority or {}).items()}
    newcomers = {str(x) for x in (new_player_ids or []) if x}
    ranked = [(priority.get(pid, 0), rng.random(), pid) for pid in vals if pid not in newcomers]
    ranked.sort(key=lambda x: (x[0], x[1]), reverse=True)
    discounted = {pid: 0.15 for pid in vals if pid in newcomers}
    if ranked and ranked[0][0] > 0:
        discounted[ranked[0][2]] = 0.25
    if len(ranked) > 1 and ranked[1][0] > 0:
        discounted[ranked[1][2]] = 0.50
    weights = [discounted.get(pid, 1.0) for pid in vals]
    total = sum(weights)
    pick = rng.random() * total
    acc = 0.0
    for pid, weight in zip(vals, weights):
        acc += weight
        if pick <= acc:
            return pid
    return vals[-1]

def apply_cross_tournament_bye_priority(draw: dict, format_key: str, start_priority: dict[str, int] | None, rng: random.Random, new_player_ids: list[str] | None = None) -> dict:
    """Softly weight initial Winners lucky passes while keeping pairings random."""
    if format_key not in ("double5", "double6", "double7") or not start_priority:
        return draw
    slots=dict(draw.get("slots") or {})
    if format_key in ("double5","double7"):
        bye_slot = "E" if format_key == "double5" else "G"
        if bye_slot not in slots: return draw
        selected=weighted_bye_choice(list(slots.values()),start_priority,rng,new_player_ids)
        if not selected or selected==slots[bye_slot]: return draw
        selected_slot=next((slot for slot,pid in slots.items() if str(pid)==str(selected)),None)
        if selected_slot:
            slots[bye_slot],slots[selected_slot]=slots[selected_slot],slots[bye_slot]
        return {**draw,"slots":slots}

    # DE6 has two Winners lucky passes (E/F). Draw both without replacement using the
    # same soft weights: newcomers are strongly discouraged from waiting, never banned.
    vals=list(slots.values()); remaining=vals.copy(); chosen=[]
    for _ in range(2):
        pick=weighted_bye_choice(remaining,start_priority,rng,new_player_ids)
        if not pick: break
        chosen.append(pick); remaining.remove(pick)
    if len(chosen)!=2: return draw
    # Keep A-D pairings as originally drawn as much as possible: swap chosen players into E/F.
    for target,pid in zip(("E","F"),chosen):
        if slots.get(target)==pid: continue
        src=next((k for k,v in slots.items() if str(v)==str(pid)),None)
        if src: slots[target],slots[src]=slots[src],slots[target]
    return {**draw,"slots":slots}


from __future__ import annotations

from itertools import combinations
import random
from typing import Iterable

WILDCARD_TEAM_SUGGESTIONS = [
    "Manchester City", "Inter", "Atletico", "BVB", "Man United", "Arsenal", "Chelsea",
    "Bayer Leverkusen", "Tottenham", "AC Milan", "Napoli",
]

GAME_VERSIONS = ("FC26", "FC27")
REAL_HELPER_TEAM = "Real Madryt"

FC26_FIXED_TEAMS = ["Bayern Monachium", "FC Barcelona", "PSG", "Liverpool"]
FC26_WILDCARD_SUGGESTIONS = WILDCARD_TEAM_SUGGESTIONS.copy()
FC27_FIXED_TEAMS = ["PSG", "Bayern Monachium", "FC Barcelona", "Arsenal", "Manchester City"]
FC27_WILDCARD_SUGGESTIONS = [
    "Liverpool", "Atletico", "Juventus", "Man United", "Chelsea", "Napoli", "BVB", "Roma", "Tottenham", "Aston Villa",
]

# Backwards-compatible aliases used by existing screens. FC26 remains legacy/default.
FIXED_TEAMS = FC26_FIXED_TEAMS
BASE_TEAMS = FIXED_TEAMS + ["Dowolna drużyna (Real Madryt banned)"]
SIX_TEAMS = FIXED_TEAMS + ["Dowolna drużyna #1 (Real Madryt banned)", "Dowolna drużyna #2 (Real Madryt banned)"]
SEVEN_TEAMS = FIXED_TEAMS + ["Dowolna drużyna #1 (Real Madryt banned)", "Dowolna drużyna #2 (Real Madryt banned)", "Dowolna drużyna #3 (Real Madryt banned)"]
EIGHT_TEAMS = FIXED_TEAMS + ["Dowolna drużyna #1 (Real Madryt banned)", "Dowolna drużyna #2 (Real Madryt banned)", "Dowolna drużyna #3 (Real Madryt banned)", "Dowolna drużyna #4 (Real Madryt banned)"]


def normalize_game_version(value: str | None) -> str:
    raw=str(value or "FC26").strip().upper().replace("EA SPORTS ","").replace("EA FC ","FC")
    return raw if raw in GAME_VERSIONS else "FC26"


def fixed_teams_for_version(game_version: str) -> list[str]:
    return (FC27_FIXED_TEAMS if normalize_game_version(game_version)=="FC27" else FC26_FIXED_TEAMS).copy()


def wildcard_suggestions_for_version(game_version: str) -> list[str]:
    return (FC27_WILDCARD_SUGGESTIONS if normalize_game_version(game_version)=="FC27" else FC26_WILDCARD_SUGGESTIONS).copy()


def allowed_teams(player_count: int, game_version: str = "FC26") -> list[str]:
    fixed=fixed_teams_for_version(game_version)
    # FC27: exactly five normal teams; every extra seat is a real weakening Wild Card.
    normal_count=5 if normalize_game_version(game_version)=="FC27" else 4
    fixed=fixed[:normal_count]
    if player_count <= len(fixed):
        # 3–4 stay manual draft; 5 uses the full normal FC27 pool without WC.
        return fixed + (["Dowolna drużyna (Real Madryt banned)"] if normalize_game_version(game_version)=="FC26" else [])
    wc_count=max(0,player_count-len(fixed))
    return fixed + [f"Dowolna drużyna #{i+1} (Real Madryt banned)" for i in range(wc_count)]


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
    "swiss8": "Swiss 3 rundy + TOP4",
    "groups9_final4": "3 grupy po 3 + Final Four",
    "groups9_barrage_final3": "3 grupy po 3 + baraże + Final Three",
    "groups9_top8": "3 grupy po 3 + TOP8",
    "double9": "Double elimination (1 play-in)",
    "groups10_sf": "2 grupy po 5 + półfinały",
    "swiss10": "Swiss 3 rundy + TOP4",
    "double10": "Double elimination (2 play-iny)",
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
    "swiss8": "15 meczów",
    "groups9_final4": "12 meczów",
    "groups9_barrage_final3": "15 meczów",
    "groups9_top8": "16 meczów",
    "double9": "16 meczów",
    "groups10_sf": "23 mecze",
    "swiss10": "18 meczów",
    "double10": "18 meczów",
}


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
    """Soft handicap for Wild Card assignment: 1st=1.55, 2nd=1.35, 3rd=1.15, others=1.00."""
    rank_weight={1:1.55,2:1.35,3:1.15}
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

    Wild Card: 1st=1.55, 2nd=1.35, 3rd=1.15.
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
    if format_key == "swiss8":
        return {"slots": dict(zip(list("ABCDEFGH"), ids, strict=True))}
    if format_key in ("groups9_final4","groups9_barrage_final3","groups9_top8"):
        seq=["A1","B1","C1","A2","B2","C2","A3","B3","C3"]
        return {"slots":dict(zip(seq,ids,strict=True))}
    if format_key == "double9":
        return {"slots":dict(zip(list("ABCDEFGHI"),ids,strict=True))}
    if format_key == "groups10_sf":
        seq=["A1","B1","A2","B2","A3","B3","A4","B4","A5","B5"]
        return {"slots":dict(zip(seq,ids,strict=True))}
    if format_key in ("swiss10","double10"):
        return {"slots":dict(zip(list("ABCDEFGHIJ"),ids,strict=True))}
    raise ValueError(f"Nieznany format: {format_key}")

def structure_match_preview(format_key: str, draw: dict) -> list[dict]:
    """Human-facing initial pairing preview for match-based formats.

    This is intentionally symbolic: players come from draw slots, while future
    dependencies stay as labels such as "Zwycięzca M1".  The same preview is
    used by Streamlit, PWA and TV so the official draw always tells the same story.
    """
    s=draw.get("slots") or {}
    def P(slot: str) -> dict:
        return {"kind":"player","slot":slot,"player_id":str(s.get(slot) or ""),"reveal_order":ord(slot[0])-ord('A') if slot and slot[0].isalpha() else 99}
    def R(label: str) -> dict:
        return {"kind":"ref","label":label,"reveal_order":None}
    def M(no: int|None, stage: str, label: str, home: dict, away: dict|None=None) -> dict:
        return {"match_no":no,"stage":stage,"stage_label":label,"home":home,"away":away}
    if format_key=="double4":
        return [M(1,"WB","WB • RUNDA 1",P("A"),P("B")),M(2,"WB","WB • RUNDA 1",P("C"),P("D"))]
    if format_key=="double5":
        return [M(1,"WB","WB • RUNDA 1",P("A"),P("B")),M(2,"WB","WB • RUNDA 1",P("C"),P("D")),M(None,"WB_BYE","WB • WOLNY LOS",P("E"),None)]
    if format_key=="double6":
        return [M(1,"WB","WB • RUNDA 1",P("A"),P("B")),M(2,"WB","WB • RUNDA 1",P("C"),P("D")),M(3,"WB","WB • RUNDA 2",R("Zwycięzca M1"),P("E")),M(4,"WB","WB • RUNDA 2",R("Zwycięzca M2"),P("F"))]
    if format_key=="double7":
        return [M(1,"WB","WB • RUNDA 1",P("A"),P("B")),M(2,"WB","WB • RUNDA 1",P("C"),P("D")),M(3,"WB","WB • RUNDA 1",P("E"),P("F")),M(None,"WB_BYE","WB • WOLNY LOS",P("G"),None)]
    if format_key=="double8":
        return [M(1,"WB","WB • QF",P("A"),P("B")),M(2,"WB","WB • QF",P("C"),P("D")),M(3,"WB","WB • QF",P("E"),P("F")),M(4,"WB","WB • QF",P("G"),P("H"))]
    if format_key=="double9":
        return [M(1,"PLAY_IN","PLAY-IN",P("A"),P("B")),M(2,"WB","WB • QF",P("C"),P("D")),M(3,"WB","WB • QF",P("E"),P("F")),M(4,"WB","WB • QF",P("G"),P("H")),M(5,"WB","WB • QF",P("I"),R("Zwycięzca M1"))]
    if format_key=="double10":
        return [M(1,"PLAY_IN","PLAY-IN",P("A"),P("B")),M(2,"PLAY_IN","PLAY-IN",P("C"),P("D")),M(3,"WB","WB • QF",P("E"),P("F")),M(4,"WB","WB • QF",P("G"),P("H")),M(5,"WB","WB • QF",P("I"),R("Zwycięzca M1")),M(6,"WB","WB • QF",P("J"),R("Zwycięzca M2"))]
    if format_key in ("swiss8","swiss10"):
        letters=list("ABCDEFGH" if format_key=="swiss8" else "ABCDEFGHIJ")
        return [M(i//2+1,"SWISS_R1","SWISS • RUNDA 1",P(letters[i]),P(letters[i+1])) for i in range(0,len(letters),2)]
    return []


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
        # LB cross is chosen dynamically: only immediate rematches are avoided; otherwise it is random.
        {"match_no":9,"stage":"LB","group_name":None,"home":"W:7","away":"D8:PAIR7"},
        {"match_no":10,"stage":"LB","group_name":None,"home":"W:8","away":"D8:PAIR8"},
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
        # LB cross is a real draw once both WB semifinals are known.  The routes are
        # stored symbolically so the draw can happen before M5 is necessarily played.
        {"match_no":6,"stage":"LB","group_name":None,"home":"D6:M6H","away":"D6:M6A"},
        {"match_no":7,"stage":"WB_FINAL","group_name":None,"home":"W:3","away":"W:4"},
        {"match_no":8,"stage":"LB","group_name":None,"home":"D6:M8H","away":"D6:M8A"},
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


def _orient(pair: tuple[str,str], rng: random.Random) -> tuple[str,str]:
    a,b=pair
    return (b,a) if rng.choice([True,False]) else (a,b)

def schedule_swiss(draw: dict, player_count: int, rng: random.Random) -> list[dict]:
    # build_draw() already created a randomized A..H/J order.  R1 must use that exact
    # visible draw; do not secretly reshuffle here after the user has seen the pairs.
    ids=list(draw["slots"].values())
    out=[]; no=1
    # R2/R3 are generated dynamically from standings. Home/away orientation may vary,
    # but the R1 opponents are exactly the pairs revealed before the tournament.
    for i in range(0,player_count,2):
        h,a=_orient((ids[i],ids[i+1]),rng); out.append({"match_no":no,"stage":"SWISS_R1","group_name":"S","home":f"P:{h}","away":f"P:{a}"}); no+=1
    per=player_count//2
    for rnd in (2,3):
        for slot in range(per):
            out.append({"match_no":no,"stage":f"SWISS_R{rnd}","group_name":"S","home":f"SWISS:R{rnd}:{slot}:H","away":f"SWISS:R{rnd}:{slot}:A"}); no+=1
    out += [
        {"match_no":no,"stage":"SF","group_name":None,"home":"SWISS:SF:1:H","away":"SWISS:SF:1:A"},
        {"match_no":no+1,"stage":"SF","group_name":None,"home":"SWISS:SF:2:H","away":"SWISS:SF:2:A"},
        {"match_no":no+2,"stage":"FINAL","group_name":None,"home":f"W:{no}","away":f"W:{no+1}"},
    ]
    return out

def _schedule_groups9_phase(draw: dict, rng: random.Random) -> list[dict]:
    pairs={g:_three_player_group_schedule(group_members(draw,g),rng) for g in ("A","B","C")}; idx={g:0 for g in pairs}; out=[]
    for no,g in enumerate(["A","B","C"]*3,1):
        h,a=_orient(pairs[g][idx[g]],rng); idx[g]+=1
        out.append({"match_no":no,"stage":"GROUP","group_name":g,"home":f"P:{h}","away":f"P:{a}"})
    return out

def schedule_groups9_final4(draw: dict, rng: random.Random) -> list[dict]:
    out=_schedule_groups9_phase(draw,rng)
    out += [
        {"match_no":10,"stage":"SF","group_name":None,"home":"G9F4:SF10H","away":"G9F4:SF10A"},
        {"match_no":11,"stage":"SF","group_name":None,"home":"G9F4:SF11H","away":"G9F4:SF11A"},
        {"match_no":12,"stage":"FINAL","group_name":None,"home":"W:10","away":"W:11"},
    ]; return out

def schedule_groups9_barrage_final3(draw: dict, rng: random.Random) -> list[dict]:
    out=_schedule_groups9_phase(draw,rng)
    out += [
        {"match_no":10,"stage":"BARRAGE","group_name":None,"home":"G9B:B10H","away":"G9B:B10A"},
        {"match_no":11,"stage":"BARRAGE","group_name":None,"home":"G9B:B11H","away":"G9B:B11A"},
        {"match_no":12,"stage":"BARRAGE","group_name":None,"home":"G9B:B12H","away":"G9B:B12A"},
        {"match_no":13,"stage":"FINAL3","group_name":"F3","home":"G9B:F13H","away":"G9B:F13A"},
        {"match_no":14,"stage":"FINAL3","group_name":"F3","home":"L:13","away":"G9B:F14THIRD"},
        {"match_no":15,"stage":"FINAL3","group_name":"F3","home":"W:13","away":"G9B:F14THIRD"},
    ]; return out

def schedule_groups9_top8(draw: dict, rng: random.Random) -> list[dict]:
    out=_schedule_groups9_phase(draw,rng)
    for no in range(10,14): out.append({"match_no":no,"stage":"QF","group_name":None,"home":f"G9T:Q{no}H","away":f"G9T:Q{no}A"})
    out += [
        {"match_no":14,"stage":"SF","group_name":None,"home":"W:10","away":"W:11"},
        {"match_no":15,"stage":"SF","group_name":None,"home":"W:12","away":"W:13"},
        {"match_no":16,"stage":"FINAL","group_name":None,"home":"W:14","away":"W:15"},
    ]; return out

def schedule_groups10_sf(draw: dict, rng: random.Random) -> list[dict]:
    a=group_members(draw,"A"); b=group_members(draw,"B")
    ar=_round_robin_pairs(a); br=_round_robin_pairs(b); out=[]; no=1
    # Alternate groups by rounds; each 5-player round has two disjoint games and one bye.
    for r in range(5):
        for g,pairs in (("A",ar[r]),("B",br[r])):
            for pair in pairs:
                h,aw=_orient(pair,rng); out.append({"match_no":no,"stage":"GROUP","group_name":g,"home":f"P:{h}","away":f"P:{aw}"}); no+=1
    out += [
        {"match_no":21,"stage":"SF","group_name":None,"home":"POS:A:1","away":"POS:B:2"},
        {"match_no":22,"stage":"SF","group_name":None,"home":"POS:B:1","away":"POS:A:2"},
        {"match_no":23,"stage":"FINAL","group_name":None,"home":"W:21","away":"W:22"},
    ]; return out

def schedule_double9(draw: dict, extra: dict) -> list[dict]:
    s=draw["slots"]
    return [
        {"match_no":1,"stage":"PLAY_IN","group_name":None,"home":f"P:{s['A']}","away":f"P:{s['B']}"},
        {"match_no":2,"stage":"WB","group_name":None,"home":f"P:{s['C']}","away":f"P:{s['D']}"},
        {"match_no":3,"stage":"WB","group_name":None,"home":f"P:{s['E']}","away":f"P:{s['F']}"},
        {"match_no":4,"stage":"WB","group_name":None,"home":f"P:{s['G']}","away":f"P:{s['H']}"},
        {"match_no":5,"stage":"WB","group_name":None,"home":f"P:{s['I']}","away":"W:1"},
        {"match_no":6,"stage":"WB","group_name":None,"home":"W:2","away":"W:3"},
        {"match_no":7,"stage":"WB","group_name":None,"home":"W:4","away":"W:5"},
        {"match_no":8,"stage":"WB_FINAL","group_name":None,"home":"W:6","away":"W:7"},
        {"match_no":9,"stage":"LB","group_name":None,"home":"D9:L9H","away":"D9:L9A"},
        {"match_no":10,"stage":"LB","group_name":None,"home":"D9:L10H","away":"D9:L10A"},
        {"match_no":11,"stage":"LB","group_name":None,"home":"D9:L11H","away":"D9:L11A"},
        {"match_no":12,"stage":"LB","group_name":None,"home":"D9:L12H","away":"D9:L12A"},
        {"match_no":13,"stage":"LB","group_name":None,"home":"D9:L13H","away":"D9:L13A"},
        {"match_no":14,"stage":"LB","group_name":None,"home":"D9:L14H","away":"D9:L14A"},
        {"match_no":15,"stage":"LB_FINAL","group_name":None,"home":"D9:L15H","away":"D9:L15A"},
        {"match_no":16,"stage":"FINAL","group_name":None,"home":"W:8","away":"W:15"},
    ]

def schedule_double10(draw: dict, extra: dict) -> list[dict]:
    s=draw["slots"]
    return [
        {"match_no":1,"stage":"PLAY_IN","group_name":None,"home":f"P:{s['A']}","away":f"P:{s['B']}"},
        {"match_no":2,"stage":"PLAY_IN","group_name":None,"home":f"P:{s['C']}","away":f"P:{s['D']}"},
        {"match_no":3,"stage":"WB","group_name":None,"home":f"P:{s['E']}","away":f"P:{s['F']}"},
        {"match_no":4,"stage":"WB","group_name":None,"home":f"P:{s['G']}","away":f"P:{s['H']}"},
        {"match_no":5,"stage":"WB","group_name":None,"home":f"P:{s['I']}","away":"W:1"},
        {"match_no":6,"stage":"WB","group_name":None,"home":f"P:{s['J']}","away":"W:2"},
        {"match_no":7,"stage":"WB","group_name":None,"home":"W:3","away":"W:4"},
        {"match_no":8,"stage":"WB","group_name":None,"home":"W:5","away":"W:6"},
        {"match_no":9,"stage":"WB_FINAL","group_name":None,"home":"W:7","away":"W:8"},
        {"match_no":10,"stage":"LB","group_name":None,"home":"D10:L10H","away":"D10:L10A"},
        {"match_no":11,"stage":"LB","group_name":None,"home":"D10:L11H","away":"D10:L11A"},
        {"match_no":12,"stage":"LB","group_name":None,"home":"D10:L12H","away":"D10:L12A"},
        {"match_no":13,"stage":"LB_BRIDGE","group_name":None,"home":"D10:L13H","away":"D10:L13A"},
        {"match_no":14,"stage":"LB","group_name":None,"home":"D10:L14H","away":"D10:L14A"},
        {"match_no":15,"stage":"LB","group_name":None,"home":"D10:L15H","away":"D10:L15A"},
        {"match_no":16,"stage":"LB","group_name":None,"home":"W:14","away":"W:15"},
        {"match_no":17,"stage":"LB_FINAL","group_name":None,"home":"W:16","away":"L:9"},
        {"match_no":18,"stage":"FINAL","group_name":None,"home":"W:9","away":"W:17"},
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
    if format_key=="swiss8": return schedule_swiss(draw,8,rng)
    if format_key=="groups9_final4": return schedule_groups9_final4(draw,rng)
    if format_key=="groups9_barrage_final3": return schedule_groups9_barrage_final3(draw,rng)
    if format_key=="groups9_top8": return schedule_groups9_top8(draw,rng)
    if format_key=="double9": return schedule_double9(draw,extra)
    if format_key=="groups10_sf": return schedule_groups10_sf(draw,rng)
    if format_key=="swiss10": return schedule_swiss(draw,10,rng)
    if format_key=="double10": return schedule_double10(draw,extra)
    raise ValueError(format_key)

def group_table(group_player_ids: Iterable[str], matches: list[dict], tie_orders: dict[str,int],
                fair_play_points: dict[str,int] | None = None, lot_orders: dict[str,int] | None = None) -> list[dict]:
    """Build a group table with FIFA Night tie-break rules.

    Order: points -> goal difference -> goals scored -> H2H / mini-table ->
    fair play -> persistent lot. ``tie_order`` is only a final technical fallback
    while a group is still unfinished / before a real lot has been created.

    A tied group match that was explicitly sent to a shoot-out keeps the draw
    points and goal totals, but its penalty winner breaks the H2H tie.
    """
    ids=list(group_player_ids)
    fair={str(k):int(v or 0) for k,v in (fair_play_points or {}).items()}
    lot={str(k):int(v or 0) for k,v in (lot_orders or {}).items()}
    stats={pid:{"player_id":pid,"m":0,"w":0,"d":0,"l":0,"gf":0,"ga":0,"gd":0,"pts":0} for pid in ids}
    played=[]
    for m in matches:
        if m.get("home_score") is None or m.get("away_score") is None: continue
        h,a=m.get("home_player_id"),m.get("away_player_id")
        if h not in stats or a not in stats: continue
        hs,ass=int(m["home_score"]),int(m["away_score"])
        stats[h]["m"]+=1; stats[a]["m"]+=1
        stats[h]["gf"]+=hs; stats[h]["ga"]+=ass; stats[a]["gf"]+=ass; stats[a]["ga"]+=hs
        if hs>ass:
            stats[h]["w"]+=1; stats[a]["l"]+=1; stats[h]["pts"]+=3
        elif hs<ass:
            stats[a]["w"]+=1; stats[h]["l"]+=1; stats[a]["pts"]+=3
        else:
            stats[h]["d"]+=1; stats[a]["d"]+=1; stats[h]["pts"]+=1; stats[a]["pts"]+=1
        played.append(m)
    for row in stats.values():
        row["gd"]=row["gf"]-row["ga"]
        row["fair_play"]=int(fair.get(str(row["player_id"]),0))
        row["tie_order"]=int(tie_orders.get(row["player_id"],9999))

    def mini_stats(block_ids: list[str]) -> dict[str,dict]:
        wanted=set(block_ids)
        out={pid:{"pts":0,"gf":0,"ga":0,"gd":0} for pid in block_ids}
        for m in played:
            h,a=m.get("home_player_id"),m.get("away_player_id")
            if h not in wanted or a not in wanted: continue
            hs,aw=int(m["home_score"]),int(m["away_score"])
            out[h]["gf"]+=hs;out[h]["ga"]+=aw;out[a]["gf"]+=aw;out[a]["ga"]+=hs
            if hs>aw:out[h]["pts"]+=3
            elif aw>hs:out[a]["pts"]+=3
            else:out[h]["pts"]+=1;out[a]["pts"]+=1
        for x in out.values():x["gd"]=x["gf"]-x["ga"]
        return out

    def direct_penalty_winner(a: str, b: str) -> str | None:
        # Single round-robin groups have one H2H. Keep this robust if a format ever
        # contains more: the latest played direct meeting is the relevant one.
        direct=[m for m in played if {str(m.get("home_player_id") or ""),str(m.get("away_player_id") or "")}=={str(a),str(b)}]
        if not direct:return None
        direct.sort(key=lambda m:(str(m.get("played_at") or ""),int(m.get("match_no") or 0)))
        m=direct[-1];hs,aw=int(m["home_score"]),int(m["away_score"])
        if hs!=aw:return str(m.get("home_player_id") if hs>aw else m.get("away_player_id"))
        hp,ap=m.get("home_penalties"),m.get("away_penalties")
        if hp is not None and ap is not None and int(hp)!=int(ap):
            return str(m.get("home_player_id") if int(hp)>int(ap) else m.get("away_player_id"))
        return None

    def finish_equal(sub: list[dict]) -> list[dict]:
        if len(sub)<=1:return sub
        # For exactly two players, a special last-group-match shoot-out is a real
        # sporting H2H decider even though the group score remains a draw.
        if len(sub)==2:
            w=direct_penalty_winner(str(sub[0]["player_id"]),str(sub[1]["player_id"]))
            if w:
                return sorted(sub,key=lambda r:0 if str(r["player_id"])==w else 1)
        sub=sorted(sub,key=lambda r:(int(fair.get(str(r["player_id"]),0)),
                                     int(lot.get(str(r["player_id"]),10**9)),
                                     int(tie_orders.get(r["player_id"],9999))))
        return sub

    def resolve_overall_block(block: list[dict]) -> list[dict]:
        if len(block)<=1:return block
        mini=mini_stats([str(r["player_id"]) for r in block])
        ordered=sorted(block,key=lambda r:(mini[str(r["player_id"])]["pts"],
                                           mini[str(r["player_id"])]["gd"],
                                           mini[str(r["player_id"])]["gf"]),reverse=True)
        out=[];i=0
        while i<len(ordered):
            pid=str(ordered[i]["player_id"]);key=(mini[pid]["pts"],mini[pid]["gd"],mini[pid]["gf"]);j=i+1
            while j<len(ordered):
                q=str(ordered[j]["player_id"]);qkey=(mini[q]["pts"],mini[q]["gd"],mini[q]["gf"])
                if qkey!=key:break
                j+=1
            out.extend(finish_equal(ordered[i:j]));i=j
        return out

    rows=list(stats.values());rows.sort(key=lambda r:(r["pts"],r["gd"],r["gf"]),reverse=True)
    final=[];i=0
    while i<len(rows):
        key=(rows[i]["pts"],rows[i]["gd"],rows[i]["gf"]);j=i+1
        while j<len(rows) and (rows[j]["pts"],rows[j]["gd"],rows[j]["gf"])==key:j+=1
        final.extend(resolve_overall_block(rows[i:j]));i=j
    for pos,row in enumerate(final,1):row["position"]=pos
    return final


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

def apply_de_playin_priority(draw: dict, format_key: str, placement_by_player_id: dict[str,int] | None, rng: random.Random, new_player_ids: list[str] | None = None) -> dict:
    """Weighted DE9/DE10 play-in draw from the previous tournament.

    Champion/finalist are more exposed, newcomers less exposed. In DE9 they can never
    meet in the single play-in; in DE10 both may be selected but never face each other.
    """
    if format_key not in ("double9","double10"):
        return draw
    import itertools
    slots=dict(draw.get("slots") or {}); pids=list(slots.values())
    place={str(k):int(v) for k,v in (placement_by_player_id or {}).items() if v}; newcomers={str(x) for x in (new_player_ids or [])}
    base={1:1.45,2:1.35,3:1.10}
    weights={pid:(0.75 if str(pid) in newcomers else base.get(place.get(str(pid)),1.0)) for pid in pids}
    champ=next((pid for pid in pids if place.get(str(pid))==1),None); runner=next((pid for pid in pids if place.get(str(pid))==2),None)
    if format_key=="double9":
        opts=[]
        for a,b in itertools.combinations(pids,2):
            if champ and runner and {str(a),str(b)}=={str(champ),str(runner)}: continue
            opts.append(((a,b),weights[a]*weights[b]))
        pair=_weighted_choice_pairs(opts,rng)
        for target,pid in zip(("A","B"),pair):
            if slots[target]==pid:continue
            src=next(k for k,v in slots.items() if v==pid);slots[target],slots[src]=slots[src],slots[target]
        return {**draw,"slots":slots}
    opts=[]
    for perm in itertools.permutations(pids,4):
        if champ and runner and ({str(perm[0]),str(perm[1])}=={str(champ),str(runner)} or {str(perm[2]),str(perm[3])}=={str(champ),str(runner)}):continue
        w=1.0
        for pid in perm:w*=weights[pid]
        opts.append((perm,w))
    chosen=_weighted_choice_pairs(opts,rng)
    for target,pid in zip(("A","B","C","D"),chosen):
        if slots[target]==pid:continue
        src=next(k for k,v in slots.items() if v==pid);slots[target],slots[src]=slots[src],slots[target]
    return {**draw,"slots":slots}

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


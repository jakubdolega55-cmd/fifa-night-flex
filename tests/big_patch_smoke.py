import os, sys, tempfile, types, traceback
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
WORK=tempfile.mkdtemp(prefix='fifa_big_patch_')
os.chdir(WORK);sys.path.insert(0,str(ROOT));os.environ.pop('DATABASE_URL',None)
try: import streamlit  # noqa
except ModuleNotFoundError:
    st=types.ModuleType('streamlit');st.secrets={};st.cache_resource=lambda *a,**k:(lambda f:f);sys.modules['streamlit']=st
try: import psycopg  # noqa
except ModuleNotFoundError:
    ps=types.ModuleType('psycopg');rows=types.ModuleType('psycopg.rows');rows.dict_row=object();ps.rows=rows;sys.modules['psycopg']=ps;sys.modules['psycopg.rows']=rows

from database import Database
from logic import allowed_teams, apply_de_playin_priority, build_draw
import random

EXPECTED={
    (8,'swiss8'):15,(9,'groups9_final4'):12,(9,'groups9_barrage_final3'):15,(9,'groups9_top8'):16,
    (9,'double9'):16,(10,'groups10_sf'):23,(10,'swiss10'):18,(10,'double10'):18,
}

def drive_setup(db,tid,game='FC27'):
    for z in range(80):
        b=db.setup_bundle(tid);phase=b['tournament']['phase']
        if phase=='team_draw':
            r=db.reveal_next_team(tid)
            if r and r.get('wildcard'):
                choices=db.wildcard_team_suggestions(game)
                # pick first concrete unused WC that validates
                for team in choices:
                    try: db.confirm_wildcard_team(tid,r['player_id'],team);break
                    except ValueError: continue
            if all(bool(p['team_revealed']) for p in db.setup_bundle(tid)['players']):db.start_structure_draw(tid)
        elif phase=='structure_draw':
            db.reveal_structure(tid);db.confirm_structure(tid);return
        elif phase=='active':return
    raise AssertionError('setup loop')

def play_all(db,tid):
    seen_pairs=[]
    for _ in range(120):
        b=db.bundle(tid)
        if b['tournament']['status']=='completed':return b,seen_pairs
        draw=db.big_visible_draw_state(tid)
        if draw:
            db.ack_big_visible_draw(tid,draw['kind']);continue
        ready=[m for m in b['matches'] if m.get('home_score') is None and m.get('home_player_id') and m.get('away_player_id')]
        if not ready:raise AssertionError(f"stuck: {[(m['match_no'],m['stage']) for m in b['matches'] if m.get('home_score') is None]}")
        m=min(ready,key=lambda x:int(x['match_no']))
        if str(m['stage']).startswith('SWISS_'):
            pair=frozenset((m['home_player_id'],m['away_player_id']))
            assert pair not in seen_pairs, f'Swiss rematch at M{m["match_no"]}'
            seen_pairs.append(pair)
        db.save_result(tid,int(m['match_no']),2,0)
    raise AssertionError('play loop')

def main():
    assert allowed_teams(5,'FC27')==['Real Madryt','PSG','Bayern Monachium','FC Barcelona','Arsenal']
    assert sum('Dowolna drużyna' in x for x in allowed_teams(10,'FC27'))==5
    assert sum('Dowolna drużyna' in x for x in allowed_teams(10,'FC26'))==6

    # DE play-in hard constraints with weighted draw.
    ids=[f'p{i}' for i in range(10)];placement={ids[0]:1,ids[1]:2,ids[2]:3}
    for seed in range(100):
        rng=random.Random(seed)
        d9=build_draw(ids[:9],'double9',rng);d9=apply_de_playin_priority(d9,'double9',placement,rng,[])
        assert {d9['slots']['A'],d9['slots']['B']}!={ids[0],ids[1]}
        d10=build_draw(ids,'double10',rng);d10=apply_de_playin_priority(d10,'double10',placement,rng,[])
        assert {d10['slots']['A'],d10['slots']['B']}!={ids[0],ids[1]}
        assert {d10['slots']['C'],d10['slots']['D']}!={ids[0],ids[1]}

    for (n,fmt),expected in EXPECTED.items():
        db=Database();db.init_schema();names=[f'{fmt}_{i+1}' for i in range(n)]
        tid=db.create_tournament(names,n,fmt,allowed_teams(n,'FC27'),True,0,[False]+[True]*(n-1),'FC27')
        assert db.setup_bundle(tid)['tournament']['game_version']=='FC27'
        # FC27: Real is a normal wheel club, never the FC26 helper.
        b=db.setup_bundle(tid)
        assert b['meta']['extra'].get('team_mode','clubs')=='clubs'
        try:
            db.assign_real_helper(tid,b['players'][0]['player_id']);raise AssertionError('FC27 helper Real accepted')
        except ValueError: pass
        drive_setup(db,tid)
        done,_=play_all(db,tid)
        played=sum(m.get('home_score') is not None for m in done['matches'])
        assert played==expected,(fmt,played,expected)
        assert len(done['matches'])==expected,(fmt,len(done['matches']))
        assert done['tournament']['status']=='completed'
        print('PASS',fmt,played)
    print('BIG PATCH BACKEND SMOKE PASS',len(EXPECTED),'formats')

if __name__=='__main__':main()

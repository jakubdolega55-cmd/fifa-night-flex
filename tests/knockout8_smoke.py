import os, sys, tempfile, types
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
WORK=tempfile.mkdtemp(prefix='fifa_ko8_')
os.chdir(WORK);sys.path.insert(0,str(ROOT));os.environ.pop('DATABASE_URL',None)
try: import streamlit  # noqa
except ModuleNotFoundError:
    st=types.ModuleType('streamlit');st.secrets={};st.cache_resource=lambda *a,**k:(lambda f:f);sys.modules['streamlit']=st
try: import psycopg  # noqa
except ModuleNotFoundError:
    ps=types.ModuleType('psycopg');rows=types.ModuleType('psycopg.rows');rows.dict_row=object();ps.rows=rows;sys.modules['psycopg']=ps;sys.modules['psycopg.rows']=rows
from database import Database
from logic import allowed_teams, FORMAT_MATCH_COUNTS, FORMAT_LABELS, structure_match_preview

def setup():
    db=Database();db.init_schema();names=[f'K{i}' for i in range(1,9)]
    tid=db.create_tournament(names,8,'knockout8',allowed_teams(8,'FC27'),True,0,[True]*8,'FC27')
    for _ in range(120):
        b=db.setup_bundle(tid);phase=b['tournament']['phase']
        if phase=='draft_order': db.reveal_draft_order(tid);db.confirm_draft_order(tid)
        elif phase=='team_draft':
            ps=[p for p in db.tournament_players(tid) if not p.get('team_revealed')]
            if ps:
                avail=[x for x in db.available_draft_teams(tid) if x!='🃏 Wild Card'];db.draft_pick(tid,ps[0]['player_id'],avail[0])
        elif phase=='team_draw':
            r=db.reveal_next_team(tid)
            if r and r.get('wildcard'):
                for team in db.wildcard_team_suggestions('FC27'):
                    try:db.confirm_wildcard_team(tid,r['player_id'],team);break
                    except ValueError:pass
            if all(p['team_revealed'] for p in db.setup_bundle(tid)['players']):db.start_structure_draw(tid)
        elif phase=='structure_draw':
            prev=structure_match_preview('knockout8',b['meta']['draw']);assert len(prev)==4,prev
            db.reveal_structure(tid);db.confirm_structure(tid);return db,tid
        elif phase=='active':return db,tid
    raise AssertionError('setup loop')

def match(db,tid,no):return next(x for x in db.bundle(tid)['matches'] if int(x['match_no'])==no)
def play(db,tid,no,hs,ass):
    m=match(db,tid,no);assert m.get('home_player_id') and m.get('away_player_id'),(no,m);db.save_result(tid,no,hs,ass)

def names_by_match(db,tid,no):
    m=match(db,tid,no);return m.get('home_name'),m.get('away_name')

def run_tied_third():
    db,tid=setup();assert FORMAT_MATCH_COUNTS['knockout8']=='7 meczów';assert 'KO' in FORMAT_LABELS['knockout8']
    assert len(db.bundle(tid)['matches'])==7
    for no in (1,2,3,4):play(db,tid,no,2,0)
    play(db,tid,5,1,0);play(db,tid,6,1,0);play(db,tid,7,2,1)
    assert db.current_tournament()['status']=='completed'
    s=db.tournament_summary(tid);thirds=s.get('third_places') or []
    assert s.get('third_place_tied') is True,s
    assert len(thirds)==2,s
    assert s.get('fourth_place') is None,s
    assert all(int(x.get('gd') or 0)==1 and int(x.get('gf') or 0)==2 for x in thirds),thirds
    print('PASS KO8 tied 3rd place')

def run_ranked_third():
    db,tid=setup()
    play(db,tid,1,2,0);play(db,tid,2,3,0);play(db,tid,3,2,0);play(db,tid,4,2,0)
    play(db,tid,5,1,0);play(db,tid,6,1,0);play(db,tid,7,1,0)
    s=db.tournament_summary(tid)
    assert s.get('third_place_tied') is False,s
    assert len(s.get('third_places') or [])==1,s
    assert s.get('third_place') and s.get('fourth_place'),s
    assert int(s['third_place']['gd'])>int(s['fourth_place']['gd']),(s['third_place'],s['fourth_place'])
    print('PASS KO8 ranked 3rd place')

if __name__=='__main__':
    run_tied_third();run_ranked_third();print('KO8 SMOKE PASS')

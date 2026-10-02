import os, sys, tempfile, types
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
WORK=tempfile.mkdtemp(prefix='fifa_de_manual_')
os.chdir(WORK);sys.path.insert(0,str(ROOT));os.environ.pop('DATABASE_URL',None)
try: import streamlit  # noqa
except ModuleNotFoundError:
    st=types.ModuleType('streamlit');st.secrets={};st.cache_resource=lambda *a,**k:(lambda f:f);sys.modules['streamlit']=st
try: import psycopg  # noqa
except ModuleNotFoundError:
    ps=types.ModuleType('psycopg');rows=types.ModuleType('psycopg.rows');rows.dict_row=object();ps.rows=rows;sys.modules['psycopg']=ps;sys.modules['psycopg.rows']=rows
from database import Database
from logic import allowed_teams

def setup(n,fmt):
    db=Database();db.init_schema();names=[f'{fmt}_{i+1}' for i in range(n)]
    tid=db.create_tournament(names,n,fmt,allowed_teams(n,'FC27'),True,0,[True]*n,'FC27')
    for _ in range(100):
        b=db.setup_bundle(tid);phase=b['tournament']['phase']
        if phase=='draft_order': db.reveal_draft_order(tid);db.confirm_draft_order(tid)
        elif phase=='team_draft':
            players=[p for p in db.tournament_players(tid) if not p.get('team_revealed')]
            if players:
                avail=[x for x in db.available_draft_teams(tid) if x!='🃏 Wild Card'];db.draft_pick(tid,players[0]['player_id'],avail[0])
        elif phase=='team_draw':
            r=db.reveal_next_team(tid)
            if r and r.get('wildcard'):
                for team in db.wildcard_team_suggestions('FC27'):
                    try: db.confirm_wildcard_team(tid,r['player_id'],team);break
                    except ValueError: pass
            if all(p['team_revealed'] for p in db.setup_bundle(tid)['players']): db.start_structure_draw(tid)
        elif phase=='structure_draw': db.reveal_structure(tid);db.confirm_structure(tid);return db,tid
        elif phase=='active': return db,tid
    raise AssertionError('setup loop')

def match(db,tid,no): return next(x for x in db.bundle(tid)['matches'] if int(x['match_no'])==no)
def play(db,tid,no):
    m=match(db,tid,no);assert m.get('home_player_id') and m.get('away_player_id'),(no,m);db.save_result(tid,no,2,0)

def main():
    db,tid=setup(6,'double6')
    for no in (1,2,3,4): play(db,tid,no)
    ev=db.big_visible_draw_state(tid)
    assert ev and ev.get('kind')=='double6_lb_cross',ev
    assert ev.get('selected') is False,ev
    try:
        db.ack_big_visible_draw(tid,ev['kind'])
        raise AssertionError('ack unexpectedly succeeded before reveal')
    except ValueError as e:
        assert 'Najpierw uruchom losowanie' in str(e),e
    shown=db.reveal_big_visible_draw(tid,ev['kind'])
    assert shown.get('selected') is True,shown
    ev2=db.big_visible_draw_state(tid);assert ev2 and ev2.get('selected') is True,ev2
    db.ack_big_visible_draw(tid,ev2['kind'])
    assert db.big_visible_draw_state(tid) is None
    print('DE manual draw trigger smoke: PASS')
if __name__=='__main__': main()

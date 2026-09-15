import os, sys, tempfile, types
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
WORK=tempfile.mkdtemp(prefix='fifa_de456_')
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
        if phase=='draft_order':
            db.reveal_draft_order(tid);db.confirm_draft_order(tid)
        elif phase=='team_draft':
            players=[p for p in db.tournament_players(tid) if not p.get('team_revealed')]
            if players:
                avail=[x for x in db.available_draft_teams(tid) if x!='🃏 Wild Card']
                assert avail
                db.draft_pick(tid,players[0]['player_id'],avail[0])
        elif phase=='team_draw':
            r=db.reveal_next_team(tid)
            if r and r.get('wildcard'):
                for team in db.wildcard_team_suggestions('FC27'):
                    try:db.confirm_wildcard_team(tid,r['player_id'],team);break
                    except ValueError:pass
            if all(p['team_revealed'] for p in db.setup_bundle(tid)['players']):db.start_structure_draw(tid)
        elif phase=='structure_draw':
            db.reveal_structure(tid);db.confirm_structure(tid);return db,tid
        elif phase=='active':return db,tid
    raise AssertionError('setup loop')


def match(db,tid,no):
    return next(x for x in db.bundle(tid)['matches'] if int(x['match_no'])==no)


def play(db,tid,no,hs=2,ass=0):
    m=match(db,tid,no);assert m.get('home_player_id') and m.get('away_player_id'),(no,m)
    db.save_result(tid,no,hs,ass)


def test_de4_no_fake_draw():
    db,tid=setup(4,'double4')
    assert db.big_visible_draw_state(tid) is None
    play(db,tid,1);play(db,tid,2)
    assert db.big_visible_draw_state(tid) is None
    m3,m4=match(db,tid,3),match(db,tid,4)
    assert m3.get('home_player_id') and m3.get('away_player_id')
    assert m4.get('home_player_id') and m4.get('away_player_id')
    print('PASS DE4 stays deterministic: no fake mid-draw')


def test_de5_early_symbolic_draw():
    db,tid=setup(5,'double5')
    state=db.double5_draw_state(tid)
    assert state and not state.get('selected') and not state.get('ack'),state
    assert [c['name'] for c in state['candidates']]==['Zwycięzca M1','Zwycięzca M2'],state
    chosen=db.reveal_double5_opponent(tid)
    assert int(chosen['match_no']) in (1,2),chosen
    assert chosen['name']==f"Zwycięzca M{int(chosen['match_no'])}",chosen
    db.ack_double5_draw(tid)
    picked=int(chosen['match_no']);other=2 if picked==1 else 1
    play(db,tid,picked)
    assert match(db,tid,other).get('home_score') is None
    m3=match(db,tid,3)
    assert m3.get('home_player_id') and m3.get('away_player_id'),m3
    first_pair=(m3.get('home_player_id'),m3.get('away_player_id'))
    # Undo keeps the already revealed W1/W2 route; it only waits for that source again.
    undone=db.undo_last_result(tid);assert undone==picked,undone
    assert not (match(db,tid,3).get('home_player_id') and match(db,tid,3).get('away_player_id'))
    state2=db.double5_draw_state(tid);assert state2 and state2.get('ack') and int((state2.get('selected') or {}).get('match_no'))==picked,state2
    play(db,tid,picked)
    m3b=match(db,tid,3);assert (m3b.get('home_player_id'),m3b.get('away_player_id'))==first_pair,(first_pair,m3b)
    print('PASS DE5 early W-source survives Undo without reroll')


def test_de6_early_lb_cross():
    db,tid=setup(6,'double6')
    play(db,tid,1);play(db,tid,2)
    play(db,tid,3);play(db,tid,4)
    assert match(db,tid,5).get('home_score') is None
    ev=db.big_visible_draw_state(tid)
    assert ev and ev.get('kind')=='double6_lb_cross',ev
    assert int(ev.get('candidate_count') or 0)==2,ev
    assert len(ev.get('pairs') or [])==2,ev
    names=[x for p in ev['pairs'] for x in (p.get('home_name'),p.get('away_name'))]
    assert 'Zwycięzca M5' in names and 'Zwycięzca M6' in names,names
    db.ack_big_visible_draw(tid,ev['kind'])
    assert not (match(db,tid,6).get('home_player_id') and match(db,tid,6).get('away_player_id'))
    play(db,tid,5)
    m6=match(db,tid,6)
    assert m6.get('home_player_id') and m6.get('away_player_id'),m6
    first_pair=(m6.get('home_player_id'),m6.get('away_player_id'))
    src_before=dict((db.bundle(tid)['meta'].get('extra') or {}).get('big_sources') or {})
    undone=db.undo_last_result(tid);assert undone==5,undone
    assert not (match(db,tid,6).get('home_player_id') and match(db,tid,6).get('away_player_id'))
    play(db,tid,5)
    m6b=match(db,tid,6);assert (m6b.get('home_player_id'),m6b.get('away_player_id'))==first_pair,(first_pair,m6b)
    src_after=(db.bundle(tid)['meta'].get('extra') or {}).get('big_sources') or {}
    assert src_after==src_before,(src_before,src_after)
    print('PASS DE6 early LB cross survives Undo without reroll')


def main():
    test_de4_no_fake_draw();test_de5_early_symbolic_draw();test_de6_early_lb_cross()
    print('ALL PASS DE4/5/6 draw audit')

if __name__=='__main__':main()

import os, sys, tempfile, types
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
WORK=tempfile.mkdtemp(prefix='fifa_draw_policy_')
os.chdir(WORK);sys.path.insert(0,str(ROOT));os.environ.pop('DATABASE_URL',None)
try: import streamlit  # noqa
except ModuleNotFoundError:
    st=types.ModuleType('streamlit');st.secrets={};st.cache_resource=lambda *a,**k:(lambda f:f);sys.modules['streamlit']=st
try: import psycopg  # noqa
except ModuleNotFoundError:
    ps=types.ModuleType('psycopg');rows=types.ModuleType('psycopg.rows');rows.dict_row=object();ps.rows=rows;sys.modules['psycopg']=ps;sys.modules['psycopg.rows']=rows

from database import Database
from logic import allowed_teams


def setup(db, n, fmt):
    db.init_schema(); names=[f'{fmt}_{i+1}' for i in range(n)]
    tid=db.create_tournament(names,n,fmt,allowed_teams(n,'FC27'),True,0,[True]*n,'FC27')
    for _ in range(100):
        b=db.setup_bundle(tid); phase=b['tournament']['phase']
        if phase=='team_draw':
            r=db.reveal_next_team(tid)
            if r and r.get('wildcard'):
                for team in db.wildcard_team_suggestions('FC27'):
                    try: db.confirm_wildcard_team(tid,r['player_id'],team); break
                    except ValueError: pass
            if all(p['team_revealed'] for p in db.setup_bundle(tid)['players']): db.start_structure_draw(tid)
        elif phase=='structure_draw': db.reveal_structure(tid);db.confirm_structure(tid);return tid
        elif phase=='active': return tid
    raise AssertionError('setup loop')


def play_stage_prefix(db, tid, end_no):
    while True:
        b=db.bundle(tid)
        pending=[m for m in b['matches'] if int(m['match_no'])<=end_no and m.get('home_score') is None]
        if not pending:return
        # acknowledge only true dynamic draws if they happen before target prefix
        ev=db.big_visible_draw_state(tid)
        if ev: db.ack_big_visible_draw(tid,ev['kind']);continue
        m=db.current_match_from(b['matches'],b['meta'].get('extra') or {})
        if not m or int(m['match_no'])>end_no:
            ready=[x for x in pending if x.get('home_player_id') and x.get('away_player_id')]
            assert ready,(end_no,[(x['match_no'],x['stage'],x.get('home_name'),x.get('away_name')) for x in pending])
            m=min(ready,key=lambda x:int(x['match_no']))
        db.save_result(tid,int(m['match_no']),2,0)


def fixed_group_cross(fmt,n,group_end):
    db=Database();tid=setup(db,n,fmt);play_stage_prefix(db,tid,group_end)
    state=db.group_playoff_reveal_state(tid)
    assert state and state.get('is_random_draw') is False,state
    assert db.big_visible_draw_state(tid) is None
    with db.connect() as conn:
        ta=db._table_from_conn(conn,tid,'A');tb=db._table_from_conn(conn,tid,'B')
    expected={frozenset((ta[0]['name'],tb[1]['name'])),frozenset((tb[0]['name'],ta[1]['name']))}
    got={frozenset((p['home_name'],p['away_name'])) for p in state['pairs']}
    assert got==expected,(fmt,expected,got)
    print('PASS fixed cross stays deterministic',fmt,'1A-2B / 1B-2A')


def groups10_cross():
    db=Database();tid=setup(db,10,'groups10_sf');play_stage_prefix(db,tid,20)
    b=db.bundle(tid);mm={int(m['match_no']):m for m in b['matches']}
    with db.connect() as conn:
        ta=db._table_from_conn(conn,tid,'A');tb=db._table_from_conn(conn,tid,'B')
    assert {mm[21]['home_name'],mm[21]['away_name']}=={ta[0]['name'],tb[1]['name']}
    assert {mm[22]['home_name'],mm[22]['away_name']}=={tb[0]['name'],ta[1]['name']}
    state=db.group_playoff_reveal_state(tid)
    assert state and state.get('format_key')=='groups10_sf' and state.get('is_random_draw') is False,state
    assert [int(p['match_no']) for p in state.get('pairs',[])]==[21,22],state
    assert db.big_visible_draw_state(tid) is None
    db.ack_group_playoffs(tid)
    assert db.group_playoff_reveal_state(tid) is None
    print('PASS groups10 fixed semifinals stay 1A-2B / 1B-2A and use deterministic reveal')


def find_late_de_draw(fmt,n,first_round_end,target_done,reveal_kind):
    # Depending on actual results, the immediate-rematch rule can leave either one
    # legal crossing (no draw) or 2 equally legal crossings (visible draw). Try a
    # few genuine brackets and require that the latter is observable.
    for attempt in range(18):
        db=Database();tid=setup(db,n,fmt)
        play_stage_prefix(db,tid,first_round_end)
        if fmt=='double7':
            st=db.double7_combined_draw_state(tid)
            if st and not st.get('selected'): db.reveal_double7_combined_draw(tid)
            db.ack_double7_combined_draw(tid)
        else:
            st=db.double_wb_draw_state(tid)
            if st and not st.get('selected'): db.reveal_double_wb_draw(tid)
            db.ack_double_wb_draw(tid)
        # Play until the inputs of the late cross are complete; do not auto-ack that cross.
        for _ in range(40):
            ev=db.big_visible_draw_state(tid)
            if ev:
                if ev.get('kind')==reveal_kind:
                    assert int(ev.get('candidate_count') or 0)>=2,ev
                    assert ev.get('is_random_draw') is True,ev
                    assert len(ev.get('pairs') or [])==2,ev
                    print('PASS visible late DE draw',fmt,reveal_kind,'candidates',ev['candidate_count'])
                    return
                db.ack_big_visible_draw(tid,ev['kind']);continue
            b=db.bundle(tid);mm={int(m['match_no']):m for m in b['matches']}
            if all(mm[i].get('home_score') is not None for i in target_done): break
            m=db.current_match_from(b['matches'],b['meta'].get('extra') or {})
            assert m,(fmt,attempt,target_done)
            db.save_result(tid,int(m['match_no']),2,0)
    raise AssertionError(f'No observable {reveal_kind} in repeated real brackets')



def groups9_policy():
    # 9B has exactly two cross-group derangements, so this is a genuine draw.
    db=Database();tid=setup(db,9,'groups9_barrage_final3');play_stage_prefix(db,tid,9)
    ev=db.big_visible_draw_state(tid)
    assert ev and ev.get('kind')=='groups9_barrage' and int(ev.get('candidate_count') or 0)==2 and ev.get('is_random_draw') is True,ev
    assert len(ev.get('pairs') or [])==3,ev
    print('PASS groups9 barrage uses real 2-variant visible draw')
    db.ack_big_visible_draw(tid,ev['kind'])
    # The three barrage winners have different rest (M10/M11/M12), so the longest-rested
    # finalist deterministically takes the M14+M15 role. No fake draw should appear.
    for no in (10,11,12):
        b=db.bundle(tid);m=next(x for x in b['matches'] if int(x['match_no'])==no);assert m.get('home_player_id') and m.get('away_player_id');db.save_result(tid,no,2,0)
    assert db.big_visible_draw_state(tid) is None
    b=db.bundle(tid);mm={int(x['match_no']):x for x in b['matches']};w10=mm[10]['winner_player_id']
    assert w10 not in {mm[13]['home_player_id'],mm[13]['away_player_id']},(w10,mm[13])
    print('PASS Final Three rest rule is deterministic when one finalist waited longest')

    # 9C Pot1-vs-Pot2 has several equally legal minimum-conflict assignments.
    db=Database();tid=setup(db,9,'groups9_top8');play_stage_prefix(db,tid,9)
    ev=db.big_visible_draw_state(tid)
    assert ev and ev.get('kind')=='groups9_top8_qf' and int(ev.get('candidate_count') or 0)>=2 and ev.get('is_random_draw') is True,ev
    assert len(ev.get('pairs') or [])==4,ev
    print('PASS groups9 TOP8 uses visible draw among equivalent minimum-conflict QF variants')

    # 9A may have two legal cross-group pairings, but rest/ordering is allowed to leave
    # one uniquely best solution. In that case there must be no fake random animation.
    db=Database();tid=setup(db,9,'groups9_final4');play_stage_prefix(db,tid,9)
    ev=db.big_visible_draw_state(tid)
    if ev:
        assert ev.get('kind')=='groups9_final4_sf' and int(ev.get('candidate_count') or 0)>=2 and ev.get('is_random_draw') is True,ev
        db.ack_big_visible_draw(tid,ev['kind'])
    b=db.bundle(tid);mm={int(x['match_no']):x for x in b['matches']}
    groups={p['player_id']:p.get('group_name') for p in b['players']}
    for no in (10,11):
        assert groups[mm[no]['home_player_id']]!=groups[mm[no]['away_player_id']],(no,mm[no],groups)
    print('PASS groups9 Final Four avoids same-group rematch and never fakes a draw')



def early_de_cross_draws():
    # DE7: immediately after the combined R1 reveal is accepted, M7/M8 routing
    # is drawn with L4/L5/W6 placeholders. M4-M6 are still unplayed.
    db=Database();tid=setup(db,7,'double7');play_stage_prefix(db,tid,3)
    st=db.double7_combined_draw_state(tid)
    if st and not st.get('selected'): db.reveal_double7_combined_draw(tid)
    db.ack_double7_combined_draw(tid)
    b=db.bundle(tid);mm={int(x['match_no']):x for x in b['matches']}
    assert all(mm[i].get('home_score') is None for i in (4,5,6)),[(i,mm[i].get('home_score')) for i in (4,5,6)]
    ev=db.big_visible_draw_state(tid)
    assert ev and ev.get('kind')=='double7_lb_cross' and int(ev.get('candidate_count') or 0)==2,ev
    names=[x for p in ev.get('pairs') or [] for x in (p.get('home_name'),p.get('away_name'))]
    assert 'Zwycięzca M6' in names and any(str(x).startswith('Przegrany M4') or str(x).startswith('Przegrany M5') for x in names),names
    print('PASS DE7 LB cross is visibly drawn early with symbolic sources')

    # DE8: after the WB-SF draw is accepted, M9/M10 routing is already known
    # as W7/W8 crossed with L5/L6, before any of M5-M8 is played.
    db=Database();tid=setup(db,8,'double8');play_stage_prefix(db,tid,4)
    st=db.double_wb_draw_state(tid)
    if st and not st.get('selected'): db.reveal_double_wb_draw(tid)
    db.ack_double_wb_draw(tid)
    b=db.bundle(tid);mm={int(x['match_no']):x for x in b['matches']}
    assert all(mm[i].get('home_score') is None for i in (5,6,7,8)),[(i,mm[i].get('home_score')) for i in (5,6,7,8)]
    ev=db.big_visible_draw_state(tid)
    assert ev and ev.get('kind')=='double8_lb_cross' and int(ev.get('candidate_count') or 0)==2,ev
    names=[x for p in ev.get('pairs') or [] for x in (p.get('home_name'),p.get('away_name'))]
    assert 'Zwycięzca M7' in names and 'Zwycięzca M8' in names
    assert any(str(x)=='Przegrany M5' for x in names) and any(str(x)=='Przegrany M6' for x in names),names
    print('PASS DE8 LB cross is visibly drawn early with symbolic sources')

def main():
    fixed_group_cross('groups6',6,6)
    fixed_group_cross('groups7_sf',7,9)
    fixed_group_cross('groups8_sf',8,12)
    groups10_cross()
    groups9_policy()
    early_de_cross_draws()
    print('VISIBLE DRAW POLICY SMOKE PASS')

if __name__=='__main__': main()

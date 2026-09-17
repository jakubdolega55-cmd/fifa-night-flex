import os, sys, tempfile, types
from pathlib import Path
from collections import defaultdict

ROOT=Path(__file__).resolve().parents[1]
WORK=tempfile.mkdtemp(prefix='fifa_swiss_')
os.chdir(WORK);sys.path.insert(0,str(ROOT));os.environ.pop('DATABASE_URL',None)
try: import streamlit  # noqa
except ModuleNotFoundError:
    st=types.ModuleType('streamlit');st.secrets={};st.cache_resource=lambda *a,**k:(lambda f:f);sys.modules['streamlit']=st
try: import psycopg  # noqa
except ModuleNotFoundError:
    ps=types.ModuleType('psycopg');rows=types.ModuleType('psycopg.rows');rows.dict_row=object();ps.rows=rows;sys.modules['psycopg']=ps;sys.modules['psycopg.rows']=rows

from database import Database
from logic import allowed_teams


def drive_setup(db,tid,game='FC27'):
    for _ in range(100):
        b=db.setup_bundle(tid); phase=b['tournament']['phase']
        if phase=='team_draw':
            r=db.reveal_next_team(tid)
            if r and r.get('wildcard'):
                for team in db.wildcard_team_suggestions(game):
                    try: db.confirm_wildcard_team(tid,r['player_id'],team);break
                    except ValueError: continue
            if all(bool(p['team_revealed']) for p in db.setup_bundle(tid)['players']): db.start_structure_draw(tid)
        elif phase=='structure_draw':
            db.reveal_structure(tid);db.confirm_structure(tid);return
        elif phase=='active': return
    raise AssertionError('setup loop')


def ack_draw(db,tid):
    draw=db.big_visible_draw_state(tid)
    if draw: db.ack_big_visible_draw(tid,draw['kind'])


def swiss_rows(db,tid):
    return db.standings(tid)['S']


def run_one(n,fmt):
    db=Database();db.init_schema();names=[f'{fmt}_{i+1}' for i in range(n)]
    tid=db.create_tournament(names,n,fmt,allowed_teams(n,'FC27'),True,0,[True]*n,'FC27')
    drive_setup(db,tid)
    per=n//2

    # R2 must stay locked until the whole R1 is finished.
    start=db.bundle(tid)
    assert all(m.get('home_player_id') and m.get('away_player_id') for m in start['matches'][:per])
    assert all(not m.get('home_player_id') and not m.get('away_player_id') for m in start['matches'][per:2*per])

    r1_pairs=[]
    for no in range(1,per+1):
        m=next(x for x in db.bundle(tid)['matches'] if int(x['match_no'])==no)
        r1_pairs.append(frozenset((m['home_player_id'],m['away_player_id'])))
        db.save_result(tid,no,2,0)
        if no<per:
            nxt=db.bundle(tid)['matches'][per:2*per]
            assert all(not x.get('home_player_id') for x in nxt), 'R2 unlocked before R1 closed'

    last_r1=set(r1_pairs[-1])
    pending=db.big_visible_draw_state(tid)
    assert pending and pending.get('kind')==f'{fmt}_round_2', (fmt,pending)
    b=db.bundle(tid); locked_r2=b['matches'][per:2*per]
    assert all(not m.get('home_player_id') and not m.get('away_player_id') for m in locked_r2), 'R2 must wait for manual ACK'
    assert db.current_match_from(b['matches'],b['meta'].get('extra') or {}) is None, 'Swiss must pause between rounds'
    ack_draw(db,tid)
    b=db.bundle(tid); r2=b['matches'][per:2*per]
    assert all(m.get('home_player_id') and m.get('away_player_id') for m in r2)
    r2_pairs=[frozenset((m['home_player_id'],m['away_player_id'])) for m in r2]
    assert not any(p in r1_pairs for p in r2_pairs), 'R2 rematch'

    # Score groups dominate the soft global-ranking factor.
    pts={r['player_id']:r['pts'] for r in swiss_rows(db,tid)}
    pdiff=sum(abs(pts[m['home_player_id']]-pts[m['away_player_id']]) for m in r2)
    assert pdiff==(0 if n==8 else 3),(fmt,'R2 score-group penalty',pdiff)

    # Rest ordering: nobody from the final R1 game should be placed into the first
    # R2 match when another selected pair can go first.
    first_r2={r2[0]['home_player_id'],r2[0]['away_player_id']}
    if any(not (set(p)&last_r1) for p in r2_pairs):
        assert not (first_r2 & last_r1),(fmt,'back-to-back risk',last_r1,first_r2)

    all_pairs=list(r1_pairs)
    for m in r2:
        all_pairs.append(frozenset((m['home_player_id'],m['away_player_id'])))
        db.save_result(tid,int(m['match_no']), 1 if int(m['match_no'])%2 else 3, 0)

    pending=db.big_visible_draw_state(tid)
    assert pending and pending.get('kind')==f'{fmt}_round_3', (fmt,pending)
    b=db.bundle(tid); locked_r3=b['matches'][2*per:3*per]
    assert all(not m.get('home_player_id') and not m.get('away_player_id') for m in locked_r3), 'R3 must wait for manual ACK'
    assert db.current_match_from(b['matches'],b['meta'].get('extra') or {}) is None, 'Swiss must pause between rounds'
    ack_draw(db,tid)
    b=db.bundle(tid); r3=b['matches'][2*per:3*per]
    assert all(m.get('home_player_id') and m.get('away_player_id') for m in r3)
    r3_pairs=[frozenset((m['home_player_id'],m['away_player_id'])) for m in r3]
    assert not any(p in all_pairs for p in r3_pairs), 'R3 rematch'
    for m in r3: db.save_result(tid,int(m['match_no']),2,1)

    # Buchholz independently recomputed from the three Swiss rounds.
    rows=swiss_rows(db,tid); row_by={r['player_id']:r for r in rows}
    swiss=[m for m in db.bundle(tid)['matches'] if str(m['stage']).startswith('SWISS_')]
    opp=defaultdict(list)
    for m in swiss:
        h,a=m['home_player_id'],m['away_player_id'];opp[h].append(a);opp[a].append(h)
    for pid,r in row_by.items():
        expected=sum(row_by[o]['pts'] for o in opp[pid])
        assert r['buchholz']==expected,(fmt,pid,r['buchholz'],expected)

    # TOP4 is fixed #1-#4 and #2-#3 only after all 3 rounds are complete.
    ack_draw(db,tid)
    b=db.bundle(tid); sf=b['matches'][3*per:3*per+2]; top=[r['player_id'] for r in rows[:4]]
    got={frozenset((m['home_player_id'],m['away_player_id'])) for m in sf}
    expected={frozenset((top[0],top[3])),frozenset((top[1],top[2]))}
    assert got==expected,(fmt,got,expected)

    # No separate bronze match: both semifinal losers must still occupy 3rd/4th
    # and must never fall below a player eliminated after the Swiss phase.
    for m in sf: db.save_result(tid,int(m['match_no']),2,0)
    b=db.bundle(tid); final=b['matches'][3*per+2]
    assert final.get('home_player_id') and final.get('away_player_id'),(fmt,final)
    db.save_result(tid,int(final['match_no']),2,1)
    summary=db.tournament_summary(tid)
    loser_names={m['away_name'] for m in sf}
    podium_losers={summary.get('third_place',{}).get('name'),summary.get('fourth_place',{}).get('name')}
    assert podium_losers==loser_names,(fmt,podium_losers,loser_names,summary)
    print('PASS',fmt,'no-rematch + score-groups + Buchholz + rest-order + TOP4 + 3rd/4th')


def main():
    run_one(8,'swiss8')
    run_one(10,'swiss10')
    print('SWISS SMOKE PASS 2/2')

if __name__=='__main__': main()

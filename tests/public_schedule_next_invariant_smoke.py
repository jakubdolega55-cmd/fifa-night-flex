import os,sys,tempfile,types
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
WORK=tempfile.mkdtemp(prefix='fifa_public_schedule_');os.chdir(WORK);sys.path.insert(0,str(ROOT));os.environ.pop('DATABASE_URL',None)
try: import streamlit  # noqa
except ModuleNotFoundError:
    st=types.ModuleType('streamlit');st.secrets={};st.cache_resource=lambda *a,**k:(lambda f:f);sys.modules['streamlit']=st
try: import psycopg  # noqa
except ModuleNotFoundError:
    ps=types.ModuleType('psycopg');rows=types.ModuleType('psycopg.rows');rows.dict_row=object();ps.rows=rows;sys.modules['psycopg']=ps;sys.modules['psycopg.rows']=rows
from database import Database
from logic import allowed_teams

def setup(db,tid):
    for _ in range(120):
        b=db.setup_bundle(tid);phase=b['tournament']['phase']
        if phase=='team_draw':
            r=db.reveal_next_team(tid)
            if r and r.get('wildcard'):
                for team in db.wildcard_team_suggestions('FC27'):
                    try:db.confirm_wildcard_team(tid,r['player_id'],team);break
                    except ValueError:continue
            if all(bool(p['team_revealed']) for p in db.setup_bundle(tid)['players']):db.start_structure_draw(tid)
        elif phase=='structure_draw':db.reveal_structure(tid);db.confirm_structure(tid);return
        elif phase=='active':return
    raise AssertionError('setup loop')

def run(n,fmt):
    db=Database();db.init_schema();tid=db.create_tournament([f'{fmt}_{i+1}' for i in range(n)],n,fmt,allowed_teams(n,'FC27'),True,0,[True]*n,'FC27');setup(db,tid)
    steps=0
    while steps<100:
        b=db.bundle(tid)
        if b['tournament']['status']=='completed':break
        ev=db.big_visible_draw_state(tid)
        if ev:db.ack_big_visible_draw(tid,ev['kind']);continue
        ms=b['matches'];extra=b['meta']['extra'];cur=db.current_match_from(ms,extra);assert cur,(fmt,'missing current')
        sched=db.live_schedule_from(ms,extra);row=next(x for x in sched if int(x['match_no'])==int(cur['match_no']))
        done=sum(1 for m in ms if m.get('home_score') is not None or str(m.get('match_status') or '')=='skipped')
        assert int(row['display_match_no'])==done+1,(fmt,'public current number',cur['match_no'],row['display_match_no'],done+1)
        forecast=db.visible_next_match_from(ms,int(cur['match_no']),extra)
        db.save_result(tid,int(cur['match_no']),2,0)
        while True:
            ev=db.big_visible_draw_state(tid)
            if not ev:break
            db.ack_big_visible_draw(tid,ev['kind'])
        b2=db.bundle(tid)
        if b2['tournament']['status']!='completed' and forecast is not None:
            actual=db.current_match_from(b2['matches'],b2['meta']['extra'])
            fno=int(forecast['match_no']);fm=next((x for x in b2['matches'] if int(x['match_no'])==fno),None)
            # Only enforce a forecast that is still a concrete playable match after the result.
            if fm and fm.get('home_player_id') and fm.get('away_player_id') and fm.get('home_score') is None:
                assert int(actual['match_no'])==fno,(fmt,'NEXT mismatch',cur['match_no'],fno,actual['match_no'])
        steps+=1
    assert steps>0
    print('PASS',fmt,steps)

def main():
    for args in ((6,'groups6'),(8,'swiss8'),(9,'double9'),(10,'double10')):run(*args)
    print('PUBLIC SCHEDULE/NEXT INVARIANT SMOKE PASS')
if __name__=='__main__':main()

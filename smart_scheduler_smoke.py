import os,sys,tempfile,types
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
os.chdir(tempfile.mkdtemp(prefix='fifa_sched_'));sys.path.insert(0,str(ROOT));os.environ.pop('DATABASE_URL',None)
try: import streamlit  # noqa
except ModuleNotFoundError:
    st=types.ModuleType('streamlit');st.secrets={};st.cache_resource=lambda *a,**k:(lambda f:f);sys.modules['streamlit']=st
try: import psycopg  # noqa
except ModuleNotFoundError:
    ps=types.ModuleType('psycopg');rows=types.ModuleType('psycopg.rows');rows.dict_row=object();ps.rows=rows;sys.modules['psycopg']=ps;sys.modules['psycopg.rows']=rows
from database import Database

def m(no,h,a,score=None,ts=None):
    return {'match_no':no,'home_player_id':h,'away_player_id':a,'home_score':score,'away_score':0 if score is not None else None,'match_status':'played' if score is not None else 'pending','played_at':ts}

def main():
    db=Database()
    extra={'smart_scheduler':True,'match_play_order':[10,11],'scheduler_tiebreak':{'10':.2,'11':.8}}
    # Back-to-back is the first hard scheduler concern.
    matches=[m(1,'a','b',2,'2026-01-01T10:00:00'),m(10,'a','c'),m(11,'d','e')]
    assert db.current_match_from(matches,extra)['match_no']==11
    print('PASS scheduler avoids immediate back-to-back when another ready match exists')

    # Long waiting player wins once both candidates are free from back-to-back.
    matches=[
      m(1,'a','x',2,'2026-01-01T10:00:00'),
      m(2,'d','y',2,'2026-01-01T10:01:00'),
      m(3,'e','z',2,'2026-01-01T10:02:00'),
      m(4,'q','r',2,'2026-01-01T10:03:00'),
      m(10,'a','c'),m(11,'d','e')]
    assert db.current_match_from(matches,extra)['match_no']==10
    print('PASS scheduler pulls in longest-waiting player')

    # Static/precomputed order still decides a complete fairness tie.
    tied=[m(10,'a','b'),m(11,'c','d')]
    assert db.current_match_from(tied,extra)['match_no']==10
    print('PASS scheduler keeps precomputed opening order on equal fairness')

    # Manual one-slot defer must beat automatic fairness exactly once while target is ready.
    forced={**extra,'manual_next_match_no':11}
    assert db.current_match_from(tied,forced)['match_no']==11
    print('PASS manual defer next-match override is respected')

    # Smart scheduler never changes participants, only picks one existing ready match.
    chosen=db.current_match_from(matches,extra)
    original=next(x for x in matches if x['match_no']==chosen['match_no'])
    assert (chosen['home_player_id'],chosen['away_player_id'])==(original['home_player_id'],original['away_player_id'])
    print('PASS scheduler never rewrites pairings')
    print('SMART SCHEDULER SMOKE PASS')

if __name__=='__main__':main()

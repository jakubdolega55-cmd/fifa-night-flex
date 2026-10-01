import os,sys,tempfile,types
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
os.chdir(tempfile.mkdtemp(prefix='fifa_live_order_'));sys.path.insert(0,str(ROOT));os.environ.pop('DATABASE_URL',None)
try: import streamlit  # noqa
except ModuleNotFoundError:
    st=types.ModuleType('streamlit');st.secrets={};st.cache_resource=lambda *a,**k:(lambda f:f);sys.modules['streamlit']=st
try: import psycopg  # noqa
except ModuleNotFoundError:
    ps=types.ModuleType('psycopg');rows=types.ModuleType('psycopg.rows');rows.dict_row=object();ps.rows=rows;sys.modules['psycopg']=ps;sys.modules['psycopg.rows']=rows
from database import Database

def m(no,h,a,score=None,ts=None,stage='GROUP'):
    return {'match_no':no,'stage':stage,'home_player_id':h,'away_player_id':a,
            'home_score':score,'away_score':0 if score is not None else None,
            'match_status':'played' if score is not None else 'pending','played_at':ts}

def main():
    db=Database()
    extra={'smart_scheduler':True,'match_play_order':[4,5,7],
           'scheduler_tiebreak':{'4':.1,'5':.2,'7':.3}}
    matches=[
        m(1,'x','y',2,'2026-01-01T10:00:00'),
        m(4,'a','b'),
        m(5,'a','c'),
        m(7,'d','e'),
    ]
    cur=db.current_match_from(matches,extra)
    assert cur['match_no']==4,cur
    naive=db.next_ready_match_from(matches,4,extra)
    projected=db.visible_next_match_from(matches,4,extra)
    assert naive['match_no']==5,naive
    assert projected['match_no']==7,projected
    sched=db.live_schedule_from(matches,extra)
    assert [x['match_no'] for x in sched]==[1,4,7,5],sched
    assert [x['display_match_no'] for x in sched]==[1,2,3,4],sched
    assert [x['match_no'] for x in matches]==[1,4,5,7],matches
    print('PASS NEXT uses post-result scheduler projection')
    print('PASS live schedule follows projected play order')
    print('PASS public M numbers follow actual/display order without changing logical IDs')

    app=(ROOT/'app.py').read_text(encoding='utf-8')
    assert '@st.fragment(run_every="5s")\ndef _render_tv_live_fragment' in app
    assert '@st.fragment(run_every="30s")\ndef _render_tv_auto_fragment' in app
    assert '@st.fragment(run_every="1s")\ndef render_tv_screen' not in app
    print('PASS Streamlit LIVE=5s and AUTO=30s refresh split')

if __name__=='__main__': main()

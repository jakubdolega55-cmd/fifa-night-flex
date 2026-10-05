import os, sys, tempfile, types
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
WORK=tempfile.mkdtemp(prefix='fifa_fc27_small_wheel_')
os.chdir(WORK);sys.path.insert(0,str(ROOT));os.environ.pop('DATABASE_URL',None)
try: import streamlit  # noqa
except ModuleNotFoundError:
    st=types.ModuleType('streamlit');st.secrets={};st.cache_resource=lambda *a,**k:(lambda f:f);sys.modules['streamlit']=st
try: import psycopg  # noqa
except ModuleNotFoundError:
    ps=types.ModuleType('psycopg');rows=types.ModuleType('psycopg.rows');rows.dict_row=object();ps.rows=rows;sys.modules['psycopg']=ps;sys.modules['psycopg.rows']=rows
from database import Database
from logic import allowed_teams

FORMATS={3:'league3_final',4:'league4_final',5:'league5_final'}
for n in (3,4,5):
    db=Database();db.init_schema()
    pool=allowed_teams(n,'FC27','clubs',False)
    assert len(pool)==6,(n,pool)
    assert pool[:5]==['Real Madryt','PSG','Bayern Monachium','FC Barcelona','Arsenal'],pool
    assert 'Dowolna drużyna' in pool[5],pool
    names=[f'P{n}_{i}' for i in range(n)]
    tid=db.create_tournament(names,n,FORMATS[n],pool,True,0,[True]*n,'FC27','clubs')
    b=db.setup_bundle(tid)
    assert b['tournament']['phase']=='team_draw',(n,b['tournament']['phase'])
    assert (b['meta']['extra'] or {}).get('partial_wheel_pool') is True
    assert len(db.remaining_wheel_pool(tid))==6
    for draw_no in range(1,n+1):
        before=db.remaining_wheel_pool(tid)
        assert len(before)==7-draw_no,(n,draw_no,before)
        r=db.reveal_next_team(tid)
        assert r and r['wheel_team'] in before,(n,draw_no,r,before)
        # Even the last real player must spin because unused sectors remain.
        assert r.get('auto_assigned') is False,(n,draw_no,r)
        if r.get('wildcard'):
            choice=db.available_wildcard_suggestions(tid)[0]
            db.confirm_wildcard_team(tid,r['player_id'],choice)
        after=db.remaining_wheel_pool(tid)
        assert len(after)==len(before)-1,(n,draw_no,after)
    assert len(db.remaining_wheel_pool(tid))==6-n,(n,db.remaining_wheel_pool(tid))
    b=db.setup_bundle(tid)
    assert all(int(p['team_revealed']) for p in b['players'])
    assert len({p['team'] for p in b['players']})==n
    print(f'PASS FC27 {n}: 6-sector wheel -> {n} draws -> {6-n} unused sectors')

# Legacy FC26 3/4 remains draft.
for n,fmt in ((3,'league3_final'),(4,'league4_final')):
    db=Database();db.init_schema();pool=allowed_teams(n,'FC26','clubs',False)
    tid=db.create_tournament([f'L{n}_{i}' for i in range(n)],n,fmt,pool,True,0,[True]*n,'FC26','clubs')
    assert db.setup_bundle(tid)['tournament']['phase']=='draft_order'
print('PASS FC26 3/4 legacy draft unchanged')

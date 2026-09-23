import os, sys, tempfile, types
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
WORK=tempfile.mkdtemp(prefix='fifa_wheel_shrink_')
os.chdir(WORK); sys.path.insert(0,str(ROOT)); os.environ.pop('DATABASE_URL',None)
try: import streamlit  # noqa
except ModuleNotFoundError:
    st=types.ModuleType('streamlit'); st.secrets={}; st.cache_resource=lambda *a,**k:(lambda f:f); sys.modules['streamlit']=st
try: import psycopg  # noqa
except ModuleNotFoundError:
    ps=types.ModuleType('psycopg'); rows=types.ModuleType('psycopg.rows'); rows.dict_row=object(); ps.rows=rows; sys.modules['psycopg']=ps; sys.modules['psycopg.rows']=rows
from database import Database
from logic import allowed_teams

def main():
    db=Database(); db.init_schema()
    names=[f'wheel_{i}' for i in range(10)]
    tid=db.create_tournament(names,10,'double10',allowed_teams(10,'FC27'),True,0,[True]*10,'FC27')
    initial=db.remaining_wheel_pool(tid)
    assert len(initial)==10, initial
    assert db.available_wildcard_suggestions(tid)[0]=='Manchester City', db.available_wildcard_suggestions(tid)[:5]
    used=[]
    for remaining in range(10,0,-1):
        before=db.remaining_wheel_pool(tid)
        assert len(before)==remaining,(remaining,before)
        assert all(x not in before for x in used), (used,before)
        r=db.reveal_next_team(tid)
        assert r, remaining
        target=str(r.get('wheel_team') or r.get('team') or '')
        assert target in r.get('pool',[]),(target,r)
        assert r['pool']==before,(r['pool'],before)
        assert len(r['pool'])==remaining
        used.append(target)
        if r.get('wildcard'):
            ok=False
            for team in db.available_wildcard_suggestions(tid):
                try:
                    db.confirm_wildcard_team(tid,r['player_id'],team); ok=True; break
                except ValueError:
                    pass
            assert ok,'could not confirm WC'
        after=db.remaining_wheel_pool(tid)
        assert len(after)==remaining-1,(remaining,after)
        assert target not in after,(target,after)
    assert db.remaining_wheel_pool(tid)==[]
    print('WHEEL SHRINK SMOKE PASS: 10 -> 0; every visual target == backend target')

if __name__=='__main__': main()

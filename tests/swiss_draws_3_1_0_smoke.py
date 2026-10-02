import os,sys,tempfile,types
WORK=tempfile.mkdtemp(prefix='fifa_swiss_draw_');os.environ['FIFA_NIGHT_DB']=os.path.join(WORK,'x.db')
# lightweight optional-dependency stubs, matching existing smoke style
st=types.ModuleType('streamlit'); st.cache_data=lambda *a,**k:(lambda f:f); st.cache_resource=lambda *a,**k:(lambda f:f); sys.modules['streamlit']=st
ps=types.ModuleType('psycopg');ps.connect=lambda *a,**k:None;ps.errors=types.SimpleNamespace(UniqueViolation=Exception);ps.IntegrityError=Exception
rowsmod=types.ModuleType('psycopg.rows');rowsmod.dict_row=lambda *a,**k:None;ps.rows=rowsmod;sys.modules['psycopg']=ps;sys.modules['psycopg.rows']=rowsmod
from database import Database
from logic import allowed_teams

def setup(db,tid):
    for _ in range(100):
        b=db.setup_bundle(tid); ph=b['tournament']['phase']
        if ph=='team_draw':
            r=db.reveal_next_team(tid)
            if r and r.get('wildcard'):
                for team in db.wildcard_team_suggestions('FC27'):
                    try: db.confirm_wildcard_team(tid,r['player_id'],team);break
                    except ValueError: pass
            if all(p['team_revealed'] for p in db.setup_bundle(tid)['players']): db.start_structure_draw(tid)
        elif ph=='structure_draw': db.reveal_structure(tid);db.confirm_structure(tid);return
        elif ph=='active': return
    raise AssertionError('setup loop')

db=Database();db.init_schema();n=8
tid=db.create_tournament([f'P{i}' for i in range(n)],n,'swiss8',allowed_teams(n,'FC27'),True,0,[True]*n,'FC27');setup(db,tid)
# Draw is final in Swiss and awards one point each.
db.save_result(tid,1,2,2)
m=next(x for x in db.bundle(tid)['matches'] if int(x['match_no'])==1)
assert (m['home_score'],m['away_score'])==(2,2)
assert m.get('winner_player_id') is None and m.get('home_penalties') is None and m.get('away_penalties') is None
rows=db.standings(tid)['S']; by={r['player_id']:r for r in rows}
for pid in (m['home_player_id'],m['away_player_id']):
    assert by[pid]['m']==1 and by[pid]['w']==0 and by[pid]['d']==1 and by[pid]['l']==0 and by[pid]['pts']==1
# Penalties are explicitly forbidden in Swiss rounds.
try:
    db.save_result(tid,2,1,1,5,4)
    raise AssertionError('Swiss penalties accepted')
except ValueError as e:
    assert 'Swiss' in str(e)
print('PASS swiss draw 3-1-0 + no penalties')

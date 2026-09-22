import os,sys,tempfile,types,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
WORK=tempfile.mkdtemp(prefix='fifa_group_tb_');os.chdir(WORK);sys.path.insert(0,str(ROOT));os.environ.pop('DATABASE_URL',None)
try: import streamlit
except ModuleNotFoundError:
 st=types.ModuleType('streamlit');st.secrets={};st.cache_resource=lambda *a,**k:(lambda f:f);sys.modules['streamlit']=st
try: import psycopg
except ModuleNotFoundError:
 ps=types.ModuleType('psycopg');rows=types.ModuleType('psycopg.rows');rows.dict_row=object();ps.rows=rows;sys.modules['psycopg']=ps;sys.modules['psycopg.rows']=rows
from database import Database
from logic import allowed_teams

def setup(db,tid):
 for _ in range(100):
  b=db.setup_bundle(tid);ph=b['tournament']['phase']
  if ph=='draft_order':db.reveal_draft_order(tid);db.confirm_draft_order(tid)
  elif ph=='team_draft':
   p=next(x for x in db.tournament_players(tid) if not x.get('team_revealed'));avail=[x for x in db.available_draft_teams(tid) if x!='🃏 Wild Card'];db.draft_pick(tid,p['player_id'],avail[0])
  elif ph=='team_draw':
   r=db.reveal_next_team(tid)
   if r and r.get('wildcard'):
    for team in db.wildcard_team_suggestions('FC27'):
     try:db.confirm_wildcard_team(tid,r['player_id'],team);break
     except ValueError:pass
   if all(bool(p['team_revealed']) for p in db.setup_bundle(tid)['players']):db.start_structure_draw(tid)
  elif ph=='structure_draw':db.reveal_structure(tid);db.confirm_structure(tid);return
  elif ph=='active':return
 raise AssertionError('setup')

def group_matches(db,tid,g='A'):
 return sorted([m for m in db.matches(tid) if m.get('group_name')==g],key=lambda x:int(x['match_no']))

def save_winner(db,tid,m,winner,events=None):
 h=str(m['home_player_id']);a=str(m['away_player_id'])
 db.save_result(tid,int(m['match_no']),1 if h==winner else 0,1 if a==winner else 0,events=events)

db=Database();db.init_schema()
# direct last-match decider
T=db.create_tournament(list('ABCDEF'),6,'groups6',allowed_teams(6,'FC27'),True,0,[True]*6,'FC27');setup(db,T)
a=group_matches(db,T,'A'); assert len(a)==3
p12=set([a[0]['home_player_id'],a[0]['away_player_id']]);p22=set([a[1]['home_player_id'],a[1]['away_player_id']]);leader=str(next(iter(p12&p22)))
for m in a[:2]:
 h=str(m['home_player_id']);aw=str(m['away_player_id']);db.save_result(T,int(m['match_no']),2 if h==leader else 0,2 if aw==leader else 0)
last=a[2];ctx=db.group_match_tiebreak_context(T,int(last['match_no']));print('CTX',ctx);assert ctx.get('required') is True
try: db.save_result(T,int(last['match_no']),2,2)
except ValueError as e: assert 'dogryw' in str(e).lower() or 'awans' in str(e).lower(),e
else: raise AssertionError('draw accepted without shootout')
h=str(last['home_player_id']);aw=str(last['away_player_id']);db.save_result(T,int(last['match_no']),2,2,5,4)
tab=db.standings(T)['A'];print('DIRECT TABLE',[(r['name'],r['pts'],r['gd'],r['gf'],r.get('fair_play')) for r in tab])
assert tab[0]['player_id']==leader
assert tab[1]['player_id']==h and tab[2]['player_id']==aw,(h,aw,tab)
assert tab[1]['pts']==1 and tab[2]['pts']==1

# three-way cyclic tie -> fair play
T2=db.create_tournament(['G','H','I','J','K','L'],6,'groups6',allowed_teams(6,'FC27'),True,0,[True]*6,'FC27');setup(db,T2)
a=group_matches(db,T2,'A');ids=sorted({str(x['home_player_id']) for x in a}|{str(x['away_player_id']) for x in a});p0,p1,p2=ids
beats={(p0,p1),(p1,p2),(p2,p0)}
def desired(a,b):
 return a if (a,b) in beats else b
for i,m in enumerate(a):
 win=desired(str(m['home_player_id']),str(m['away_player_id']))
 ev=[]
 # give p1 one yellow and p2 one red in their first encountered match
 if i==0:
  ev=[{'event_type':'yellow_card','actor_player_id':p1,'footballer_name':'Y'}]
 if i==1:
  ev=[{'event_type':'red_card','actor_player_id':p2,'footballer_name':'R'}]
 save_winner(db,T2,m,win,ev)
tab=db.standings(T2)['A'];print('FAIR TABLE',[(r['player_id'],r['pts'],r['gd'],r['gf'],r.get('fair_play')) for r in tab])
assert [r['player_id'] for r in tab]==[p0,p1,p2],tab
assert [r['fair_play'] for r in tab]==[0,1,3],tab

# three-way cyclic tie, no cards -> persistent lot, not tie_order
T3=db.create_tournament(['M','N','O','P','Q','R'],6,'groups6',allowed_teams(6,'FC27'),True,0,[True]*6,'FC27');setup(db,T3)
a=group_matches(db,T3,'A');ids=sorted({str(x['home_player_id']) for x in a}|{str(x['away_player_id']) for x in a});p0,p1,p2=ids;beats={(p0,p1),(p1,p2),(p2,p0)}
for m in a: save_winner(db,T3,m,desired(str(m['home_player_id']),str(m['away_player_id'])))
with db.connect() as c:
 meta,extra=db._meta_extra_conn(c,T3);lot=(extra.get('group_lot_order') or {}).get('A') or {}
assert set(lot)==set(ids),lot
first=db.standings(T3)['A'];second=db.standings(T3)['A'];order=[r['player_id'] for r in first];expected=sorted(ids,key=lambda x:int(lot[x]));print('LOT',lot,'ORDER',order)
assert order==expected,(order,expected)
assert [r['player_id'] for r in second]==order
print('GROUP TIEBREAK TEST PASS')

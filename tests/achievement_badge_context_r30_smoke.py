import json, os, sys, tempfile, types, uuid
from pathlib import Path
from datetime import datetime, timedelta, timezone

ROOT=Path(__file__).resolve().parents[1]
WORK=tempfile.mkdtemp(prefix='fifa_r30_badge_context_')
os.chdir(WORK);sys.path.insert(0,str(ROOT));os.environ.pop('DATABASE_URL',None)
try:
    import streamlit
except ModuleNotFoundError:
    st=types.ModuleType('streamlit');st.secrets={};st.cache_resource=lambda *a,**k:(lambda f:f);sys.modules['streamlit']=st
try:
    import psycopg
except ModuleNotFoundError:
    ps=types.ModuleType('psycopg');rows=types.ModuleType('psycopg.rows');rows.dict_row=object();ps.rows=rows;sys.modules['psycopg']=ps;sys.modules['psycopg.rows']=rows

from database import Database
DB=Database();DB.init_schema()
BASE=datetime(2026,1,1,tzinfo=timezone.utc);clock=0

def stamp():
    global clock
    clock+=1
    return (BASE+timedelta(minutes=clock)).isoformat()

def player(pid,name=None):
    name=name or pid
    with DB.connect() as c:c.execute(DB._sql('INSERT INTO players (id,name,normalized_name,created_at) VALUES (?,?,?,?)'),(pid,name,name.casefold(),stamp()))

def tournament(tid,pids,status='completed',champ=None,teams=None):
    teams=teams or {p:f'Team {p}' for p in pids}
    with DB.connect() as c:
        c.execute(DB._sql('INSERT INTO tournaments (id,status,phase,is_test,is_current,game_version,groups_revealed,created_at,completed_at,champion_player_id) VALUES (?,?,?,?,?,?,?,?,?,?)'),(tid,status,'completed' if status=='completed' else 'active',0,0,'FC27',1,stamp(),stamp() if status=='completed' else None,champ))
        c.execute(DB._sql('INSERT INTO flex_tournament_meta (tournament_id,player_count,format_key,team_pool_json,draw_json,extra_json,draw_revealed,redraw_count) VALUES (?,?,?,?,?,?,?,?)'),(tid,len(pids),'league4_final','[]','{}',json.dumps({'team_mode':'clubs'}),1,0))
        for i,p in enumerate(pids,1):
            c.execute(DB._sql('INSERT INTO tournament_players (tournament_id,player_id,team,team_reveal_order,team_revealed,group_name,tie_order) VALUES (?,?,?,?,?,?,?)'),(tid,p,teams[p],i,1,'',i))

def match(tid,no,home,away,hs,aws,stage='LEAGUE'):
    with DB.connect() as c:c.execute(DB._sql('INSERT INTO matches (id,tournament_id,match_no,stage,group_name,home_player_id,away_player_id,home_score,away_score,winner_player_id,played_at,match_status) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)'),(str(uuid.uuid4()),tid,no,stage,'',home,away,hs,aws,home if hs>aws else away if aws>hs else None,stamp(),'played'))

def event(tid,no,order,typ,actor,credited,footballer,minute):
    with DB.connect() as c:c.execute(DB._sql('INSERT INTO match_events (id,tournament_id,match_no,event_order,event_type,minute,stoppage,minute_label,actor_player_id,credited_player_id,footballer_name,normalized_footballer,synthetic_de,confidence,source_images_json,created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)'),(str(uuid.uuid4()),tid,no,order,typ,minute,0,str(minute),actor,credited,footballer,footballer.casefold() if footballer else '',0,'high','[]',stamp()))

for p,n in [('A','Adam'),('B','Bartek'),('C','Celina')]:player(p,n)

# Active history: match 1 has a penalty miss and one player scores 6, but another scorer adds the 7th.
# It must NOT count as One Man Army progress of 6.
tournament('live',['A','B'],status='active',teams={'A':'Arsenal','B':'Milan'})
match('live',1,'A','B',7,1)
event('live',1,1,'penalty_miss','A',None,'Hero',3)
for i,m in enumerate((10,20,30,40,50,60),2):event('live',1,i,'normal_goal','A','A','Hero',m)
event('live',1,8,'normal_goal','A','A','Other',70)
event('live',1,9,'normal_goal','B','B','Rival',80)
# Match 2 is a genuine single-scorer win, but only 2 goals => truthful 2/3 progress.
match('live',2,'A','B',2,0)
event('live',2,1,'normal_goal','A','A','Solo',20)
event('live',2,2,'normal_goal','A','A','Solo',50)

# Three championship teams for Mistrz wielu barw.
for i,team in enumerate(('Arsenal','Bayern','Juventus'),1):
    tid=f'title-{i}'
    tournament(tid,['C','B'],status='completed',champ='C',teams={'C':team,'B':'PSG'})
    match(tid,1,'C','B',2,0,stage='FINAL')

# A completed FIFA Night verifies that classic match badges get full historical context too.
tournament('context',['A','B'],status='completed',champ='A',teams={'A':'Real Madrid','B':'Liverpool'})
match('context',1,'A','B',4,3)
match('context',2,'A','B',2,2,stage='FINAL')
with DB.connect() as c:
    c.execute(DB._sql('UPDATE matches SET winner_player_id=?, home_penalties=?, away_penalties=? WHERE tournament_id=? AND match_no=?'),('A',7,6,'context',2))

center=DB.achievement_center();by={p['player_id']:p for p in center['players']}
a=by['A']; c=by['C']
miss=next(x for x in a['unlocked'] if x['key']=='missed_penalty_win')
assert miss['event_context']=='FIFA Night (w toku)',miss
assert miss['match_context']=='vs Bartek • 7:1',miss
assert miss['team_context']=='Arsenal',miss
locked={x['key']:x for x in a['locked']}
assert 'one_man_army' in locked, [x['key'] for x in a['unlocked']]
assert locked['one_man_army']['progress']=='najlepiej: 2/3 gole — wszystkie jednego strzelca',locked['one_man_army']
colors=next(x for x in c['unlocked'] if x['key']=='many_colors_champion')
for team in ('Arsenal','Bayern','Juventus'):
    assert team in colors['detail'],colors
assert colors['event_context']=='FIFA Night #3',colors
assert colors['team_context']=='Juventus',colors
thriller=next(x for x in a['unlocked'] if x['key']=='thriller')
assert thriller['event_context']=='FIFA Night #4' and thriller['match_context']=='vs Bartek • 4:3',thriller
assert thriller['team_context']=='Real Madrid' and thriller['detail']=='',thriller
ice=next(x for x in a['unlocked'] if x['key']=='ice_cold')
assert ice['event_context']=='FIFA Night #4' and ice['match_context']=='vs Bartek • 2:2 (k. 7:6)',ice
assert ice['team_context']=='Real Madrid' and ice['detail']=='',ice

mobile=(ROOT/'mobile'/'src'/'StatsScreen.tsx').read_text(encoding='utf-8')
assert 'Wybierz kategorię' in mobile
assert 'badgeCategoryTile' in mobile and 'badgeCategoryTileActive' in mobile
assert 'const items=group?catalog.filter' in mobile
assert 'Mecz: {got.match_context}' in mobile
assert 'Mecz: ${x.match_context}' in mobile
assert 'got.event_context' in mobile and 'x.event_context' in mobile
assert 'Drużyna: {got.team_context}' in mobile and 'Drużyna: ${x.team_context}' in mobile
app=(ROOT/'app.py').read_text(encoding='utf-8')
assert 'event_context' in app and 'team_context' in app
print('achievement_badge_context_r30_smoke PASS')

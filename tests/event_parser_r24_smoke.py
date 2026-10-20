import os,sys,tempfile,types
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
WORK=tempfile.mkdtemp(prefix='fifa_r24_events_')
os.chdir(WORK)
sys.path.insert(0,str(ROOT))
os.environ.pop('DATABASE_URL',None)

# Lightweight stubs: the smoke uses SQLite only.
ps=types.ModuleType('psycopg'); rows=types.ModuleType('psycopg.rows'); rows.dict_row=object(); ps.rows=rows
sys.modules.setdefault('psycopg',ps);sys.modules.setdefault('psycopg.rows',rows)
pp=types.ModuleType('psycopg_pool'); pp.ConnectionPool=None;sys.modules.setdefault('psycopg_pool',pp)
st=types.ModuleType('streamlit'); st.secrets={}; st.cache_resource=lambda *a,**k:(lambda f:f);sys.modules.setdefault('streamlit',st)

import mobile_api as api
api.db.init_schema()

PROMPT=api.AI_EVENT_SCAN_PROMPT + api._match_event_scan_prompt({
    'game_version':'FC27','format_key':'groups6','stage':'GROUP',
    'participants':[
        {'slot':'home','player_id':'p1','player_name':'A','team':'Arsenal'},
        {'slot':'away','player_id':'p2','player_name':'B','team':'Manchester City'},
    ],
})
assert 'DIRECT RED CARD' in PROMPT and 'ALWAYS red_card' in PROMPT
assert 'second_yellow_red' in PROMPT and 'Do NOT convert the second yellow into red_card' in PROMPT
assert 'distinctly MEDICAL pictogram' in PROMPT and 'goal/net-with-X' in PROMPT
assert 'finished 3:3 and the shoot-out finished 7:6' in PROMPT
print('R24 PROMPT RULES PASS')


def base_result(score_left=0,score_right=0,events=None,shootout_left=None,shootout_right=None):
    return {
        'left_label':'Arsenal','right_label':'Manchester City',
        'score_left':score_left,'score_right':score_right,'match_clock':'FT',
        'score_confidence':'high','events':events or [],'event_list_complete':True,
        'needs_more_images':False,'notes':[],
        'left_participant_slot':'home','right_participant_slot':'away','mapping_confidence':'high',
        'shootout_left':shootout_left,'shootout_right':shootout_right,
    }

CTX={
    'game_version':'FC27','format_key':'groups6','stage':'GROUP',
    'participants':[
        {'slot':'home','player_id':'p1','player_name':'A','team':'Arsenal'},
        {'slot':'away','player_id':'p2','player_name':'B','team':'Manchester City'},
    ],
}

# 1) Direct red remains a direct red; same-player two yellows remain two yellows.
card_events=[
    {'image_indices':[1],'minute':25,'stoppage':None,'minute_label':'25','side':'left','event_type':'red_card','player':'William Saliba','own_goal_by':None,'related_player':None,'credited_side':'unknown','confidence':'high'},
    {'image_indices':[1],'minute':30,'stoppage':None,'minute_label':'30','side':'right','event_type':'yellow_card','player':'Rodri','own_goal_by':None,'related_player':None,'credited_side':'unknown','confidence':'high'},
    {'image_indices':[1],'minute':39,'stoppage':None,'minute_label':'39','side':'right','event_type':'yellow_card','player':'Rodri','own_goal_by':None,'related_player':None,'credited_side':'unknown','confidence':'high'},
]
card_norm=api._normalize_and_validate_event_scan_result(base_result(events=card_events))
assert [e['event_type'] for e in card_norm['events']]==['red_card','yellow_card','yellow_card'],card_norm['events']
print('R24 DIRECT RED + SECOND YELLOW DISTINCTION PASS')

# 2) Injury and missed penalty stay distinct and neither affects the score.
misc_events=[
    {'image_indices':[1],'minute':70,'stoppage':None,'minute_label':'70','side':'right','event_type':'penalty_miss','player':'Erling Haaland','own_goal_by':None,'related_player':None,'credited_side':'unknown','confidence':'high'},
    {'image_indices':[1],'minute':80,'stoppage':None,'minute_label':'80','side':'left','event_type':'injury','player':'Bukayo Saka','own_goal_by':None,'related_player':None,'credited_side':'unknown','confidence':'high'},
]
misc=api._normalize_and_validate_event_scan_result(base_result(events=misc_events))
assert [e['event_type'] for e in misc['events']]==['penalty_miss','injury']
assert misc['goal_validation']['complete'] is True,misc['goal_validation']
print('R24 INJURY VS PENALTY MISS PASS')

# 3) Wrong-team scorer is now resolved on mapped events and blocks silent acceptance.
wrong_goal={
    'image_indices':[1],'minute':12,'stoppage':None,'minute_label':'12','side':'left',
    'event_type':'normal_goal','player':'Erling Haaland','own_goal_by':None,'related_player':None,
    'credited_side':'left','confidence':'high'
}
wrong=api._map_scan_to_fifa_context(base_result(1,0,[wrong_goal]),CTX)
wrong=api._resolve_scan_footballer_names(wrong,CTX)
we=wrong['fifa_night']['events'][0]
assert we['actor_team_name']=='Arsenal',we
assert we['footballer_resolution']['status']=='unresolved',we
assert wrong['fifa_night']['goal_validation']['complete'] is False,wrong['fifa_night']['goal_validation']
assert wrong['fifa_night']['goal_validation']['unresolved_goal_scorers']==1
match={'home_player_id':'p1','away_player_id':'p2','home_name':'A','away_name':'B','home_team':'Arsenal','away_team':'Manchester City','stage':'GROUP'}
try:
    api._normalize_events_for_save(match,'groups6',1,0,[we])
except ValueError as exc:
    assert 'nie został potwierdzony' in str(exc),exc
else:
    raise AssertionError('unresolved wrong-team scorer should be blocked')
# Explicit user confirmation is allowed because local rosters may lag behind EA updates.
confirmed={**we,'footballer_confirmed':True}
normalized,validation=api._normalize_events_for_save(match,'groups6',1,0,[confirmed])
assert validation['complete'] is True and normalized[0]['footballer_name']=='Erling Haaland'
print('R24 SCORER ROSTER REVIEW PASS')

# 4) 3:3 + shoot-out 7:6: 120-minute shoot-out rows are not normal goals.
regular=[]
for i,(side,name) in enumerate([
    ('left','Bukayo Saka'),('right','Erling Haaland'),('left','Viktor Gyokeres'),
    ('right','Phil Foden'),('left','Martin Odegaard'),('right','Jeremy Doku'),
],1):
    regular.append({'image_indices':[1],'minute':10*i,'stoppage':None,'minute_label':str(10*i),'side':side,'event_type':'normal_goal','player':name,'own_goal_by':None,'related_player':None,'credited_side':side,'confidence':'high'})
shoot=[]
for i in range(13):
    side='left' if i%2==0 else 'right'
    shoot.append({'image_indices':[2+(i//6)],'minute':120,'stoppage':None,'minute_label':'120','side':side,'event_type':'penalty_goal','player':f'Kick {i+1}','own_goal_by':None,'related_player':None,'credited_side':side,'confidence':'high'})
shoot_result=api._map_scan_to_fifa_context(base_result(3,3,regular+shoot,7,6),CTX)
fn=shoot_result['fifa_night']
assert fn['home_score']==3 and fn['away_score']==3,fn
assert fn['home_penalties']==7 and fn['away_penalties']==6,fn
assert len(fn['events'])==6,fn['events']
assert fn['goal_validation']['complete'] is True,fn['goal_validation']
assert any('serii karnych' in str(x) for x in shoot_result.get('notes') or []),shoot_result.get('notes')
print('R24 3:3 + PENS 7:6 PASS')

# 5) Mobile UI must expose the roster-review gate/confirmation.
mobile=(ROOT/'mobile/src/FifaScreen.tsx').read_text(encoding='utf-8')
assert 'unresolvedScorers' in mobile and 'POTWIERDŹ PIŁKARZA' in mobile
assert 'footballer_resolution:undefined,footballer_confirmed:true' in mobile
print('R24 MOBILE REVIEW UI PASS')

print('PASS R24 EVENT PARSER TARGETED SMOKE')

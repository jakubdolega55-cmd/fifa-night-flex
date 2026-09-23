import sys, types
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
try:
    import streamlit  # noqa
except ModuleNotFoundError:
    st=types.ModuleType('streamlit');st.secrets={};st.cache_resource=lambda *a,**k:(lambda f:f);sys.modules['streamlit']=st
try:
    import psycopg  # noqa
except ModuleNotFoundError:
    ps=types.ModuleType('psycopg');rows=types.ModuleType('psycopg.rows');rows.dict_row=object();ps.rows=rows
    sys.modules['psycopg']=ps;sys.modules['psycopg.rows']=rows
from database import Database, GALA_AWARD_ORDER

SAMPLES={
    'superscorer':{'name':'Haaland','goals':31,'scoring_matches':14,'fifa_night_players':4,'hattricks':3,'goal_progress':[0,2,2,5,31]},
    'team_best':{'name':'Liverpool','matches':22,'finals':5,'titles':3,'wins':14,'draws':4,'losses':4,'win_pct':63.6,'gf':61,'ga':43,'gd':18},
    'finance':{'name':'Kubsi','won_pln':424,'paid_pln':240,'balance_pln':184},
    'debut':{'name':'Mati','matches':10,'w':6,'d':1,'l':3,'win_pct':60,'points_per_match':1.9,'gf':27,'ga':19,'gd':8,'finals':2,'titles':1},
    'progress':{'name':'A','matches':31,'win_pct':55,'early_points_per_match':1.08,'late_points_per_match':2.04,'early_gd_per_match':-.46,'late_gd_per_match':.62},
    'outsider':{'name':'B','starts':7,'finals':2,'titles':1,'gd':14,'wins':19,'win_pct':61,'gf':71,'ga':57},
    'rivalry':{'name':'Kubsi vs Mati','participant_names':['Kubsi','Mati'],'matches':12,'finals':1,'semifinals':2,'wins_a':7,'wins_b':5,'goals_a':34,'goals_b':29,'penalty_matches':2,'winner_name':'Kubsi','loser_name':'Mati','winner_decider':'zwycięstwa H2H'},
    'fair_play':{'name':'Mati','matches':18,'fouls_total':14,'fouls_matches':11,'discipline_per_match':.17,'yellow':3,'red':0},
    'universal':{'name':'K','teams_count':8,'successful_teams':5,'starts':7,'win_pct':64},
    'comeback_king':{'name':'B','comeback_wins':5,'comeback_points':11,'best_comeback_from':'1:4','best_comeback_final':'5:4','comeback_breakdown':{'1':3,'2':1,'3':1}},
    'late_king':{'name':'K','matches':24,'latest_goal':"90+6'",'late_goals':9,'goals_90plus':4},
    'spectacle':{'name':'M','matches':21,'avg_goals':4.8,'spectacular_matches':9,'penalty_matches':4,'summary_total_xg_per_match':6.1},
    'match_year':{'name':'Kubsi 5:4 Mati','home_name':'Kubsi','away_name':'Mati','home_score':5,'away_score':4,'stage_label':'półfinał','cash_pot_pln':120,'drama_text':['3 zmiany prowadzenia'],'winner_name':'Kubsi','loser_name':'Mati'},
    'clutch':{'name':'K','clutch_matches':11,'clutch_wins':8,'clutch_pct':72.7,'clutch_by_stage':{'FINAL':{'m':4,'w':3},'SF':{'m':4,'w':3},'QF':{'m':3,'w':2}}},
    'player_scorers':{'name':'Haaland — Kubsi','matches':12,'hattricks':3,'goals':19},
    'defense':{'name':'M','matches':22,'clean_sheets':7,'ga_per_match':1.42,'ga':31,'xga_per_match':1.51},
    'offensive':{'name':'K','matches':24,'big_wins':12,'goals_per_match':3.71,'goals':89,'max_margin':7,'xg_per_match':3.4,'shots_per_match':13.2,'sot_per_match':7.1},
    'player_year':{'name':'K','starts':8,'matches':47,'finals':7,'titles':4,'win_pct':66,'gf':121,'ga':86,'gd':35,'wins':31,'draws':5,'losses':11,'clutch_wins':9,'clutch_matches':13,'clutch_pct':69.2},
}

assert list(SAMPLES)==GALA_AWARD_ORDER
for key in GALA_AWARD_ORDER:
    out=Database._gala_candidate_presentation(key,SAMPLES[key])
    assert out['display_name']
    assert out['teaser_lines'], key
    assert out['winner_lines'], key

# Mystery rules from the agreed gala design: TOP3 explains nomination without
# revealing the strongest deciding data. Winner cards can reveal the full case.
def teaser(key):
    return " | ".join(Database._gala_candidate_presentation(key,SAMPLES[key])['teaser_lines']).lower()

assert 'goli' not in teaser('superscorer') and 'meczów z golem' in teaser('superscorer') and 'graczy fifa night' in teaser('superscorer') and 'hat-trick' in teaser('superscorer')
assert 'bramki' not in teaser('team_best') and '% w' not in teaser('team_best') and 'tytu' not in teaser('team_best') and 'fina' in teaser('team_best')
assert 'wpłat' not in teaser('finance') and 'bilans' not in teaser('finance')
assert 'fina' not in teaser('debut') and 'tytu' not in teaser('debut') and 'pkt/mecz' not in teaser('debut')
assert '→' not in teaser('progress') and 'pkt/mecz' not in teaser('progress') and 'bilans bramek/mecz' not in teaser('progress')
assert '% w' not in teaser('outsider') and 'zwycięstw' not in teaser('outsider')
assert '7 : 5' not in teaser('rivalry') and 'bramki' not in teaser('rivalry')
assert '🟨' not in teaser('fair_play') and '🟥' not in teaser('fair_play') and 'dyscypliny' not in teaser('fair_play')
assert '% w' not in teaser('universal') and 'sukces' not in teaser('universal')
assert 'pkt comebacku' not in teaser('comeback_king') and 'największy' not in teaser('comeback_king')
assert "goli od 85" not in teaser('late_king')
assert 'widowiskowych' not in teaser('spectacle') and 'karnymi' not in teaser('spectacle')
assert '5 : 4' not in teaser('match_year') and '9 goli' not in teaser('match_year')
assert 'wygranych clutch' not in teaser('clutch') and '%' not in teaser('clutch')
assert 'goli' not in teaser('player_scorers')
assert 'straconego' not in teaser('defense') and 'xga' not in teaser('defense')
assert 'gola/mecz' not in teaser('offensive') and 'xg' not in teaser('offensive')
assert 'tytu' not in teaser('player_year') and 'finałów' in teaser('player_year') and 'turniejów' in teaser('player_year')

# Special reveals / effects.
assert Database._gala_candidate_presentation('superscorer',SAMPLES['superscorer'])['special']['type']=='goal_progress'
assert Database._gala_candidate_presentation('progress',SAMPLES['progress'])['special']['type']=='before_after'
assert Database._gala_candidate_presentation('late_king',SAMPLES['late_king'])['special']['type']=='late_clock'
assert Database._gala_candidate_presentation('rivalry',SAMPLES['rivalry'])['special']['type']=='rivalry_vs'
assert Database._gala_candidate_presentation('match_year',SAMPLES['match_year'])['special']['type']=='match_vs'
py=Database._gala_candidate_presentation('player_year',SAMPLES['player_year'])
assert py['special']['type']=='player_year' and py['special']['hero_metric']=='4 TYTUŁY Z 7 FINAŁÓW'

# If rivalry needs a deeper tiebreak, disclose the decider only on the winner card.
alt=dict(SAMPLES['rivalry']);alt['wins_a']=alt['wins_b']=6;alt['winner_decider']='bilans bramek H2H'
r=Database._gala_candidate_presentation('rivalry',alt)
assert not any('rozstrzygnięcie' in x for x in r['teaser_lines'])
assert any('rozstrzygnięcie: bilans bramek h2h' in x.lower() for x in r['winner_lines'])
print('GALA TV PAYLOAD SMOKE PASS')

import os,sys,tempfile,types
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
os.chdir(tempfile.mkdtemp(prefix="fifa_format_first_champion_"));sys.path.insert(0,str(ROOT));os.environ.pop("DATABASE_URL",None)
try: import streamlit
except ModuleNotFoundError:
 st=types.ModuleType("streamlit");st.secrets={};st.cache_resource=lambda *a,**k:(lambda f:f);sys.modules["streamlit"]=st
try: import psycopg
except ModuleNotFoundError:
 ps=types.ModuleType("psycopg");rows=types.ModuleType("psycopg.rows");rows.dict_row=object();ps.rows=rows;sys.modules["psycopg"]=ps;sys.modules["psycopg.rows"]=rows
from database import Database
DB=Database();DB.init_schema()
players=(("p1","Ala"),("p2","Ola"))
with DB.connect() as c:
 for pid,name in players:
  c.execute(DB._sql("INSERT INTO players (id,name,normalized_name,created_at) VALUES (?,?,?,?)"),(pid,name,name.casefold(),"2026-01-01T00:00:00+00:00"))
 # First DE is intentionally already covered by the existing `first_de` milestone.
 # Swiss and KO get dedicated *champion* milestones only after the whole event ends.
 for idx,(tid,fmt,status,champ) in enumerate((
  ("de","double4","completed","p1"),
  ("sw_abandoned","swiss8","abandoned",None),
  ("sw","swiss8","completed","p1"),
  ("ko","knockout8","completed","p2"),
 ),1):
  ts=f"2026-01-0{idx}T12:00:00+00:00"
  c.execute(DB._sql("INSERT INTO tournaments (id,status,phase,is_test,is_current,game_version,groups_revealed,created_at,completed_at,champion_player_id) VALUES (?,?,?,0,0,'FC27',1,?,?,?)"),(tid,status,"completed" if status=="completed" else "abandoned",ts,ts,champ))
  c.execute(DB._sql("INSERT INTO flex_tournament_meta (tournament_id,player_count,format_key,team_pool_json,draw_json,extra_json,draw_revealed,redraw_count) VALUES (?,?,?,'[]','{}','{}',1,0)"),(tid,8 if fmt!="double4" else 4,fmt))
  for order,(pid,name) in enumerate(players,1):
   c.execute(DB._sql("INSERT INTO tournament_players (tournament_id,player_id,team,team_reveal_order,team_revealed,group_name,tie_order) VALUES (?,?,?, ?,1,'',?)"),(tid,pid,"Arsenal" if pid=="p1" else "Bayern Monachium",order,order))
ms=DB.global_milestones();by_key={x["key"]:x for x in ms["timeline"]}
assert "first_de" in by_key, sorted(by_key)
assert "first_de_win" not in by_key, sorted(by_key)
for key,title,tid,champion in (
 ("first_swiss_champion","Pierwszy mistrz Swiss","sw","Ala"),
 ("first_ko_champion","Pierwszy mistrz KO","ko","Ola"),
):
 assert key in by_key,(key,sorted(by_key))
 assert by_key[key]["title"]==title,by_key[key]
 assert by_key[key]["tournament_id"]==tid,by_key[key]
 assert by_key[key]["match_no"] is None,by_key[key]
 assert champion in by_key[key]["detail"],by_key[key]
assert "first_swiss_win" not in by_key and "first_ko_win" not in by_key, sorted(by_key)
assert by_key["first_swiss_champion"]["tournament_id"]!="sw_abandoned",by_key["first_swiss_champion"]
print("PASS first champions: existing DE + Swiss + KO")

import os,sys,tempfile,types
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];WORK=tempfile.mkdtemp(prefix="gala_tv_handshake_");os.chdir(WORK);sys.path.insert(0,str(ROOT));os.environ.pop("DATABASE_URL",None)
try:
 import streamlit
except ModuleNotFoundError:
 st=types.ModuleType("streamlit");st.secrets={};st.cache_resource=lambda *a,**k:(lambda f:f);sys.modules["streamlit"]=st
try:
 import psycopg
except ModuleNotFoundError:
 ps=types.ModuleType("psycopg");rows=types.ModuleType("psycopg.rows");rows.dict_row=object();ps.rows=rows;sys.modules["psycopg"]=ps;sys.modules["psycopg.rows"]=rows
from database import Database,GALA_AWARD_ORDER,GALA_TIMING
assert GALA_TIMING["intro_seconds"]==9.0
assert GALA_TIMING["nominees_seconds"]==11.0
assert GALA_TIMING["nominee_interval_seconds"]==2.5
db=Database();db.init_schema();cats=[];sels={}
for key in GALA_AWARD_ORDER:
 cs=[{"id":f"{key}-{i}","name":f"{key}-{i}","score":10-i,"reason":"x"} for i in range(1,4)];cats.append({"key":key,"title":key,"award":True,"candidates":cs});sels[key]={"id":f"{key}-1","name":"x"}
db.annual_awards=lambda y:{"year":y,"categories":cats,"overview":{},"selections":sels,"nomination_summary":[]}
st=db.start_awards_gala(2026);assert st["display_phase"]=="intro_pending" and st["waiting_for_tv"] is True
st2=db.awards_gala_status(2026);assert st2["display_phase"]=="intro_pending"
# Wrong/stale TV ACK must not start the timer.
st3=db.mark_awards_gala_tv_ready(2026,99);assert st3["display_phase"]=="intro_pending"
# Correct TV ACK starts a fresh full intro.
st4=db.mark_awards_gala_tv_ready(2026,0);assert st4["display_phase"]=="intro" and st4["waiting_for_tv"] is False
print("GALA TV HANDSHAKE SMOKE PASS")

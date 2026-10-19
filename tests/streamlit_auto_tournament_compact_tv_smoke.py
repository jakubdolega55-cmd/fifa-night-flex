from pathlib import Path
root=Path(__file__).resolve().parents[1]
app=(root/'app.py').read_text(encoding='utf-8')
ui=(root/'ui.py').read_text(encoding='utf-8')
assert '@st.fragment(run_every="2s")\ndef watch_current_tournament' in app
assert 'if current_id!=str(expected_id or ""):' in app
assert 'st.session_state["viewer_view"]="📺 LIVE"' in app
assert 'watch_current_tournament(str((t or {}).get("id") or ""))' in app
assert 'if str(t.get("phase") or "") in SETUP_PHASES:' in app
assert 'render_synced_setup_tv(t["id"],MOBILE_API_PUBLIC_URL,compact=True)' in app
assert 'def render_synced_setup_tv(tid: str, api_url: str, compact: bool = False):' in ui
assert 'iframe_height=600 if compact else 680' in ui
assert '.tvroot.compact .wheelBox{{width:min(38vw,540px)}}' in ui
print('PASS passive Streamlit viewer auto-detects new tournament and setup TV is compact')

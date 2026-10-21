from pathlib import Path

root = Path(__file__).resolve().parents[1]
src = (root / 'app.py').read_text(encoding='utf-8')
assert 'def award_owner_name(' in src
assert 'owner=award_owner_name(' in src
assert 'with st.expander("🧹 Reset gali / laureatów"' in src
assert 'RESETUJ WSZYSTKICH LAUREATÓW I GALĘ' in src
# Reset must not be hidden behind the old `if GALA_TEST_MODE:` wrapper anymore.
frag = src[src.index('with st.expander("🧹 Reset gali / laureatów"')-80:src.index('with st.expander("🧹 Reset gali / laureatów"')+80]
assert 'if GALA_TEST_MODE:' not in frag
assert 'close_awards_season_disabled_' in src
assert 'Po kliknięciu „ZAKOŃCZ GALĘ” ten przycisk się odblokuje.' in src
print('PASS awards_admin_controls_r32_smoke')

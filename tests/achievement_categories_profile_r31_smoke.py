import re
from collections import Counter
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
db=(ROOT/'database.py').read_text(encoding='utf-8')
mobile=(ROOT/'mobile'/'src'/'StatsScreen.tsx').read_text(encoding='utf-8')
app=(ROOT/'app.py').read_text(encoding='utf-8')

block=db[db.index('def _achievement_catalog'):db.index('def achievement_center')]
pairs=re.findall(r'\{"key":"([^"]+)".*?"category":"([^"]+)"\}',block)
assert len(pairs)==53,len(pairs)
counts=Counter(cat for _,cat in pairs)
assert counts==Counter({'career':10,'rivalry':9,'match':10,'hero':8,'tournament':8,'teams':5,'finance':3}),counts

labels=('🏅 Kariera','🔥 Forma i rywalizacja','🎮 Mecze','🎯 Bohaterowie i wydarzenia','🏆 Turnieje','👕 Drużyny','💰 Finanse')
for label in labels:
    assert label in mobile,label
    assert label in app,label
for old in ('📈 Progres i serie','🧩 Events','📊 Summary','⚔️ H2H','🏆 Turnieje i kariera'):
    assert old not in mobile,old

# Profile itself must stay compact: count plus two entry points, no inline badge wall.
assert 'badgeCount' in mobile and 'ZDOBYTE' in mobile
assert '🎖️ ZOBACZ MOJE' in mobile and "setBadgeView('mine')" in mobile
assert '🏅 ZOBACZ WSZYSTKIE' in mobile and "setBadgeView('all')" in mobile
assert 'Dotknij zdobytej odznaki' not in mobile
assert 'openBadges' not in mobile
assert "mode==='mine'?allItems.filter" in mobile
assert "visibleGroups=mode==='mine'?available.filter" in mobile
assert '<Muted>{wonInGroup}/{allItems.length} zdobytych</Muted>' in mobile

# Streamlit profile follows the same compact principle instead of rendering the full badge list inline.
assert 'with st.popover("🎖️ Zobacz moje"' in app
assert 'with st.popover("🏅 Zobacz wszystkie"' in app
assert '🔒 Odznaki do zdobycia' not in app
print('achievement_categories_profile_r31_smoke PASS')

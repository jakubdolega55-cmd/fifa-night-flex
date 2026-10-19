from pathlib import Path
root=Path(__file__).resolve().parents[1]
s=(root/'ui.py').read_text(encoding='utf-8')
assert "const livePool=(meta.remaining_wheel_pool||[])" in s
assert "wheelMarkup(livePool.length?livePool:" in s
print('PASS TV idle wheel uses backend remaining_wheel_pool before first spin')

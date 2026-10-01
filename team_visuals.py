from __future__ import annotations

import base64
import html
from functools import lru_cache
from pathlib import Path

# Lightweight remote crest library. Browsers / React Native cache these small images;
# if a Wild Card has no known mapping, UI falls back to initials instead of failing.
_CLUBS = {
    'real madryt': ('spain','real-madrid'),
    'real madrid': ('spain','real-madrid'),
    'psg': ('france','paris-saint-germain'),
    'paris saint-germain': ('france','paris-saint-germain'),
    'bayern monachium': ('germany','bayern-munchen'),
    'bayern munich': ('germany','bayern-munchen'),
    'bayern münchen': ('germany','bayern-munchen'),
    'fc barcelona': ('spain','barcelona'),
    'barcelona': ('spain','barcelona'),
    'arsenal': ('england','arsenal'),
    'manchester city': ('england','manchester-city'),
    'liverpool': ('england','liverpool'),
    'liverpool fc': ('england','liverpool'),
    'atletico': ('spain','atletico-madrid'),
    'atletico madrid': ('spain','atletico-madrid'),
    'atlético': ('spain','atletico-madrid'),
    'atlético madrid': ('spain','atletico-madrid'),
    'atlético de madrid': ('spain','atletico-madrid'),
    'inter': ('italy','inter'),
    'inter milan': ('italy','inter'),
    'lombardia fc': ('italy','inter'),
    'man united': ('england','manchester-united'),
    'man utd': ('england','manchester-united'),
    'manchester utd': ('england','manchester-united'),
    'manchester united': ('england','manchester-united'),
    'bvb': ('germany','borussia-dortmund'),
    'bvb 09': ('germany','borussia-dortmund'),
    'borussia dortmund': ('germany','borussia-dortmund'),
    'napoli': ('italy','napoli'),
    'chelsea': ('england','chelsea'),
    'tottenham': ('england','tottenham'),
    'tottenham hotspur': ('england','tottenham'),
    'ac milan': ('italy','milan'),
    'milan': ('italy','milan'),
    'bayer leverkusen': ('germany','bayer-leverkusen'),
}

_FLAGS = {
    'hiszpania':'spain', 'spain':'spain',
    'anglia':'england', 'england':'england',
    'brazylia':'brazil', 'brazil':'brazil',
    'niemcy':'germany', 'germany':'germany',
    'portugalia':'portugal', 'portugal':'portugal',
    'włochy':'italy', 'wlochy':'italy', 'italy':'italy',
    'argentyna':'argentina', 'argentina':'argentina',
    'holandia':'netherlands', 'netherlands':'netherlands',
    'belgia':'belgium', 'belgium':'belgium',
    'chorwacja':'croatia', 'croatia':'croatia',
    'dania':'denmark', 'denmark':'denmark',
    'maroko':'morocco', 'morocco':'morocco',
    'turcja':'turkey', 'turkey':'turkey',
    'szwajcaria':'switzerland', 'switzerland':'switzerland',
}

_ASSET_ROOT = Path(__file__).resolve().parent / 'assets' / 'teams'


@lru_cache(maxsize=64)
def _png_data_uri(path: str) -> str | None:
    file_path = Path(path)
    try:
        raw = file_path.read_bytes()
    except OSError:
        return None
    return 'data:image/png;base64,' + base64.b64encode(raw).decode('ascii')



def _norm(value: str | None) -> str:
    return ' '.join(str(value or '').strip().casefold().split())


def team_flag(value: str | None) -> str | None:
    return _FLAGS.get(_norm(value))


def team_flag_data_uri(value: str | None) -> str | None:
    slug = team_flag(value)
    if not slug:
        return None
    return _png_data_uri(str(_ASSET_ROOT / 'flags' / f'{slug}.png'))


def team_logo_url(value: str | None, size: int = 256) -> str | None:
    data = _CLUBS.get(_norm(value))
    if not data:
        return None
    country, slug = data
    return f'https://football-logos.cc/logos/{country}/{int(size)}x{int(size)}/{slug}.png'


def team_initials(value: str | None) -> str:
    words=[x for x in str(value or '').replace('-', ' ').split() if x]
    if not words:
        return 'FC'
    if len(words)==1:
        return words[0][:3].upper()
    return ''.join(x[0] for x in words[:3]).upper()


def team_visual_html(value: str | None, size: int = 64, extra_style: str = '') -> str:
    name=str(value or '')
    flag_uri=team_flag_data_uri(name)
    if flag_uri:
        return (
            f"<div class='team-flag' style='width:{size}px;height:{size}px;display:grid;place-items:center;{extra_style}'>"
            f"<img src='{flag_uri}' alt='{html.escape(name)}' title='{html.escape(name)}' "
            f"style='width:100%;height:100%;object-fit:contain;display:block;filter:drop-shadow(0 4px 7px rgba(0,0,0,.22))'>"
            f"</div>"
        )
    url=team_logo_url(name, 256)
    initials=html.escape(team_initials(name))
    if url:
        return (
            f"<div class='team-visual' style='width:{size}px;height:{size}px;{extra_style}'>"
            f"<img src='{html.escape(url)}' alt='{html.escape(name)}' title='{html.escape(name)}' loading='eager' decoding='async' "
            f"style='width:100%;height:100%;object-fit:contain;display:block;filter:drop-shadow(0 4px 7px rgba(0,0,0,.28))' "
            f"onerror=\"this.style.display='none';this.nextElementSibling.style.display='grid'\">"
            f"<span style='display:none;width:100%;height:100%;place-items:center;border-radius:50%;background:#14263a;color:#dbeafe;font-weight:900;font-size:{max(11,size//4)}px'>{initials}</span>"
            f"</div>"
        )
    return (
        f"<div class='team-visual' style='width:{size}px;height:{size}px;display:grid;place-items:center;border-radius:50%;"
        f"background:#14263a;border:1px solid #31506b;color:#dbeafe;font-weight:900;font-size:{max(11,size//4)}px;{extra_style}'>{initials}</div>"
    )

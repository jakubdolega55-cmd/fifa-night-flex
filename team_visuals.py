from __future__ import annotations

import base64
import html
from functools import lru_cache
from pathlib import Path

# Runtime visuals are fully local. Club crests are vendored into assets/teams/clubs
# before deploy/build. Unknown/manual Wild Cards fall back to initials.
_CLUBS = {
    'real madryt': 'real-madrid',
    'real madrid': 'real-madrid',
    'psg': 'paris-saint-germain',
    'paris saint-germain': 'paris-saint-germain',
    'bayern monachium': 'bayern-munchen',
    'bayern munich': 'bayern-munchen',
    'bayern münchen': 'bayern-munchen',
    'fc barcelona': 'barcelona',
    'barcelona': 'barcelona',
    'arsenal': 'arsenal',
    'manchester city': 'manchester-city',
    'liverpool': 'liverpool',
    'liverpool fc': 'liverpool',
    'atletico': 'atletico-madrid',
    'atletico madrid': 'atletico-madrid',
    'atlético': 'atletico-madrid',
    'atlético madrid': 'atletico-madrid',
    'atlético de madrid': 'atletico-madrid',
    'inter': 'inter',
    'inter milan': 'inter',
    'lombardia fc': 'inter',
    'man united': 'manchester-united',
    'man utd': 'manchester-united',
    'manchester utd': 'manchester-united',
    'manchester united': 'manchester-united',
    'bvb': 'borussia-dortmund',
    'bvb 09': 'borussia-dortmund',
    'borussia dortmund': 'borussia-dortmund',
    'tottenham': 'tottenham',
    'tottenham hotspur': 'tottenham',
    'ac milan': 'milan',
    'milan': 'milan',
    'bayer leverkusen': 'bayer-leverkusen',
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


@lru_cache(maxsize=128)
def _png_data_uri(path: str) -> str | None:
    file_path = Path(path)
    try:
        raw = file_path.read_bytes()
    except OSError:
        return None
    if not raw.startswith(b'\x89PNG\r\n\x1a\n'):
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


def team_logo_slug(value: str | None) -> str | None:
    return _CLUBS.get(_norm(value))


def team_logo_data_uri(value: str | None) -> str | None:
    slug = team_logo_slug(value)
    if not slug:
        return None
    return _png_data_uri(str(_ASSET_ROOT / 'clubs' / f'{slug}.png'))


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
    logo_uri=team_logo_data_uri(name)
    initials=html.escape(team_initials(name))
    if logo_uri:
        return (
            f"<div class='team-visual' style='width:{size}px;height:{size}px;{extra_style}'>"
            f"<img src='{logo_uri}' alt='{html.escape(name)}' title='{html.escape(name)}' "
            f"style='width:100%;height:100%;object-fit:contain;display:block;filter:drop-shadow(0 4px 7px rgba(0,0,0,.28))'>"
            f"</div>"
        )
    return (
        f"<div class='team-visual' style='width:{size}px;height:{size}px;display:grid;place-items:center;border-radius:50%;"
        f"background:#14263a;border:1px solid #31506b;color:#dbeafe;font-weight:900;font-size:{max(11,size//4)}px;{extra_style}'>{initials}</div>"
    )

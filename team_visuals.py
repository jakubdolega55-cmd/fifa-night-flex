from __future__ import annotations

import html

# Lightweight remote crest library. Browsers / React Native cache these small images;
# if a Wild Card has no known mapping, UI falls back to initials instead of failing.
_CLUBS = {
    'real madryt': ('spain','real-madrid'),
    'real madrid': ('spain','real-madrid'),
    'psg': ('france','paris-saint-germain'),
    'paris saint-germain': ('france','paris-saint-germain'),
    'bayern monachium': ('germany','bayern-munchen'),
    'bayern munich': ('germany','bayern-munchen'),
    'fc barcelona': ('spain','barcelona'),
    'barcelona': ('spain','barcelona'),
    'arsenal': ('england','arsenal'),
    'manchester city': ('england','manchester-city'),
    'liverpool': ('england','liverpool'),
    'liverpool fc': ('england','liverpool'),
    'atletico': ('spain','atletico-madrid'),
    'atletico madrid': ('spain','atletico-madrid'),
    'atlético': ('spain','atletico-madrid'),
    'inter': ('italy','inter'),
    'man united': ('england','manchester-united'),
    'manchester united': ('england','manchester-united'),
    'bvb': ('germany','borussia-dortmund'),
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
    'hiszpania':'🇪🇸', 'spain':'🇪🇸',
    'anglia':'🏴', 'england':'🏴',
    'brazylia':'🇧🇷', 'brazil':'🇧🇷',
    'niemcy':'🇩🇪', 'germany':'🇩🇪',
    'portugalia':'🇵🇹', 'portugal':'🇵🇹',
    'włochy':'🇮🇹', 'wlochy':'🇮🇹', 'italy':'🇮🇹',
    'argentyna':'🇦🇷', 'argentina':'🇦🇷',
    'holandia':'🇳🇱', 'netherlands':'🇳🇱',
    'belgia':'🇧🇪', 'belgium':'🇧🇪',
    'chorwacja':'🇭🇷', 'croatia':'🇭🇷',
    'dania':'🇩🇰', 'denmark':'🇩🇰',
    'maroko':'🇲🇦', 'morocco':'🇲🇦',
    'turcja':'🇹🇷', 'turkey':'🇹🇷',
    'szwajcaria':'🇨🇭', 'switzerland':'🇨🇭',
}


def _norm(value: str | None) -> str:
    return ' '.join(str(value or '').strip().casefold().split())


def team_flag(value: str | None) -> str | None:
    return _FLAGS.get(_norm(value))


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
    flag=team_flag(name)
    if flag:
        return f"<div class='team-flag' style='font-size:{max(28,int(size*.72))}px;line-height:{size}px;{extra_style}'>{flag}</div>"
    url=team_logo_url(name, 256)
    initials=html.escape(team_initials(name))
    if url:
        return (
            f"<div class='team-visual' style='width:{size}px;height:{size}px;{extra_style}'>"
            f"<img src='{html.escape(url)}' alt='{html.escape(name)}' loading='eager' "
            f"style='width:100%;height:100%;object-fit:contain;display:block' "
            f"onerror=\"this.style.display='none';this.nextElementSibling.style.display='grid'\">"
            f"<span style='display:none;width:100%;height:100%;place-items:center;border-radius:50%;background:#14263a;color:#dbeafe;font-weight:900;font-size:{max(11,size//4)}px'>{initials}</span>"
            f"</div>"
        )
    return (
        f"<div class='team-visual' style='width:{size}px;height:{size}px;display:grid;place-items:center;border-radius:50%;"
        f"background:#14263a;border:1px solid #31506b;color:#dbeafe;font-weight:900;font-size:{max(11,size//4)}px;{extra_style}'>{initials}</div>"
    )

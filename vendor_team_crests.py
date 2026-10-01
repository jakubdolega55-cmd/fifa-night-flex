from __future__ import annotations

import argparse
import json
import shutil
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent
MANIFEST = json.loads((ROOT / 'team_crest_sources.json').read_text(encoding='utf-8'))
PNG_MAGIC = b'\x89PNG\r\n\x1a\n'


def _sources(meta: dict[str, str]) -> list[str]:
    country = meta['country']
    remote = meta['remote']
    footy = meta['footy']
    return [
        f'https://football-logos.cc/logos/{country}/256x256/{remote}.png',
        f'https://www.footylogos.com/dls/logo/{footy}.png',
    ]


def _download(url: str) -> bytes:
    req = urllib.request.Request(url, headers={'User-Agent': 'FIFA-Night-Asset-Vendor/1.1.3'})
    with urllib.request.urlopen(req, timeout=25) as response:
        data = response.read()
    if not data.startswith(PNG_MAGIC):
        raise ValueError(f'not a PNG: {url}')
    return data


def vendor(*, root_only: bool = False, force: bool = False) -> None:
    root_dir = ROOT / 'assets' / 'teams' / 'clubs'
    mobile_dir = ROOT / 'mobile' / 'assets' / 'teams' / 'clubs'
    root_dir.mkdir(parents=True, exist_ok=True)
    mobile_dir.mkdir(parents=True, exist_ok=True)

    failures: list[str] = []
    for slug, meta in MANIFEST.items():
        root_file = root_dir / f'{slug}.png'
        if force or not (root_file.exists() and root_file.read_bytes().startswith(PNG_MAGIC)):
            last_error: Exception | None = None
            for url in _sources(meta):
                try:
                    root_file.write_bytes(_download(url))
                    print(f'[OK] {slug} <- {url}')
                    last_error = None
                    break
                except (OSError, ValueError, urllib.error.URLError) as exc:
                    last_error = exc
                    print(f'[retry] {slug}: {exc}')
            if last_error is not None:
                failures.append(f'{slug}: {last_error}')
                continue
        else:
            print(f'[cached] {slug}')

        if not root_only:
            shutil.copy2(root_file, mobile_dir / root_file.name)

    if failures:
        raise SystemExit('Nie udalo sie pobrac herbów:\n- ' + '\n- '.join(failures))

    print(f'Gotowe: {len(MANIFEST)} lokalnych herbów' + (' (Streamlit)' if root_only else ' (Streamlit + mobile)'))


def main() -> None:
    parser = argparse.ArgumentParser(description='Vendor local FIFA Night team crests before build/deploy.')
    parser.add_argument('--root-only', action='store_true', help='Only populate assets/teams/clubs for Streamlit.')
    parser.add_argument('--force', action='store_true', help='Redownload even if a valid local PNG exists.')
    args = parser.parse_args()
    vendor(root_only=args.root_only, force=args.force)


if __name__ == '__main__':
    main()

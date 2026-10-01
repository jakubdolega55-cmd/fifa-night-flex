# FIFA Night — Team visuals / Live Form polish — 2026-10-01

Base: TEAM-VISUALS-LIVE-FORM V14 checkpoint.

Polish only; tournament logic and API contract unchanged.

- Club crest aliases expanded (Bayern München, Atlético de Madrid, Lombardia FC / Inter, Man Utd, BVB 09).
- England national-team flag changed from generic black flag to the real England flag Unicode sequence.
- Mobile crest images now request force-cache and use a subtle shadow; fallback remains initials.
- LIVE FORM renamed to FORMA LIVE and made more visible.
- W = green, R = yellow, P = red with stronger contrast.
- Form always reserves five slots; missing older results use muted dashes so both rows stay aligned.
- Same form treatment applied to Streamlit/TV.
- Android versionCode remains 14 because V14 APK has not been built yet; this polish is part of the same V14 release.

- Crests still use the existing lightweight remote source, but mobile requests force-cache and every client keeps the initials fallback. Local bundling can be done later without changing tournament logic.

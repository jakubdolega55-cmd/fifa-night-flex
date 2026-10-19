# R20 — Mobile/PWA Awards seasons

- Mobile Awards selector uses Sezon 1 / Sezon 2 / ... instead of calendar years.
- Current season is loaded from backend; closed seasons are read from frozen R19 snapshots.
- Gala controls are available only for the current season.
- Season PNG endpoints and filenames replace year-based UI exports.
- Share cards say SEZON W LICZBACH / Sezon N.
- Player profile Awards use season labels and avoid duplicate legacy Season 1 selections.
- Legacy year API routes remain for backward compatibility.

- Android `versionCode` bumped from 14 to 15 because this release changes the installed mobile client.

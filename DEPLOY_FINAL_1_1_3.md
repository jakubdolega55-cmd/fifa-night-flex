# FIFA Night 1.1.3 — final deployment

## Gala
Final mode is OFF by default and in render.yaml: `FIFA_GALA_TEST_MODE=0`.
The Gala navigation appears only when all required laureates are selected. The test-only bulk reset is hidden/blocked.

## Summary
The mobile app already sends up to 6 screenshots in one `scan-preview` request. Upload Events and Summary from the same match together. Summary classification, parsing, storage and Awards weighting are server-side. After real FC27 screenshots are reviewed, parser/field/weight changes should require only backend redeploy (`mobile_api.py` / `database.py`) as long as the upload contract remains unchanged.

## APK
Use the separate `FIFA-NIGHT-APK-1.1.3-BUILD-READY-FINAL.zip`.
Windows: `npm.cmd install`, `npm.cmd run check`, `npx.cmd expo-doctor`, then `npx.cmd eas-cli@latest build --platform android --profile preview`.

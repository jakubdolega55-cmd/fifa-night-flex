# FIFA Night 1.1.3 — final build candidate

- Gala test mode defaults to OFF (`FIFA_GALA_TEST_MODE=0`).
- Gala is visible only after all required laureates are validly selected.
- Test-only reset-all-laureates is hidden/blocked when test mode is off.
- Mobile scan flow already accepts multiple screenshots in one request. Events + Summary can be uploaded together; Summary parsing/storage/Awards logic is server-side.
- Future tuning of Summary field mapping/parser/weights should therefore require backend deployment only, not a new APK, provided the upload flow and mobile UI contract remain unchanged.
- FC27 nationals and current FC27 club pool are included.

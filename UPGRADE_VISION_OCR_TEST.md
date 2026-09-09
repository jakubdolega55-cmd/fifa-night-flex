# FIFA Night — Google Vision OCR test

## Co dodano

- `mobile_api.py` — wspólny FastAPI z prototypowym endpointem `POST /api/v1/vision/test-scan`.
- Endpoint przyjmuje 1–2 zdjęcia JPG/PNG/WEBP i wysyła je do Google Cloud Vision `TEXT_DETECTION`.
- Endpoint niczego nie zapisuje do Neona.
- Endpoint wymaga nagłówka `X-Admin-Password` zgodnego z `ADMIN_PASSWORD` ustawionym na Renderze.
- `requirements-api.txt` — zależności FastAPI + `httpx` + `python-multipart`.
- `render.yaml` — dopisany sekret `GOOGLE_VISION_API_KEY`.
- `app.py` — w Ustawieniach, po włączeniu sterowania, pojawia się test Google OCR.
- Tester pokazuje zdjęcia, surowy tekst OCR i czas odpowiedzi.

## Render

Ustawione sekrety:
- `DATABASE_URL`
- `ADMIN_PASSWORD`
- `MOBILE_TOKEN_SECRET`
- `GOOGLE_VISION_API_KEY`

Start command:
`uvicorn mobile_api:app --host 0.0.0.0 --port $PORT`

Build command:
`pip install -r requirements-api.txt`

## Streamlit

Do pierwszego testu adres Rendera można wkleić ręcznie w Ustawieniach.
Później można dodać do Streamlit Secrets:

`FIFA_NIGHT_API_URL = "https://twoj-serwis.onrender.com"`

`ADMIN_PASSWORD` w Streamlit Secrets powinno być takie samo jak `ADMIN_PASSWORD` na Renderze.

## Ważne

Na tym etapie to tylko OCR. Nie ma jeszcze parsera wyniku/strzelców i nie ma zapisu meczu.

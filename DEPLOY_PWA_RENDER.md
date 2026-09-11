# Publikacja FIFA Night PWA na Render

Repo zawiera gotową drugą usługę w `render.yaml`:

- `fifa-night-api` — FastAPI,
- `fifa-night-pwa` — statyczna aplikacja Expo Web/PWA.

## Jeśli używasz Blueprint

Po pushu `render.yaml` zsynchronizuj Blueprint w Render. Render utworzy/odświeży usługę `fifa-night-pwa`.

## Jeśli nie używasz Blueprint

Utwórz **Static Site** z tego samego repo i ustaw:

- Root Directory: `mobile`
- Build Command: `npm install && npm run build:web`
- Publish Directory: `dist`
- Environment: `NODE_VERSION=22.16.0`
- Environment: `EXPO_PUBLIC_API_URL=https://fifa-night-api.onrender.com`
- Rewrite: `/*` -> `/index.html`

Po deployu Render poda publiczny adres HTTPS. Ten adres otwierasz na iPhonie w Safari i wybierasz `Udostępnij -> Dodaj do ekranu początkowego`.

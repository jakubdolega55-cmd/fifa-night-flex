# Vision AI Compare — hotfix 2

Testowy moduł rozpoznawania ekranów EA FC został rozszerzony z Google OCR o:

- OpenAI GPT-5.6 Luna (vision),
- Gemini 3.8 Flash (vision),
- obsługę 1–5 screenów z zakładki Wydarzenia,
- wspólny JSON zdarzeń,
- rozróżnienie gola / kartki / zmiany,
- deduplikację nakładających się screenów po stronie modelu,
- pomiar czasu i tokenów oraz orientacyjnego kosztu.

Nic nie zapisuje do Neona.

Wymagane zmienne Render:
- GOOGLE_VISION_API_KEY — tylko dla Google OCR,
- OPENAI_API_KEY — dla OpenAI,
- GEMINI_API_KEY — dla Gemini.

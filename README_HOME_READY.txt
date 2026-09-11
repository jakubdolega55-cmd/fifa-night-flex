FIFA NIGHT RC2 + iPHONE PWA — HOME READY

CO TO JEST
- Android nadal: natywna APK z Expo/EAS.
- iPhone: PWA instalowane z Safari -> Dodaj do ekranu poczatkowego.
- Streamlit: laptop/TV/admin.
- Wszystkie korzystaja z tego samego FastAPI/Render/Neon.

CO MOZESZ ZROBIC TERAZ, BEZ TERMINALA
1. Pobierz i zachowaj cala paczke HOME READY.
2. Nie instaluj niczego na komputerze sluzbowym.
3. Jesli masz dostep do GitHub/Render przez przegladarke, mozesz tylko sprawdzic:
   - jakie repo jest podlaczone do Render,
   - czy API na Render nazywa sie fifa-night-api,
   - czy Auto-Deploy jest wlaczony.
4. Nie tworz nowej uslugi PWA przed wrzuceniem tego kodu na GitHub.

W DOMU — NAJBEZPIECZNIEJSZA KOLEJNOSC
A. Skopiuj/rozpakuj te pliki do swojego ISTNIEJACEGO repo FIFA Night.
   Nie pracuj w nowym przypadkowym git init, jesli masz juz repo polaczone z GitHub/Render.

B. Uruchom BUILD_PWA_HOME.cmd (dwuklik) ALBO w terminalu w katalogu glownym:
   cd mobile
   npm.cmd install
   npm.cmd run check
   npx.cmd expo-doctor
   npm.cmd run build:web

C. Sukces oznacza:
   - TypeScript bez bledow,
   - Expo Doctor wszystkie checki PASS,
   - na koncu: PWA VERIFY: ALL CHECKS PASSED,
   - istnieje mobile\dist\index.html.

D. Wroc do katalogu glownego repo i zrob push do GitHub.
   Mozesz uzyc PUSH_TO_GITHUB_AFTER_BUILD.cmd, ALE tylko jesli pracujesz w swoim
   istniejacym repo z poprawnym remote.

E. Render
   render.yaml zawiera gotowa usluge:
   - fifa-night-api
   - fifa-night-pwa (Static Site)

   Dla PWA:
   Root Directory: mobile
   Build: npm install && npm run build:web
   Publish: dist
   EXPO_PUBLIC_API_URL=https://fifa-night-api.onrender.com
   Rewrite: /* -> /index.html

   Jesli korzystasz z Render Blueprint, zsynchronizuj Blueprint po pushu.
   Jesli obecne API bylo tworzone recznie, NIE kasuj go. Utworz tylko osobny Static Site
   fifa-night-pwa z powyzszymi ustawieniami.

F. Po udanym deployu dostaniesz URL HTTPS, np.
   https://fifa-night-pwa.onrender.com

G. iPhone
   Safari -> otworz URL -> Udostepnij -> Dodaj do ekranu poczatkowego -> Dodaj.

NIE WYSYLAJ KOLEDZE ZIP-A.
Wysylasz mu dopiero publiczny link HTTPS po udanym deployu.

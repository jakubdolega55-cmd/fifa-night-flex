@echo off
setlocal EnableExtensions
cd /d "%~dp0mobile"

echo ============================================================
echo FIFA NIGHT - iPhone PWA - BUILD HOME
echo ============================================================
echo.

where node >nul 2>nul
if errorlevel 1 goto NODE_MISSING
where npm.cmd >nul 2>nul
if errorlevel 1 goto NODE_MISSING

echo [0/5] Srodowisko
node -v
npm.cmd -v

echo.
echo [1/5] Instalacja zaleznosci...
call npm.cmd install
if errorlevel 1 goto FAIL

echo.
echo [2/5] TypeScript...
call npm.cmd run check
if errorlevel 1 goto FAIL

echo.
echo [3/5] Expo Doctor...
call npx.cmd expo-doctor
if errorlevel 1 goto FAIL

echo.
echo [4/5] Produkcyjny build PWA...
call npm.cmd run build:web
if errorlevel 1 goto FAIL

echo.
echo [5/5] Kontrola wyniku...
if not exist "dist\index.html" goto FAIL
if not exist "dist\manifest.json" goto FAIL

echo.
echo ============================================================
echo GOTOWE - PWA ZBUDOWANE POPRAWNIE
echo Folder: %CD%\dist
echo ============================================================
echo.
echo Nastepny krok: push repo na GitHub. Render zbuduje i opublikuje
ECHO usluge fifa-night-pwa zgodnie z render.yaml.
echo.
pause
exit /b 0

:NODE_MISSING
echo.
echo BLAD: Node.js/npm nie sa dostepne w PATH.
echo Zainstaluj Node.js 22 LTS i otworz nowy terminal.
pause
exit /b 2

:FAIL
echo.
echo ============================================================
echo BUILD ZATRZYMANY - NIE PUSHUJ TEJ WERSJI JAKO GOTOWEJ.
echo Zrob screenshot ostatnich komunikatow i podeslij do ChatGPT.
echo ============================================================
pause
exit /b 1

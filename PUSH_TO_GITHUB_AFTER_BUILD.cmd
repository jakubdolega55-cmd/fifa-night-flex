@echo off
setlocal EnableExtensions
cd /d "%~dp0"

echo ============================================================
echo FIFA NIGHT - PUSH DO ISTNIEJACEGO REPO GITHUB
echo ============================================================

git rev-parse --is-inside-work-tree >nul 2>nul
if errorlevel 1 goto NOT_REPO

echo Repo:
git remote -v
echo.
echo Sprawdz zmiany:
git status --short
echo.
set /p GO=Czy to jest WLASCIWE repo FIFA Night i chcesz zrobic push? [T/N]: 
if /I not "%GO%"=="T" exit /b 0

git add .
if errorlevel 1 goto FAIL

git commit -m "FIFA Night RC2 + iPhone PWA beta"
if errorlevel 1 (
  echo.
  echo Commit nie powstal. Jesli widzisz 'nothing to commit', mozesz kontynuowac push recznie.
)

git push
if errorlevel 1 goto FAIL

echo.
echo PUSH GOTOWY. Jesli Render ma Auto-Deploy, obserwuj deploy API/PWA.
pause
exit /b 0

:NOT_REPO
echo.
echo BLAD: ten folder nie jest Twoim istniejacym repo GitHub.
echo Najbezpieczniej skopiuj zawartosc tej paczki DO istniejacego klonu repo FIFA Night,
echo a dopiero potem uruchom ten skrypt z katalogu glownego repo.
pause
exit /b 2

:FAIL
echo.
echo PUSH NIE ZAKONCZYL SIE POPRAWNIE. Nie kombinuj dalej - podeslij komunikat.
pause
exit /b 1

@echo off
setlocal
cd /d "%~dp0mobile"
echo === FIFA NIGHT 1.1.3 - APK BUILD ===
call npm.cmd install || goto :err
call npm.cmd run check || goto :err
call npx.cmd expo-doctor || goto :err
call npx.cmd eas-cli@latest whoami || goto :login
:build
call npx.cmd eas-cli@latest build --platform android --profile preview || goto :err
echo.
echo GOTOWE. EAS poda link do APK.
pause
exit /b 0
:login
echo.
echo Nie jestes zalogowany do EAS. Logowanie...
call npx.cmd eas-cli@latest login || goto :err
call npx.cmd eas-cli@latest whoami || goto :err
goto :build
:err
echo.
echo COS SIE WYKRZACZYLO. Sprawdz komunikat wyzej.
pause
exit /b 1

@echo off
setlocal
cd /d "%~dp0mobile"
echo === FIFA NIGHT 1.1.3 / V14 APK BUILD ===
where npm >nul 2>nul || (echo ERROR: npm not found & pause & exit /b 1)
where npx >nul 2>nul || (echo ERROR: npx not found & pause & exit /b 1)
if not exist node_modules (
  echo Installing dependencies...
  call npm.cmd install || (pause & exit /b 1)
)
echo Preparing local team crests...
call npm.cmd run vendor:teams || (pause & exit /b 1)
echo Running TypeScript check...
call npm.cmd run check || (pause & exit /b 1)
echo Running Expo Doctor...
call npx.cmd expo-doctor || (pause & exit /b 1)
echo Starting EAS preview APK build...
call npx.cmd eas-cli@latest build --platform android --profile preview
pause

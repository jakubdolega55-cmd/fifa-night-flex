$ErrorActionPreference = 'Stop'
Write-Host '=== FIFA Night PWA / iPhone ==='
Write-Host '1/4 npm install'
npm.cmd install
Write-Host '2/4 TypeScript'
npm.cmd run check
Write-Host '3/4 Expo Doctor'
npx.cmd expo-doctor
Write-Host '4/4 Expo Web export + PWA metadata'
npm.cmd run build:web
Write-Host ''
Write-Host 'GOTOWE: mobile\dist\'

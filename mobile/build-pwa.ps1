$ErrorActionPreference = 'Stop'
Write-Host '=== FIFA Night PWA / iPhone ==='
Write-Host '1/4 npm install'
npm.cmd install
Write-Host '2/5 Lokalne herby'
npm.cmd run vendor:teams
Write-Host '3/5 TypeScript'
npm.cmd run check
Write-Host '4/5 Expo Doctor'
npx.cmd expo-doctor
Write-Host '5/5 Expo Web export + PWA metadata'
npm.cmd run build:web
Write-Host ''
Write-Host 'GOTOWE: mobile\dist\'

$ErrorActionPreference = 'Stop'
Write-Host '=== FIFA Night 1.1.3 / V14 PWA ==='
Write-Host '1/4 npm install'
npm.cmd install
Write-Host '2/4 TypeScript'
npm.cmd run check
Write-Host '3/4 Expo Doctor'
npx.cmd expo-doctor
Write-Host '4/4 Expo Web export + lokalne herby + PWA metadata'
npm.cmd run build:web
Write-Host ''
Write-Host 'GOTOWE: mobile\dist\'

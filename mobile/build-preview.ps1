$ErrorActionPreference = "Stop"

Write-Host "FIFA Night Mobile 1.1.3 / V14 - APK checks"
Write-Host "1/5 npm install"
npm.cmd install

Write-Host "2/5 Weryfikacja lokalnych herbow"
npm.cmd run verify:teams

Write-Host "3/5 TypeScript"
npm.cmd run check

Write-Host "4/5 Expo Doctor"
npx.cmd expo-doctor

Write-Host "5/5 EAS preview APK"
npx.cmd eas-cli@latest build --platform android --profile preview

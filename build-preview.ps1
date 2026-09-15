$ErrorActionPreference = "Stop"

Write-Host "FIFA Night Mobile 1.0 - final APK checks"
Write-Host "1/4 npm install"
npm.cmd install

Write-Host "2/4 TypeScript"
npm.cmd run check

Write-Host "3/4 Expo Doctor"
npx.cmd expo-doctor

Write-Host "4/4 EAS preview APK"
npx.cmd eas-cli@latest build --platform android --profile preview

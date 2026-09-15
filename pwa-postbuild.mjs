import fs from 'node:fs';
import path from 'node:path';

const file=path.resolve('dist/index.html');
if(!fs.existsSync(file))throw new Error('Brak dist/index.html — najpierw uruchom expo export --platform web.');
let html=fs.readFileSync(file,'utf8');
const tags=`\n<link rel="manifest" href="./manifest.json" />\n<link rel="apple-touch-icon" href="./apple-touch-icon.png" />\n<meta name="theme-color" content="#07111f" />\n<meta name="apple-mobile-web-app-capable" content="yes" />\n<meta name="apple-mobile-web-app-status-bar-style" content="black-translucent" />\n<meta name="apple-mobile-web-app-title" content="FIFA Night" />\n<style>html,body{margin:0;background:#07111f;min-height:100%;overscroll-behavior-y:none}body{min-height:100dvh}#root{min-height:100dvh;max-width:680px;margin:0 auto;background:#07111f}@media(display-mode:standalone){#root{box-sizing:border-box;padding-top:env(safe-area-inset-top);padding-bottom:env(safe-area-inset-bottom)}}</style>\n`;
html=html.replace(/(<meta[^>]+name=[\"']viewport[\"'][^>]+content=[\"'])([^\"']*)([\"'][^>]*>)/i,(m,a,c,z)=>c.includes('viewport-fit=cover')?m:`${a}${c}, viewport-fit=cover${z}`);
if(!html.includes('rel="manifest"'))html=html.replace('</head>',`${tags}</head>`);
fs.writeFileSync(file,html);
console.log('PWA metadata injected into dist/index.html');

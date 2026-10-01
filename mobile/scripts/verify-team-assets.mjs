import fs from 'node:fs';
import path from 'node:path';
import {fileURLToPath} from 'node:url';

const here=path.dirname(fileURLToPath(import.meta.url));
const mobileRoot=path.resolve(here,'..');
const clubDir=path.join(mobileRoot,'assets','teams','clubs');
const expected=[
  'real-madrid','paris-saint-germain','bayern-munchen','barcelona','arsenal',
  'manchester-city','liverpool','atletico-madrid','inter','manchester-united',
  'borussia-dortmund','tottenham','milan','bayer-leverkusen'
];
const missing=[];
for(const slug of expected){
  const file=path.join(clubDir,`${slug}.png`);
  if(!fs.existsSync(file)) missing.push(slug);
}
if(missing.length){
  console.error(`ERROR: Brak lokalnych herbów: ${missing.join(', ')}`);
  process.exit(1);
}
console.log(`Local team assets: OK (${expected.length} club crests)`);

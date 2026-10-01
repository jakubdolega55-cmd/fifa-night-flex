import fs from 'node:fs/promises';
import path from 'node:path';
import {fileURLToPath} from 'node:url';

const here=path.dirname(fileURLToPath(import.meta.url));
const mobileRoot=path.resolve(here,'..');
const repoRoot=path.resolve(mobileRoot,'..');
const manifest=JSON.parse(await fs.readFile(path.join(repoRoot,'team_crest_sources.json'),'utf8'));
const outDir=path.join(mobileRoot,'assets','teams','clubs');
await fs.mkdir(outDir,{recursive:true});
const magic=Buffer.from([0x89,0x50,0x4e,0x47,0x0d,0x0a,0x1a,0x0a]);
const isPng=b=>b.length>=8&&b.subarray(0,8).equals(magic);

async function fetchPng(url){
 const res=await fetch(url,{headers:{'user-agent':'FIFA-Night-Asset-Vendor/1.1.3'}});
 if(!res.ok)throw new Error(`${res.status} ${res.statusText}`);
 const buf=Buffer.from(await res.arrayBuffer());
 if(!isPng(buf))throw new Error('response is not PNG');
 return buf;
}

const failures=[];
for(const [slug,m] of Object.entries(manifest)){
 const file=path.join(outDir,`${slug}.png`);
 let cached=false;
 try{cached=isPng(await fs.readFile(file));}catch{}
 if(cached){console.log(`[cached] ${slug}`);continue;}
 const urls=[
  `https://football-logos.cc/logos/${m.country}/256x256/${m.remote}.png`,
  `https://www.footylogos.com/dls/logo/${m.footy}.png`,
 ];
 let ok=false;let last='';
 for(const url of urls){
  try{await fs.writeFile(file,await fetchPng(url));console.log(`[OK] ${slug} <- ${url}`);ok=true;break;}
  catch(e){last=String(e?.message||e);console.log(`[retry] ${slug}: ${last}`);}
 }
 if(!ok)failures.push(`${slug}: ${last}`);
}
if(failures.length){console.error('Nie udalo sie pobrac herbów:\n- '+failures.join('\n- '));process.exit(1);}
console.log(`Gotowe: ${Object.keys(manifest).length} lokalnych herbów mobile/PWA`);

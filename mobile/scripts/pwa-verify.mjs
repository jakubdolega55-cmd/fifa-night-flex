import fs from 'node:fs';
import path from 'node:path';

const dist = path.resolve('dist');
const required = [
  'index.html',
  'manifest.json',
  'icon-192.png',
  'icon-512.png',
  'apple-touch-icon.png',
];

let failed = false;
const ok = (msg) => console.log(`PASS  ${msg}`);
const bad = (msg) => { console.error(`FAIL  ${msg}`); failed = true; };

if (!fs.existsSync(dist)) {
  bad('Brak katalogu dist.');
  process.exit(1);
}
for (const rel of required) {
  const p = path.join(dist, rel);
  fs.existsSync(p) ? ok(rel) : bad(`Brak ${rel}`);
}

const manifestPath = path.join(dist, 'manifest.json');
if (fs.existsSync(manifestPath)) {
  try {
    const m = JSON.parse(fs.readFileSync(manifestPath, 'utf8'));
    m.name === 'FIFA Night' ? ok('manifest.name = FIFA Night') : bad('Nieprawidłowe manifest.name');
    m.display === 'standalone' ? ok('manifest.display = standalone') : bad('manifest.display nie jest standalone');
    String(m.start_url || '').length > 0 ? ok('manifest.start_url') : bad('Brak manifest.start_url');
    const sizes = new Set((m.icons || []).map(x => String(x.sizes || '')));
    sizes.has('192x192') ? ok('ikona 192x192') : bad('Brak ikony 192x192 w manifeście');
    sizes.has('512x512') ? ok('ikona 512x512') : bad('Brak ikony 512x512 w manifeście');
  } catch (e) {
    bad(`manifest.json nie jest poprawnym JSON: ${e.message}`);
  }
}

const indexPath = path.join(dist, 'index.html');
if (fs.existsSync(indexPath)) {
  const html = fs.readFileSync(indexPath, 'utf8');
  html.includes('rel="manifest"') ? ok('index.html -> manifest') : bad('index.html nie linkuje manifestu');
  html.includes('apple-mobile-web-app-capable') ? ok('meta iOS standalone') : bad('Brak meta iOS standalone');
  html.includes('apple-touch-icon') ? ok('apple-touch-icon') : bad('Brak apple-touch-icon');
  html.includes('viewport-fit=cover') ? ok('Safe Area / viewport-fit=cover') : bad('Brak viewport-fit=cover');
}

const files = [];
function walk(dir) {
  if (!fs.existsSync(dir)) return;
  for (const entry of fs.readdirSync(dir, {withFileTypes:true})) {
    const p = path.join(dir, entry.name);
    if (entry.isDirectory()) walk(p); else files.push(p);
  }
}
walk(dist);
const js = files.filter(p => p.endsWith('.js'));
let apiFound = false;
for (const p of js) {
  const txt = fs.readFileSync(p, 'utf8');
  if (txt.includes('https://fifa-night-api.onrender.com')) { apiFound = true; break; }
}
apiFound ? ok('produkcyjny adres API w bundle') : bad('Nie znaleziono produkcyjnego adresu API w bundle');

if (failed) {
  console.error('\nPWA VERIFY: FAIL');
  process.exit(1);
}
console.log('\nPWA VERIFY: ALL CHECKS PASSED');

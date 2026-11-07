// Capturi pentru docs/img cu Chrome headless prin CDP (WebSocket nativ în Node 24).
import { spawn } from 'node:child_process';
import { writeFileSync, mkdirSync } from 'node:fs';
import { pathToFileURL, fileURLToPath } from 'node:url';

// rădăcina proiectului = 4 niveluri deasupra scriptului (.claude/skills/doinadress/scripts)
const ROOT = fileURLToPath(new URL('../../../../', import.meta.url)).replaceAll('\\', '/').replace(/\/$/, '');
const OUT = process.argv[2];
if (!OUT) { console.error('folosire: node shots.mjs <dir_iesire>'); process.exit(1); }
mkdirSync(OUT, { recursive: true });
const PORT = 9333;
const chrome = spawn('C:/Program Files/Google/Chrome/Application/chrome.exe', [
  '--headless=new', `--remote-debugging-port=${PORT}`, `--user-data-dir=${OUT}/profile`,
  '--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist',
  '--allow-file-access-from-files', '--no-first-run', 'about:blank'], { stdio: 'ignore' });
const sleep = ms => new Promise(r => setTimeout(r, ms));

async function json(path, method = 'GET') {
  for (let i = 0; i < 50; i++) {
    try { return await (await fetch(`http://127.0.0.1:${PORT}${path}`, { method })).json(); } catch { await sleep(300); }
  }
  throw new Error('chrome nu răspunde');
}

const ONLY = process.argv.slice(3);   // opțional: doar capturile numite (ex. catalog panou)
async function shot({ name, file, hash = '', w, h, mobile = false, js = null, wait = 9000, after = 2500 }) {
  if (ONLY.length && !ONLY.some(o => name === o || name.startsWith(o + '_'))) return;
  const t = await json('/json/new?about:blank', 'PUT');
  const ws = new WebSocket(t.webSocketDebuggerUrl);
  await new Promise(r => ws.onopen = r);
  let id = 0; const pend = new Map();
  ws.onmessage = e => { const m = JSON.parse(e.data); if (m.id && pend.has(m.id)) { pend.get(m.id)(m); pend.delete(m.id); } };
  const send = (method, params = {}) => new Promise(r => { const i = ++id; pend.set(i, r); ws.send(JSON.stringify({ id: i, method, params })); });
  await send('Emulation.setDeviceMetricsOverride', { width: w, height: h, deviceScaleFactor: 1, mobile });
  if (mobile) await send('Emulation.setTouchEmulationEnabled', { enabled: true });
  await send('Page.enable');
  await send('Page.navigate', { url: pathToFileURL(`${ROOT}/${file}`).href + hash });
  await sleep(wait);
  if (js) { const r = await send('Runtime.evaluate', { expression: js, awaitPromise: true }); if (r.result?.exceptionDetails) console.log(name, 'JS error', JSON.stringify(r.result.exceptionDetails).slice(0, 300)); await sleep(after); }
  const r = await send('Page.captureScreenshot', { format: 'png' });
  writeFileSync(`${OUT}/${name}.png`, Buffer.from(r.result.data, 'base64'));
  console.log('ok', name);
  ws.close(); await fetch(`http://127.0.0.1:${PORT}/json/close/${t.id}`).catch(() => {});   // răspunde cu text, nu JSON
}

const REAL = 'DoinaDress_Cabina3D.html', SIMPLU = 'DoinaDress_Cabina3D_simplu.html';
const click = (sel, i = 0) => `document.querySelectorAll(${JSON.stringify(sel)})[${i}].click()`;
try {
  await json('/json/version');
  await shot({ name: 'corp_realist', file: REAL, w: 1382, h: 754 });
  await shot({ name: 'fata_realist', file: REAL, hash: '#barbat-fata', w: 1382, h: 754 });
  await shot({ name: 'catalog', file: REAL, w: 1382, h: 754, js: `${click('#avatars .av', 1)}; document.getElementById('btnCat').click()`, after: 25000 });
  await shot({ name: 'panou', file: SIMPLU, w: 1300, h: 850, js: click('#avatars .av', 4) });
  await shot({ name: 'familia_full', file: SIMPLU, w: 1382, h: 754 });
  await shot({ name: 'telefon', file: SIMPLU, hash: '#panou', w: 520, h: 900, mobile: true });
  for (const id of ['barbat', 'femeie', 'fetita'])
    await shot({ name: 'fata_' + id, file: SIMPLU, hash: `#${id}-fata`, w: 500, h: 700, mobile: true });
} finally { chrome.kill(); }

// Does a run survive quitting the app?
//
// Phase 2's whole promise: start a run, close Helixsh, reopen it, and still be
// watching that run. This drives the real app twice against one userData
// directory to check that.
//
//   xvfb-run -a node .claude/skills/run-desktop/survival.mjs
//
// Exits non-zero on failure.

import { createRequire } from 'node:module';
import * as path from 'node:path';

const APP_DIR = path.resolve(import.meta.dirname, '../../..');
const require = createRequire(import.meta.url);
const electron = require(path.join(APP_DIR, 'node_modules/playwright-core'))._electron;

const results = [];
const record = (name, pass, detail) => {
  results.push({ name, pass });
  console.log(`${pass ? 'PASS' : 'FAIL'} :: ${name} :: ${detail}`);
};

const launch = () => electron.launch({
  executablePath: process.platform === 'darwin'
    ? path.join(APP_DIR, 'node_modules/electron/dist/Electron.app/Contents/MacOS/Electron')
    : path.join(APP_DIR, 'node_modules/electron/dist/electron'),
  args: ['.'], cwd: APP_DIR, timeout: 60_000,
});

// ---- first session: create a run backed by a genuinely live process --------
let app = await launch();
let page = await app.firstWindow();
await page.waitForSelector('#run-form', { timeout: 30_000 });

// Seed from here rather than inside the main process: the store is files on
// disk, so an external writer is equivalent, and `require` is not in scope
// inside app.evaluate.
const userData = await app.evaluate(({ app: electronApp }) => electronApp.getPath('userData'));
const seeded = (() => {
  const fs = require('node:fs');
  const { spawn } = require('node:child_process');
  const { createRunStore } = require(path.join(APP_DIR, 'desktop/lib/runstore.cjs'));

  const store = createRunStore(path.join(userData, 'runs'));
  const run = store.create({
    request: { pipeline: 'rnaseq', runtime: 'docker' },
    command: 'nextflow run nf-core/rnaseq -profile docker',
    pipeline: 'rnaseq',
  });

  // Detached, writing straight to the run's log: the arrangement that lets a
  // run outlive the window.
  const fd = store.openLog(run.runId);
  const child = spawn(
    process.execPath,
    ['-e', "console.log('pipeline started'); setInterval(()=>console.log('still working'), 400)"],
    { detached: true, stdio: ['ignore', fd, fd] },
  );
  fs.closeSync(fd);
  child.unref();
  store.attach(run.runId, { pid: child.pid, marker: '' });
  return { runId: run.runId, pid: child.pid };
})();

await new Promise((r) => setTimeout(r, 900));
await page.evaluate(() => document.getElementById('refresh-runs').click());
await new Promise((r) => setTimeout(r, 400));

record('run appears in history while the app is open',
  await page.evaluate((id) => !!document.querySelector(`.run-item[data-run-id="${id}"]`), seeded.runId),
  seeded.runId);

// ---- quit: the run must NOT be killed --------------------------------------
await app.close();
await new Promise((r) => setTimeout(r, 1200));

let aliveAfterQuit = true;
try { process.kill(seeded.pid, 0); } catch { aliveAfterQuit = false; }
record('the run keeps running after the app quits', aliveAfterQuit, `pid ${seeded.pid}`);

// ---- second session: the run is still there and still followed -------------
app = await launch();
page = await app.firstWindow();
await page.waitForSelector('#run-form', { timeout: 30_000 });
await new Promise((r) => setTimeout(r, 1200));

const listed = await page.evaluate((id) => {
  const el = document.querySelector(`.run-item[data-run-id="${id}"]`);
  return el ? el.querySelector('.run-status')?.textContent : null;
}, seeded.runId);
record('the run is still listed after a relaunch', listed !== null, `status: ${listed}`);
record('and is still reported as running', listed === 'running', `status: ${listed}`);

// Open it: the log written before the quit must still be readable.
await page.evaluate((id) => document.querySelector(`.run-item[data-run-id="${id}"]`)?.click(), seeded.runId);
await new Promise((r) => setTimeout(r, 1500));
const consoleText = await page.evaluate(() => document.getElementById('console').innerText);
record('output written before the quit is replayed',
  consoleText.includes('pipeline started'), JSON.stringify(consoleText.slice(0, 60)));
record('and new output still arrives',
  consoleText.includes('still working'), 'live tail after reattach');
record('the reviewed command is shown with the run',
  consoleText.includes('nextflow run nf-core/rnaseq'), 'command recorded');

// ---- stopping an adopted run --------------------------------------------
await page.evaluate(() => document.getElementById('cancel').click());
await new Promise((r) => setTimeout(r, 1200));
let aliveAfterCancel = true;
try { process.kill(seeded.pid, 0); } catch { aliveAfterCancel = false; }
record('an adopted run can still be stopped', !aliveAfterCancel, `pid ${seeded.pid}`);

await app.close();

// ---- third session: a run that died unobserved is not still "running" -----
app = await launch();
page = await app.firstWindow();
await page.waitForSelector('#run-form', { timeout: 30_000 });
await new Promise((r) => setTimeout(r, 1200));
const finalStatus = await page.evaluate((id) => {
  const el = document.querySelector(`.run-item[data-run-id="${id}"]`);
  return el ? el.querySelector('.run-status')?.textContent : null;
}, seeded.runId);
record('a run that ended is no longer claimed to be running',
  finalStatus !== 'running' && finalStatus !== null, `status: ${finalStatus}`);
await app.close();

const passed = results.filter((r) => r.pass).length;
console.log(`\n${passed}/${results.length} passed`);
process.exit(passed === results.length ? 0 : 1);

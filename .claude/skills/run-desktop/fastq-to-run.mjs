// Can a user get from a directory of FASTQ files to a runnable plan without
// ever opening a terminal?
//
// That is Phase 4's acceptance criterion. This drives the real app through it.
//
//   xvfb-run -a node .claude/skills/run-desktop/fastq-to-run.mjs
//
// Exits non-zero on failure.

import { createRequire } from 'node:module';
import * as path from 'node:path';

const APP_DIR = path.resolve(import.meta.dirname, '../../..');
const require = createRequire(import.meta.url);
const electron = require(path.join(APP_DIR, 'node_modules/playwright-core'))._electron;
const fs = require('node:fs');
const os = require('node:os');

const results = [];
const record = (name, pass, detail) => {
  results.push({ name, pass });
  console.log(`${pass ? 'PASS' : 'FAIL'} :: ${name} :: ${detail}`);
};

const app = await electron.launch({
  executablePath: process.platform === 'darwin'
    ? path.join(APP_DIR, 'node_modules/electron/dist/Electron.app/Contents/MacOS/Electron')
    : path.join(APP_DIR, 'node_modules/electron/dist/electron'),
  args: ['.'], cwd: APP_DIR, timeout: 60_000,
});
const page = await app.firstWindow();
await page.waitForSelector('#run-form', { timeout: 30_000 });

const txt = (s) => page.evaluate((x) => document.querySelector(x)?.innerText ?? '', s);
const click = (s) => page.evaluate((x) => { document.querySelector(x)?.click(); }, s);
const stubPicker = (p) => app.evaluate(({ dialog }, f) => {
  dialog.showOpenDialog = async () => ({ canceled: false, filePaths: [f] });
}, p);

// A directory of paired FASTQ files, as it would come off a sequencer.
const fastqDir = fs.mkdtempSync(path.join(os.tmpdir(), 'helixsh-fastq-'));
for (const sample of ['CTRL_1', 'CTRL_2', 'TREAT_1', 'TREAT_2']) {
  fs.writeFileSync(path.join(fastqDir, `${sample}_R1_001.fastq.gz`), '');
  fs.writeFileSync(path.join(fastqDir, `${sample}_R2_001.fastq.gz`), '');
}
const outdir = fs.mkdtempSync(path.join(os.tmpdir(), 'helixsh-out-'));

// ---- pick a pipeline from the registry, not by typing a guess -------------
await click('#browse-pipelines');
await page.waitForFunction(
  () => document.querySelectorAll('.pipeline-item').length > 0, { timeout: 30_000 });
const offered = await page.evaluate(() =>
  [...document.querySelectorAll('.pipeline-item')].map((b) => b.dataset.pipeline));
record('the pipeline browser lists real nf-core pipelines',
  offered.includes('rnaseq') && offered.length > 3, `${offered.length} offered`);

await page.evaluate(() =>
  document.querySelector('.pipeline-item[data-pipeline="sarek"]')?.click());
await new Promise((r) => setTimeout(r, 400));
const picked = await page.evaluate(() => ({
  pipeline: document.getElementById('pipeline').value,
  revision: document.getElementById('revision').value,
}));
record('choosing one fills in the pipeline', picked.pipeline === 'sarek', picked.pipeline);
record('and pins its version, so the run is reproducible',
  /^\d+\.\d+/.test(picked.revision), picked.revision || '(blank)');
record('and the browser closes',
  await page.evaluate(() => document.getElementById('pipeline-browser').classList.contains('hidden')),
  'dismissed');

// ---- build a samplesheet from the FASTQ directory --------------------------
await page.evaluate(() => { document.getElementById('pipeline').value = 'rnaseq'; });
await stubPicker(fastqDir);
await click('#build-samplesheet');
await page.waitForFunction(
  () => !/Building/.test(document.getElementById('samplesheet-state').innerText), { timeout: 60_000 });

const sheetPath = await page.evaluate(() => document.getElementById('inputPath').value);
const state = await txt('#samplesheet-state');
record('building a samplesheet from FASTQ files fills the field',
  sheetPath.endsWith('.csv'), sheetPath.split('/').pop());
record('and reports how many samples it found',
  /4 samples/.test(state), state.split('\n')[0]);
record('and says it is usable', /no problems/.test(state), state.split('\n')[0]);

const sheetText = fs.readFileSync(sheetPath, 'utf8');
record('the generated sheet has a row per sample with both reads',
  sheetText.split('\n').filter(Boolean).length === 5 && sheetText.includes('_R2_001.fastq.gz'),
  `${sheetText.split('\n').filter(Boolean).length - 1} rows`);

// ---- and that sheet can actually be planned with --------------------------
await stubPicker(outdir);
await page.evaluate(() =>
  document.querySelector('button[data-picker="directory"][data-target="outputPath"]').click());
await page.waitForFunction(
  () => document.getElementById('outputPath').value !== '', { timeout: 10_000 });

await click('#plan');
await page.waitForFunction(
  () => !/Validating/.test(document.getElementById('run-state').innerText), { timeout: 90_000 });
await new Promise((r) => setTimeout(r, 400));
const planned = await txt('#console');
record('a generated samplesheet is accepted for execution',
  /planned: nextflow run nf-core\/rnaseq/.test(planned) && planned.includes(sheetPath),
  planned.match(/planned: (.*)/)?.[1]?.slice(0, 90) ?? await txt('#run-state'));
record('and the plan sees the samples it contains',
  /"row_count": 4/.test(planned), planned.match(/"row_count": \d+/)?.[0] ?? 'not reported');

// ---- a broken sheet is reported before a run is attempted ------------------
const bad = path.join(fastqDir, 'broken.csv');
fs.writeFileSync(bad, 'sample,fastq_1\nA,/x.fastq.gz\n');
await stubPicker(bad);
// Clear the previous verdict first: waiting for text that the stale message
// already matches would return before the new validation had run.
await page.evaluate(() => { document.getElementById('samplesheet-state').textContent = ''; });
await page.evaluate(() =>
  document.querySelector('button[data-picker="samplesheet"][data-target="inputPath"]').click());
await page.waitForFunction(
  () => document.getElementById('samplesheet-state').innerText.trim() !== '',
  { timeout: 30_000 });
await new Promise((r) => setTimeout(r, 300));
const badState = await txt('#samplesheet-state');
record('a broken samplesheet is called out when it is chosen',
  /not usable/.test(badState), badState.split('\n')[0]);
record('and says what is wrong with it',
  /strandedness/.test(badState), badState.split('\n').slice(1).join(' ').slice(0, 70));

await app.close();
const passed = results.filter((r) => r.pass).length;
console.log(`\n${passed}/${results.length} passed`);
process.exit(passed === results.length ? 0 : 1);

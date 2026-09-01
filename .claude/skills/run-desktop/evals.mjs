// Scripted eval battery for the Helixsh desktop app.
//
// Drives the real app through representative nf-core projects and asserts the
// security guardrails still hold. Unlike the unit suites this exercises the
// main process, the renderer and the Python backend together.
//
//   xvfb-run -a node .claude/skills/run-desktop/evals.mjs
//
// Exits non-zero if any check fails.

import { createRequire } from 'node:module';
import * as fs from 'node:fs';
import * as os from 'node:os';
import * as path from 'node:path';

const APP_DIR = path.resolve(import.meta.dirname, '../../..');
const DEMO = path.join(APP_DIR, 'demo');
const WORK = path.join(DEMO, 'work');
const SHOT_DIR = process.env.SCREENSHOT_DIR || path.join(os.tmpdir(), 'helixsh-shots');

const require = createRequire(import.meta.url);
const electron = require(path.join(APP_DIR, 'node_modules/playwright-core'))._electron;

fs.mkdirSync(SHOT_DIR, { recursive: true });
try {
  for (const dir of ['rnaseq-results', 'sarek-results', 'viralrecon-results', 'scrnaseq-results', 'cache']) {
    fs.mkdirSync(path.join(WORK, dir), { recursive: true });
  }
} catch (error) {
  console.error(`Cannot create ${WORK}: ${error.message}\n` +
    'The app runs as an unprivileged user, so the repository must be writable by it.');
  process.exit(2);
}

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
const click = (s) => page.evaluate((x) => {
  const el = document.querySelector(x);
  if (!el) return 'NOT_FOUND';
  el.click();
  return 'OK';
}, s);
const setVal = (id, v) => page.evaluate(([i, val]) => {
  const el = document.getElementById(i);
  if (el.type === 'checkbox') el.checked = val === true || val === 'true';
  else el.value = val;
  el.dispatchEvent(new Event('change', { bubbles: true }));
}, [id, v]);
const ss = (n) => page.screenshot({ path: path.join(SHOT_DIR, n + '.png') });

async function pick(kind, target, p) {
  await app.evaluate(({ dialog }, f) => {
    dialog.showOpenDialog = async () => ({ canceled: false, filePaths: [f] });
  }, p);
  await click(`button[data-picker="${kind}"][data-target="${target}"]`);
  await page.waitForFunction(([t, v]) => document.getElementById(t).value === v,
    [target, p], { timeout: 10_000 });
}

async function generateConfig(runtime) {
  await click(`#generate-${runtime}`);
  // Wait for a settled label rather than for "Generating…" to go away: when
  // the panel starts at "Not generated" that condition is already true, and
  // the check reads the state before generation has finished.
  await page.waitForFunction(
    (r) => ['Config ready', 'Generation failed']
      .includes(document.getElementById(`${r}-config-state`).innerText),
    runtime, { timeout: 30_000 });
  return txt(`#${runtime}-config-state`);
}

async function plan() {
  await click('#plan');
  await page.waitForFunction(
    () => !document.getElementById('run-state').innerText.match(/Validating/), { timeout: 90_000 });
  await new Promise((r) => setTimeout(r, 400));
  return { state: await txt('#run-state'), notice: await txt('#notice'), out: await txt('#console') };
}

async function attemptRun() {
  // Readiness runs `doctor --json`, which the main process allows 30s. A fixed
  // sleep here raced it: the refusal landed after the read and surfaced in the
  // next check instead. Wait for the UI to actually settle.
  const before = await page.evaluate(() => JSON.stringify([
    document.getElementById('notice').innerText,
    document.getElementById('run-state').innerText,
  ]));
  await click('#run');
  await page.waitForFunction((prev) => JSON.stringify([
    document.getElementById('notice').innerText,
    document.getElementById('run-state').innerText,
  ]) !== prev, before, { timeout: 45_000 }).catch(() => {});
  return { state: await txt('#run-state'), notice: await txt('#notice'), out: await txt('#console') };
}

let r;

// ---- Demo: bulk RNA-seq on Docker ------------------------------------------
await pick('directory', 'outputPath', path.join(WORK, 'rnaseq-results'));
await pick('samplesheet', 'inputPath', path.join(DEMO, 'rnaseq-samplesheet.csv'));
await setVal('revision', '3.18.0');
r = await plan();
record('demo/rnaseq docker plan',
  r.out.includes('nextflow run nf-core/rnaseq -profile docker') && r.state === 'Plan ready',
  r.out.match(/planned: (.*)/)?.[1] ?? r.state);
record('demo/rnaseq reads the samplesheet', r.out.includes('"row_count": 4'),
  r.out.match(/"row_count": \d+/)?.[0] ?? 'no row_count');
await ss('01-rnaseq');

// ---- Guardrail: execution requires an available runtime ---------------------
await app.evaluate(({ dialog }) => { dialog.showMessageBox = async () => ({ response: 1 }); });
let g = await attemptRun();
record('guard/runtime readiness blocks execution',
  /capability unavailable/i.test(g.notice + g.out), g.notice.split('\n')[0]);

// ---- Guardrail: configuration drift forces revalidation ---------------------
await setVal('pipeline', 'sarek');
g = await attemptRun();
record('guard/config drift forces revalidation',
  g.state === 'Revalidate' && /Validate the plan again/.test(g.notice), g.state);

// ---- Guardrail: a path not chosen through a picker is rejected --------------
await page.evaluate(() => { document.getElementById('outputPath').value = '/etc'; });
r = await plan();
record('guard/unapproved path rejected',
  /was not selected as a directory path/.test(r.notice + r.out),
  (r.notice || '').split('\n')[0]);

// ---- Demo: tumour/normal WGS on Kubernetes ---------------------------------
await pick('directory', 'outputPath', path.join(WORK, 'sarek-results'));
await pick('samplesheet', 'inputPath', path.join(DEMO, 'sarek-samplesheet.csv'));
await setVal('pipeline', 'sarek');
await setVal('revision', '3.5.1');
await setVal('runtime', 'kubernetes');
await new Promise((res) => setTimeout(res, 300));
record('ui/kubernetes panel reveals on target change',
  await page.evaluate(() => !document.getElementById('kubernetes-panel').classList.contains('hidden')),
  'panel visible');
await setVal('storageClaim', 'nextflow-pvc');
const k8sState = await generateConfig('kubernetes');
const cfgPath = await page.evaluate(() => document.getElementById('configPath').value);
record('demo/sarek k8s config generated', k8sState === 'Config ready' && !!cfgPath,
  cfgPath || 'none');
r = await plan();
record('demo/sarek k8s plan', r.out.includes('nf-core/sarek') && r.state === 'Plan ready',
  r.out.match(/planned: (.*)/)?.[1] ?? r.state);
record('demo/sarek detects tumour-normal pairing', r.out.includes('"has_tumor_normal": true'),
  r.out.match(/"has_tumor_normal": \w+/)?.[0] ?? 'not reported');
await ss('02-sarek-k8s');

// ---- Guardrail: injection payload in a Kubernetes name ----------------------
await setVal('storageClaim', "pvc'; System.exit(1); //");
record('guard/k8s config rejects injection payload',
  (await generateConfig('kubernetes')) === 'Generation failed',
  await txt('#kubernetes-config-state'));

// ---- Regression: the k8s config must not follow a non-k8s run --------------
// A config generated for Kubernetes pins process.executor = 'k8s'; carrying it
// into a Docker run would send a "local" pipeline to a cluster.
await setVal('storageClaim', 'nextflow-pvc');
await setVal('runtime', 'apptainer');
await setVal('pipeline', 'viralrecon');
await setVal('revision', '2.6.0');
await pick('directory', 'outputPath', path.join(WORK, 'viralrecon-results'));
await pick('samplesheet', 'inputPath', path.join(DEMO, 'viralrecon-samplesheet.csv'));
await setVal('offline', true);
r = await plan();
record('demo/viralrecon apptainer offline plan',
  r.out.includes('nf-core/viralrecon') && r.state === 'Plan ready',
  r.out.match(/planned: (.*)/)?.[1] ?? r.state);
record('regression/k8s config does not leak into a non-k8s run',
  !r.out.includes('nf-k8s') && !(await page.evaluate(() => document.getElementById('configPath').value)),
  r.out.match(/planned: (.*)/)?.[1] ?? 'no plan');
await ss('03-viralrecon');

// ---- Demo: single cell, resume off -----------------------------------------
await setVal('offline', false);
await setVal('runtime', 'docker');
await setVal('pipeline', 'scrnaseq');
await setVal('revision', '2.7.1');
await setVal('resume', false);
await pick('directory', 'outputPath', path.join(WORK, 'scrnaseq-results'));
await pick('samplesheet', 'inputPath', path.join(DEMO, 'rnaseq-samplesheet.csv'));
r = await plan();
record('demo/scrnaseq plan honours the resume toggle',
  r.out.includes('nf-core/scrnaseq') && !r.out.match(/planned:.*-resume/),
  r.out.match(/planned: (.*)/)?.[1] ?? r.state);

// ---- Demo: burst to AWS Batch ----------------------------------------------
// Nothing is submitted. What matters here is that the app can compose a cloud
// run, that the generated config is the only thing pinning the executor, and
// that it carries no secret.
await setVal('pipeline', 'rnaseq');
await setVal('revision', '3.18.0');
await pick('directory', 'outputPath', path.join(WORK, 'rnaseq-results'));
await setVal('runtime', 'awsbatch');
await new Promise((res) => setTimeout(res, 300));
record('ui/aws batch panel reveals on target change',
  await page.evaluate(() => !document.getElementById('awsbatch-panel').classList.contains('hidden')),
  'panel visible');
record('ui/credentials are reported before anything is submitted',
  (await txt('#awsbatch-credentials')).startsWith('Credentials'),
  await txt('#awsbatch-credentials') || 'nothing reported');

r = await plan();
record('guard/aws batch refuses to plan without a generated config',
  r.state !== 'Plan ready' && /require a generated executor config/.test(r.notice + r.out),
  (r.notice || '').split('\n')[0] || r.state);

await setVal('awsRegion', 'eu-west-1');
await setVal('awsJobQueue', 'genomics-spot');
await setVal('awsBucket', 'my-lab-nf');
await setVal('awsPrefix', 'runs/2026');
const awsState = await generateConfig('awsbatch');
const awsCfg = await page.evaluate(() => document.getElementById('configPath').value);
record('demo/aws batch config generated', awsState === 'Config ready' && !!awsCfg,
  awsCfg || 'none');

const awsText = awsCfg ? fs.readFileSync(awsCfg, 'utf8') : '';
record('demo/aws work directory is on S3',
  awsText.includes("workDir = 's3://my-lab-nf/runs/2026/work'"),
  awsText.match(/workDir = .*/)?.[0] ?? 'no workDir');
record('demo/aws config carries no credential',
  !awsText.split('\n').some((line) =>
    !line.trim().startsWith('//') && line.includes('=') &&
    /accesskey|secretkey|password|token|api_?key/i.test(line)),
  'no credential-shaped assignment');

// Editing a setting must not leave the config built from the old ones
// attached, still labelled ready.
await setVal('awsJobQueue', 'genomics-ondemand');
record('guard/editing a setting drops the config generated from the old ones',
  !(await page.evaluate(() => document.getElementById('configPath').value)) &&
    (await txt('#awsbatch-config-state')) === 'Not generated',
  await txt('#awsbatch-config-state'));
await generateConfig('awsbatch');

r = await plan();
record('demo/aws batch plan',
  r.out.includes('nf-core/rnaseq') && r.state === 'Plan ready',
  r.out.match(/planned: (.*)/)?.[1] ?? r.state);
record('demo/aws batch contributes no container profile',
  !/planned:.*-profile/.test(r.out), r.out.match(/planned: (.*)/)?.[1] ?? 'no plan');
await ss('04-aws-batch');

// ---- Regression: a config must not survive a change of executor -------------
// Each generated config pins process.executor. An AWS Batch config left
// attached to a Google Batch run would submit to AWS under the wrong heading,
// which is the same failure the Kubernetes leak was.
await setVal('runtime', 'googlebatch');
await new Promise((res) => setTimeout(res, 300));
record('regression/changing executor drops the previous config',
  !(await page.evaluate(() => document.getElementById('configPath').value)),
  'configPath cleared');

await setVal('gcpProject', 'my-lab-project');
await setVal('gcpLocation', 'us-central1');
await setVal('gcpBucket', 'my-lab-nf');
const gcpState = await generateConfig('googlebatch');
const gcpCfg = await page.evaluate(() => document.getElementById('configPath').value);
record('demo/google batch config generated', gcpState === 'Config ready' && !!gcpCfg,
  gcpCfg || 'none');
record('demo/google work directory is on Cloud Storage',
  !!gcpCfg && fs.readFileSync(gcpCfg, 'utf8').includes("workDir = 'gs://my-lab-nf/work'"),
  gcpCfg ? (fs.readFileSync(gcpCfg, 'utf8').match(/workDir = .*/)?.[0] ?? 'no workDir') : 'no config');
r = await plan();
record('demo/google batch plan',
  r.out.includes('nf-core/rnaseq') && r.state === 'Plan ready',
  r.out.match(/planned: (.*)/)?.[1] ?? r.state);
await ss('05-google-batch');

// ---- Guardrail: injection payload in a cloud name ---------------------------
await setVal('runtime', 'awsbatch');
await new Promise((res) => setTimeout(res, 300));
await setVal('awsRegion', 'eu-west-1');
await setVal('awsBucket', 'my-lab-nf');
await setVal('awsJobQueue', "q'; System.exit(1); //");
record('guard/aws config rejects injection payload',
  (await generateConfig('awsbatch')) === 'Generation failed' &&
    !(await page.evaluate(() => document.getElementById('configPath').value)),
  await txt('#awsbatch-config-state'));

// ---- Guardrail: path traversal in the pipeline name -------------------------
await setVal('runtime', 'docker');
await setVal('pipeline', '../../etc/passwd');
r = await plan();
record('guard/path traversal in pipeline name refused', r.state !== 'Plan ready', r.state);

await app.close();

const passed = results.filter((x) => x.pass).length;
console.log(`\n${passed}/${results.length} passed`);
process.exit(passed === results.length ? 0 : 1);

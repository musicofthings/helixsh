// Does a finished run show what it produced?
//
// Phase 3: after a pipeline ends a user needs to know whether it worked, what
// came out, and when it failed, why. This seeds a finished run with a real
// nf-core-shaped output directory and drives the app over it.
//
//   xvfb-run -a node .claude/skills/run-desktop/results.mjs
//
// Exits non-zero on failure.

import { createRequire } from 'node:module';
import * as path from 'node:path';

const APP_DIR = path.resolve(import.meta.dirname, '../../..');
const require = createRequire(import.meta.url);
const electron = require(path.join(APP_DIR, 'node_modules/playwright-core'))._electron;
const fs = require('node:fs');
const os = require('node:os');
const { createRunStore } = require(path.join(APP_DIR, 'desktop/lib/runstore.cjs'));

const results = [];
const record = (name, pass, detail) => {
  results.push({ name, pass });
  console.log(`${pass ? 'PASS' : 'FAIL'} :: ${name} :: ${detail}`);
};

// A trace with the fully qualified names Nextflow really emits, so this also
// exercises the per-process grouping fixed in Phase 1.
const TRACE = [
  'task_id\thash\tnative_id\tname\tstatus\texit\tsubmit\tduration\trealtime\t%cpu\tpeak_rss\tpeak_vmem\trchar\twchar',
  '1\ta1/bb\t101\tNFCORE_RNASEQ:RNASEQ:FASTQC (CTRL_1)\tCOMPLETED\t0\t2026-01-01\t3m 12s\t3m 2s\t185.4\t2.1 GB\t4.0 GB\t1.2 GB\t300 MB',
  '2\ta3/dd\t103\tNFCORE_RNASEQ:RNASEQ:ALIGN_STAR:STAR_ALIGN (CTRL_1)\tCOMPLETED\t0\t2026-01-01\t41m 8s\t40m 2s\t760.2\t38.4 GB\t52.0 GB\t22 GB\t9 GB',
  '3\ta4/ee\t104\tNFCORE_RNASEQ:RNASEQ:ALIGN_STAR:STAR_ALIGN (TREAT_1)\tFAILED\t137\t2026-01-01\t12m 4s\t11m 30s\t640.0\t41.0 GB\t52.0 GB\t8 GB\t2 GB',
  '4\ta5/ff\t105\tNFCORE_RNASEQ:RNASEQ:QUANTIFY:SALMON_QUANT (CTRL_1)\tCOMPLETED\t0\t2026-01-01\t8m 30s\t8m 10s\t410.0\t9.8 GB\t16.0 GB\t5 GB\t1 GB',
  '',
].join('\n');

const FAILURE_LOG = `
N E X T F L O W  ~  version 25.10.4
executor >  local (4)
-[nf-core/rnaseq] Pipeline completed with errors-
ERROR ~ Error executing process > 'NFCORE_RNASEQ:RNASEQ:ALIGN_STAR:STAR_ALIGN (TREAT_1)'

Caused by:
  Process terminated with an error exit status (137)

Command exit status:
  137

Command error:
  EXITING because of FATAL ERROR: not enough memory for BAM sorting
  SOLUTION: re-run with at least 40G

Work dir:
  /data/work/a4/ee1870f42f197683ac06a5654120b676

Container:
  quay.io/biocontainers/star:2.7.11b--h43eeafb_1

 -- Check '.nextflow.log' file for details
`;

const launch = () => electron.launch({
  executablePath: process.platform === 'darwin'
    ? path.join(APP_DIR, 'node_modules/electron/dist/Electron.app/Contents/MacOS/Electron')
    : path.join(APP_DIR, 'node_modules/electron/dist/electron'),
  args: ['.'], cwd: APP_DIR, timeout: 60_000,
});

const app = await launch();
const page = await app.firstWindow();
await page.waitForSelector('#run-form', { timeout: 30_000 });
const userData = await app.evaluate(({ app: a }) => a.getPath('userData'));

// A realistic nf-core output directory.
const outdir = fs.mkdtempSync(path.join(os.tmpdir(), 'helixsh-outdir-'));
const write = (rel, body = 'x') => {
  const full = path.join(outdir, rel);
  fs.mkdirSync(path.dirname(full), { recursive: true });
  fs.writeFileSync(full, body);
  return full;
};
write('pipeline_info/execution_trace_2026-09-01_04-00-00.txt', TRACE);
write('multiqc/multiqc_report.html', '<html><body>MultiQC</body></html>');
write('fastqc/CTRL_1_fastqc.html', 'x'.repeat(2048));
write('star/CTRL_1.bam', 'x'.repeat(4096));

const store = createRunStore(path.join(userData, 'runs'));
const run = store.create({
  request: { pipeline: 'rnaseq', runtime: 'docker', outputPath: outdir },
  command: 'nextflow run nf-core/rnaseq -profile docker --outdir ' + outdir,
  pipeline: 'rnaseq',
});
fs.writeFileSync(store.logPath(run.runId), FAILURE_LOG);
store.markFinished(run.runId, { exitCode: 1 });

await page.evaluate(() => document.getElementById('refresh-runs').click());
await new Promise((r) => setTimeout(r, 500));
await page.evaluate((id) => document.querySelector(`.run-item[data-run-id="${id}"]`)?.click(), run.runId);
await page.waitForFunction(() => !document.getElementById('results').classList.contains('hidden'), { timeout: 30_000 });
await new Promise((r) => setTimeout(r, 800));

const text = await page.evaluate(() => document.getElementById('results-body').innerText);

record('failure triage names the failed process',
  text.includes('STAR_ALIGN (TREAT_1)'), text.split('\n')[0]);
record('and shows the exit status and work directory',
  text.includes('137') && text.includes('/data/work/a4/ee1870f42f197683ac06a5654120b676'),
  'exit + work dir shown');
record('and the tool\'s own reason, not just that it failed',
  text.includes('not enough memory for BAM sorting'), 'stderr surfaced');

record('per-process table splits the real nf-core names',
  ['FASTQC', 'STAR_ALIGN', 'SALMON_QUANT'].every((n) => text.includes(n)),
  'FASTQC / STAR_ALIGN / SALMON_QUANT');
record('and marks which process failed',
  /1 failed/.test(text), text.match(/\d+ \(1 failed\)/)?.[0] ?? 'not marked');
record('and reports peak memory in human units',
  /GB/.test(text), text.match(/[\d.]+ GB/)?.[0] ?? 'no memory shown');

const reportLabels = await page.evaluate(() =>
  [...document.querySelectorAll('.report-link')].map((b) => b.textContent));
record('offers the MultiQC report', reportLabels.includes('MultiQC report'),
  JSON.stringify(reportLabels));

record('lists the output files',
  text.includes('star/CTRL_1.bam') && text.includes('fastqc/CTRL_1_fastqc.html'),
  'outputs listed');

// Security: the renderer asks by path, so a path outside the run's own output
// directory must be refused rather than opened.
const refused = await page.evaluate(async (id) => {
  try {
    await window.helixsh.openResult(id, '/etc/passwd');
    return 'OPENED';
  } catch (error) {
    return error.message;
  }
}, run.runId);
record('refuses to open a file outside the run output directory',
  /output directory/.test(refused) && refused !== 'OPENED', refused.slice(0, 80));

// A run still going should not present a half-written tree as results.
const live = store.create({
  request: { pipeline: 'sarek', runtime: 'docker', outputPath: outdir },
  command: 'nextflow run nf-core/sarek', pipeline: 'sarek',
});
await page.evaluate(() => document.getElementById('refresh-runs').click());
await new Promise((r) => setTimeout(r, 500));
await page.evaluate((id) => document.querySelector(`.run-item[data-run-id="${id}"]`)?.click(), live.runId);
await new Promise((r) => setTimeout(r, 1200));
record('hides results while a run is still going',
  await page.evaluate(() => document.getElementById('results').classList.contains('hidden')),
  'results hidden for a running run');

await app.close();
const passed = results.filter((r) => r.pass).length;
console.log(`\n${passed}/${results.length} passed`);
process.exit(passed === results.length ? 0 : 1);

"use strict";

const assert = require("node:assert/strict");
const test = require("node:test");
const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");

const {
  MAX_TREE_ENTRIES,
  collectResults,
  findReports,
  findTraceFile,
  parseFailures,
} = require("../lib/results.cjs");

// Verbatim from a real nf-core/demo failure, so the parser is written against
// what Nextflow prints rather than a guess at it.
const REAL_FAILURE_LOG = `
executor >  local (2)
[cf/845dc5] NFC…O:DEMO:FASTQC (SAMPLE3_SE) | 0 of 3
Execution cancelled -- Finishing pending tasks before exit
-[nf-core/demo] Pipeline completed with errors-
ERROR ~ Error executing process > 'NFCORE_DEMO:DEMO:FASTQC (SAMPLE2_PE)'

Caused by:
  Process \`NFCORE_DEMO:DEMO:FASTQC (SAMPLE2_PE)\` terminated with an error exit status (126)

Command executed:

  fastqc --quiet --threads 4 SAMPLE2_PE_1.gz SAMPLE2_PE_2.gz

Command exit status:
  126

Command output:
  (empty)

Command error:
  Unable to find image 'quay.io/biocontainers/fastqc:0.12.1--hdfd78af_0' locally
  Status: Downloaded newer image for quay.io/biocontainers/fastqc:0.12.1--hdfd78af_0
  /bin/bash: line 9: .command.run: Permission denied

Work dir:
  /home/runner/work/helixsh/helixsh/.nfcore-work/04/1870f42f197683ac06a5654120b676

Container:
  quay.io/biocontainers/fastqc:0.12.1--hdfd78af_0

Tip: you can try to figure out what's wrong by changing to the process work dir
 -- Check '.nextflow.log' file for details
`;

function tempOutdir() {
  return fs.mkdtempSync(path.join(os.tmpdir(), "helixsh-results-"));
}

function write(root, relative, content = "x") {
  const full = path.join(root, relative);
  fs.mkdirSync(path.dirname(full), { recursive: true });
  fs.writeFileSync(full, content);
  return full;
}

test("pulls the parts of a failure a user would otherwise hunt for", () => {
  const [failure, ...rest] = parseFailures(REAL_FAILURE_LOG);

  assert.equal(rest.length, 0);
  assert.equal(failure.process, "NFCORE_DEMO:DEMO:FASTQC (SAMPLE2_PE)");
  assert.equal(failure.exitStatus, "126");
  assert.equal(
    failure.workDir,
    "/home/runner/work/helixsh/helixsh/.nfcore-work/04/1870f42f197683ac06a5654120b676",
  );
  assert.equal(failure.container, "quay.io/biocontainers/fastqc:0.12.1--hdfd78af_0");
});

test("keeps the whole stderr, since the last line is usually the reason", () => {
  const [failure] = parseFailures(REAL_FAILURE_LOG);

  assert.match(failure.commandError, /Unable to find image/);
  // The actual cause was the final line; truncating to the first would hide it.
  assert.match(failure.commandError, /\.command\.run: Permission denied$/);
});

test("reports every failed task, not just the first", () => {
  const twice = REAL_FAILURE_LOG + REAL_FAILURE_LOG.replace("SAMPLE2_PE", "SAMPLE3_SE");

  const failures = parseFailures(twice);

  assert.equal(failures.length, 2);
  assert.deepEqual(failures.map((f) => f.exitStatus), ["126", "126"]);
});

test("a successful run has no failures", () => {
  assert.deepEqual(parseFailures("Pipeline completed successfully\n"), []);
  assert.deepEqual(parseFailures(""), []);
  assert.deepEqual(parseFailures(null), []);
});

test("finds the newest nf-core execution trace", () => {
  const outdir = tempOutdir();
  write(outdir, "pipeline_info/execution_trace_2026-01-01_00-00-00.txt");
  const newest = write(outdir, "pipeline_info/execution_trace_2026-06-01_00-00-00.txt");
  write(outdir, "pipeline_info/software_versions.yml");

  assert.equal(findTraceFile(outdir), newest);
});

test("no trace directory is a null, not a crash", () => {
  assert.equal(findTraceFile(tempOutdir()), null);
  assert.equal(findTraceFile("/nonexistent/path/for/sure"), null);
});

test("labels the reports a user would want to open", () => {
  const outdir = tempOutdir();
  write(outdir, "multiqc/multiqc_report.html");
  write(outdir, "pipeline_info/execution_report_2026-01-01.html");
  write(outdir, "fastqc/sample_a_fastqc.zip");

  const labels = findReports(outdir).map((r) => r.label).sort();

  assert.deepEqual(labels, ["Execution report", "MultiQC report"]);
});

test("collects outputs with paths relative to the output directory", () => {
  const outdir = tempOutdir();
  write(outdir, "fastqc/sample_a_fastqc.html", "abc");
  write(outdir, "multiqc/multiqc_report.html");

  const results = collectResults({ outdir, logText: "" });

  assert.deepEqual(
    results.outputs.map((o) => o.relative).sort(),
    ["fastqc/sample_a_fastqc.html", "multiqc/multiqc_report.html"],
  );
  assert.equal(results.outputs.find((o) => o.relative.endsWith("_fastqc.html")).size, 3);
  assert.equal(results.truncated, false);
});

test("caps the output listing rather than walking a whole genome of files", () => {
  const outdir = tempOutdir();
  for (let i = 0; i < MAX_TREE_ENTRIES + 25; i += 1) {
    write(outdir, `results/file_${i}.txt`);
  }

  const results = collectResults({ outdir, logText: "" });

  assert.equal(results.outputs.length, MAX_TREE_ENTRIES);
  assert.equal(results.truncated, true);
});

test("a run with no output directory still reports its failures", () => {
  const results = collectResults({ outdir: "", logText: REAL_FAILURE_LOG });

  assert.equal(results.outputs.length, 0);
  assert.equal(results.failures.length, 1);
  assert.equal(results.failures[0].exitStatus, "126");
});

test("a missing output directory is empty, not fatal", () => {
  const results = collectResults({ outdir: "/nonexistent/outdir", logText: "" });

  assert.deepEqual(results.outputs, []);
  assert.deepEqual(results.reports, []);
  assert.equal(results.trace, null);
});

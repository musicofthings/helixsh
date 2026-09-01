"use strict";

/**
 * What a finished run actually produced.
 *
 * A run console shows the same scrolling log a terminal would, which is what
 * the user had before. What a core facility needs after a pipeline ends is
 * different: did it work, what came out, and when it failed, why. This module
 * turns a run's output directory and log into those answers.
 *
 * Deliberately free of Electron so it can be unit tested directly.
 */

const fs = require("node:fs");
const path = require("node:path");

// nf-core pipelines publish these under --outdir by convention.
const TRACE_DIRECTORY = "pipeline_info";
const TRACE_PREFIX = "execution_trace";
const REPORT_PATTERNS = [
  { label: "MultiQC report", match: /multiqc_report\.html$/i },
  { label: "Execution report", match: /execution_report.*\.html$/i },
  { label: "Execution timeline", match: /execution_timeline.*\.html$/i },
  { label: "Pipeline DAG", match: /pipeline_dag.*\.(html|svg)$/i },
];

const MAX_TREE_ENTRIES = 500;
const MAX_TREE_DEPTH = 4;

/**
 * Pull the failed tasks out of a Nextflow log.
 *
 * Nextflow prints a fixed block per failed task -- the process, its exit
 * status, the work directory and the tool's own stderr. That last pair is
 * what a user actually needs and what they currently have to go hunting for,
 * so parse the block rather than making them scroll.
 *
 * Written against real failure output, not a guess at the format.
 */
function parseFailures(logText) {
  if (!logText) return [];
  const failures = [];
  // Each failure starts at "Error executing process > '<name>'".
  const blocks = String(logText).split(/ERROR ~ Error executing process > /);
  for (const block of blocks.slice(1)) {
    const name = block.match(/^'([^']+)'/)?.[1] ?? "";
    failures.push({
      process: name,
      exitStatus: field(block, "Command exit status") || "",
      workDir: field(block, "Work dir") || "",
      container: field(block, "Container") || "",
      commandError: field(block, "Command error", { multiline: true }) || "",
    });
  }
  return failures;
}

/**
 * Read one labelled section of a Nextflow failure block.
 *
 * The sections are "Label:" on its own line followed by indented lines, so a
 * section ends at the next unindented line.
 */
function field(block, label, { multiline = false } = {}) {
  const start = block.indexOf(`${label}:`);
  if (start === -1) return "";
  const rest = block.slice(start + label.length + 1);
  const lines = [];
  for (const line of rest.split("\n").slice(1)) {
    if (line.trim() === "" && lines.length === 0) continue;
    // An unindented, non-empty line begins the next section.
    if (line.trim() !== "" && !/^\s/.test(line)) break;
    if (line.trim() === "" && !multiline) break;
    lines.push(line.trim());
    if (!multiline) break;
  }
  return lines.join("\n").trim();
}

/** The newest nf-core execution trace under an output directory, if any. */
function findTraceFile(outdir) {
  const directory = path.join(outdir, TRACE_DIRECTORY);
  let entries;
  try {
    entries = fs.readdirSync(directory);
  } catch {
    return null;
  }
  const traces = entries
    .filter((name) => name.startsWith(TRACE_PREFIX) && name.endsWith(".txt"))
    .map((name) => path.join(directory, name))
    .sort();
  return traces.length ? traces[traces.length - 1] : null;
}

/** Reports worth offering a link to, newest name last. */
function findReports(outdir) {
  const found = [];
  for (const file of walk(outdir)) {
    for (const { label, match } of REPORT_PATTERNS) {
      if (match.test(file.path)) {
        found.push({ label, path: file.path, name: path.basename(file.path) });
        break;
      }
    }
  }
  return found;
}

/** Bounded walk of an output directory: enough to browse, not enough to hang. */
function* walk(root, depth = 0) {
  if (depth > MAX_TREE_DEPTH) return;
  let entries;
  try {
    entries = fs.readdirSync(root, { withFileTypes: true });
  } catch {
    return;
  }
  for (const entry of entries) {
    const full = path.join(root, entry.name);
    if (entry.isDirectory()) {
      yield* walk(full, depth + 1);
    } else if (entry.isFile()) {
      let size = 0;
      try {
        size = fs.statSync(full).size;
      } catch {
        size = 0;
      }
      yield { path: full, size };
    }
  }
}

/**
 * Everything worth showing about a run's outputs.
 *
 * `outputs` is capped: a real pipeline can emit tens of thousands of files,
 * and a list that long helps nobody and blocks the main process while it is
 * built.
 */
function collectResults({ outdir, logText }) {
  const failures = parseFailures(logText);
  if (!outdir) {
    return { outdir: "", trace: null, reports: [], outputs: [], truncated: false, failures };
  }

  let outputs = [];
  let truncated = false;
  for (const file of walk(outdir)) {
    if (outputs.length >= MAX_TREE_ENTRIES) {
      truncated = true;
      break;
    }
    outputs.push({
      path: file.path,
      relative: path.relative(outdir, file.path),
      size: file.size,
    });
  }
  outputs.sort((a, b) => a.relative.localeCompare(b.relative));

  return {
    outdir,
    trace: findTraceFile(outdir),
    reports: findReports(outdir),
    outputs,
    truncated,
    failures,
  };
}

module.exports = {
  MAX_TREE_ENTRIES,
  collectResults,
  findReports,
  findTraceFile,
  parseFailures,
};

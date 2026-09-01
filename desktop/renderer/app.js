"use strict";

const byId = (id) => document.getElementById(id);
const consoleElement = byId("console");
const runState = byId("run-state");
const notice = byId("notice");
const MAX_CONSOLE_CHARS = 1_000_000;
let activeRunId = "";
let viewedRunId = "";
let plannedFingerprint = "";
let capabilityByName = new Map();

// Executors that need a generated config. Each has a panel, a state label and
// a generate button named after it.
const EXECUTOR_RUNTIMES = ["kubernetes", "awsbatch", "googlebatch"];
// The doctor check that says where each cloud executor's credentials come from.
const CREDENTIAL_CAPABILITY = {
  awsbatch: "aws-credentials",
  googlebatch: "google-credentials",
};

function appendConsole(text, stream = "stdout") {
  const prefix = stream === "stderr" ? "⚠ " : "";
  const updated = `${consoleElement.textContent}${prefix}${text}`;
  consoleElement.textContent =
    updated.length > MAX_CONSOLE_CHARS
      ? `[earlier output truncated]\n${updated.slice(-MAX_CONSOLE_CHARS)}`
      : updated;
  consoleElement.scrollTop = consoleElement.scrollHeight;
}

function setRunState(label, state) {
  runState.textContent = label;
  runState.className = `run-state ${state}`;
}

function requestFromForm() {
  return {
    pipeline: byId("pipeline").value,
    revision: byId("revision").value,
    runtime: byId("runtime").value,
    inputPath: byId("inputPath").value,
    outputPath: byId("outputPath").value,
    workflowPath: byId("workflowPath").value,
    schemaPath: byId("schemaPath").value,
    paramsPath: byId("paramsPath").value,
    configPath: byId("configPath").value,
    cacheRoot: byId("cacheRoot").value,
    image: byId("image").value,
    resume: byId("resume").checked,
    offline: byId("offline").checked,
  };
}

function fingerprint(request) {
  return JSON.stringify(request);
}

async function loadCapabilities() {
  const container = byId("capabilities");
  try {
    const capabilities = await window.helixsh.capabilities();
    capabilityByName = new Map(capabilities.map((item) => [item.name, item]));
    const highlighted = new Set(["nextflow", "docker", "kubernetes"]);
    container.replaceChildren();
    for (const item of capabilities.filter((entry) => highlighted.has(entry.name))) {
      const chip = document.createElement("span");
      chip.className = `status-chip ${item.state === "ok" ? "ok" : "missing"}`;
      chip.textContent = `${item.name} ${item.state === "ok" ? "ready" : "unavailable"}`;
      chip.title = item.details;
      container.appendChild(chip);
    }
    showCredentialsNote(byId("runtime").value);
  } catch (error) {
    const chip = document.createElement("span");
    chip.className = "status-chip missing";
    chip.textContent = "Backend unavailable";
    container.replaceChildren(chip);
    appendConsole(`${error.message}\n`, "stderr");
  }
}

// ── executors ─────────────────────────────────────────────────────────────

/**
 * Say where a cloud run will get its credentials, before anything is submitted.
 *
 * Nothing here gates the run. Credentials that come from an instance profile
 * or the metadata server leave no local trace, so "unknown" is a normal answer
 * on exactly the hosts most likely to be submitting -- but a half-configured
 * environment is worth saying out loud, because otherwise the first sign of it
 * is a rejected job several minutes after Run.
 */
function showCredentialsNote(runtime) {
  const note = byId(`${runtime}-credentials`);
  if (!note) return;
  const capability = capabilityByName.get(CREDENTIAL_CAPABILITY[runtime]);
  if (!capability) {
    note.className = "credentials-note";
    note.textContent = "";
    return;
  }
  // "unknown" gets no colour: it is the normal answer on a host inside the
  // provider, not something to warn about.
  const tone = { ok: "ok", missing: "problem" }[capability.state] || "";
  const label = capability.state === "missing" ? "Credentials problem" : "Credentials";
  note.className = `credentials-note ${tone}`.trimEnd();
  note.textContent = `${label}: ${capability.details}.`;
}

function showExecutorPanel(runtime) {
  for (const name of EXECUTOR_RUNTIMES) {
    byId(`${name}-panel`).classList.toggle("hidden", name !== runtime);
  }
}

/** Forget any generated config, and say so in every panel that could show one. */
function clearExecutorConfig() {
  byId("configPath").value = "";
  for (const name of EXECUTOR_RUNTIMES) {
    byId(`${name}-config-state`).textContent = "Not generated";
  }
}

async function generateExecutorConfig(runtime, generate, settings) {
  const state = byId(`${runtime}-config-state`);
  state.textContent = "Generating…";
  try {
    const result = await generate(settings);
    byId("configPath").value = result.path;
    state.textContent = "Config ready";
    plannedFingerprint = "";
  } catch (error) {
    // A half-written config must not stay attached: the run would use the
    // previous executor's settings under the new panel's heading.
    byId("configPath").value = "";
    state.textContent = "Generation failed";
    notice.textContent = error.message;
  }
}

async function planRun() {
  const request = requestFromForm();
  setRunState("Validating", "active");
  notice.textContent = "Running Helixsh preflight checks…";
  consoleElement.textContent = "";
  try {
    const result = await window.helixsh.plan(request);
    appendConsole(result.stdout);
    if (result.stderr) appendConsole(result.stderr, "stderr");
    if (result.code === 0) {
      plannedFingerprint = fingerprint(request);
      setRunState("Plan ready", "ok");
      notice.textContent = "Validation complete. Review the command below, then run when ready.";
    } else {
      plannedFingerprint = "";
      setRunState("Needs attention", "error");
      notice.textContent = "The plan did not pass. Resolve the reported issue before execution.";
    }
  } catch (error) {
    plannedFingerprint = "";
    setRunState("Validation failed", "error");
    notice.textContent = error.message;
    appendConsole(`${error.message}\n`, "stderr");
  }
}

async function startRun() {
  const request = requestFromForm();
  if (fingerprint(request) !== plannedFingerprint) {
    notice.textContent = "The configuration changed. Validate the plan again before running.";
    setRunState("Revalidate", "error");
    return;
  }

  try {
    const result = await window.helixsh.start(request);
    if (result.cancelled) {
      notice.textContent = "Execution cancelled. The reviewed plan was not started.";
      return;
    }
    activeRunId = result.runId;
    viewedRunId = result.runId;
    byId("cancel").classList.remove("hidden");
    byId("run").disabled = true;
    setRunState("Running", "active");
    notice.textContent =
      "The pipeline is running. It keeps running if you close Helixsh, and reappears here next time.";
    appendConsole(`\n[desktop] started run ${activeRunId}\n`);
    byId("results").classList.add("hidden");
    refreshRuns();
  } catch (error) {
    setRunState("Start failed", "error");
    notice.textContent = error.message;
    appendConsole(`${error.message}\n`, "stderr");
  }
}

const EXECUTOR_SETTINGS = {
  kubernetes: () => ({
    generate: window.helixsh.generateKubernetesConfig,
    settings: {
      namespace: byId("namespace").value,
      serviceAccount: byId("serviceAccount").value,
      storageClaim: byId("storageClaim").value,
      storageMountPath: byId("storageMountPath").value,
    },
  }),
  awsbatch: () => ({
    generate: window.helixsh.generateAwsBatchConfig,
    settings: {
      region: byId("awsRegion").value,
      jobQueue: byId("awsJobQueue").value,
      bucket: byId("awsBucket").value,
      prefix: byId("awsPrefix").value,
    },
  }),
  googlebatch: () => ({
    generate: window.helixsh.generateGoogleBatchConfig,
    settings: {
      project: byId("gcpProject").value,
      location: byId("gcpLocation").value,
      bucket: byId("gcpBucket").value,
      prefix: byId("gcpPrefix").value,
    },
  }),
};

document.querySelectorAll("[data-picker]").forEach((button) => {
  button.addEventListener("click", async () => {
    const result = await window.helixsh.selectPath(button.dataset.picker);
    if (result) {
      byId(button.dataset.target).value = result;
      plannedFingerprint = "";
      // Say whether the sheet is usable now, rather than at plan time.
      if (button.dataset.target === "inputPath") validateChosenSamplesheet();
    }
  });
});

byId("runtime").addEventListener("change", () => {
  const runtime = byId("runtime").value;
  showExecutorPanel(runtime);
  // Changing executor always drops the generated config, even between two
  // executors that both need one: the file pins `process.executor`, so an AWS
  // Batch config left attached to a Google Batch run would submit to AWS under
  // the wrong heading. The main process refuses that too; this keeps the form
  // from ever offering it.
  clearExecutorConfig();
  showCredentialsNote(runtime);
  plannedFingerprint = "";
});
byId("run-form").addEventListener("submit", (event) => {
  event.preventDefault();
  planRun();
});
byId("run").addEventListener("click", startRun);
for (const runtime of EXECUTOR_RUNTIMES) {
  byId(`generate-${runtime}`).addEventListener("click", () => {
    const { generate, settings } = EXECUTOR_SETTINGS[runtime]();
    generateExecutorConfig(runtime, generate, settings);
  });
  // Editing a setting invalidates the config generated from the previous ones.
  // Left alone, the panel would still read "Config ready" while the run used
  // the queue or cluster the user had just changed away from.
  for (const event of ["input", "change"]) {
    byId(`${runtime}-panel`).addEventListener(event, clearExecutorConfig);
  }
}
byId("cancel").addEventListener("click", async () => {
  if (!viewedRunId) return;
  await window.helixsh.cancel(viewedRunId);
  notice.textContent = "Cancellation requested. Nextflow may take a moment to stop.";
  refreshRuns();
});

byId("refresh-runs").addEventListener("click", refreshRuns);
byId("build-samplesheet").addEventListener("click", buildSamplesheet);
byId("browse-pipelines").addEventListener("click", openPipelineBrowser);
byId("close-browser").addEventListener("click", () => {
  byId("pipeline-browser").classList.add("hidden");
});
byId("pipeline-browser").addEventListener("click", (event) => {
  // Clicking the backdrop dismisses, clicking the panel does not.
  if (event.target === byId("pipeline-browser")) {
    byId("pipeline-browser").classList.add("hidden");
  }
});
document.addEventListener("keydown", (event) => {
  if (event.key === "Escape") byId("pipeline-browser").classList.add("hidden");
});

window.helixsh.onJobEvent((event) => {
  if (event.runId !== viewedRunId) return;
  if (event.type === "output") appendConsole(event.text, event.stream);
  if (event.type === "error") appendConsole(`${event.message}\n`, "stderr");
  if (event.type === "exit") {
    // A run adopted after a restart reports no exit code: nobody was its
    // parent to collect one, so say that rather than invent a number.
    const unknown = event.code === null || event.code === undefined;
    const succeeded = event.code === 0;
    setRunState(
      unknown ? "Ended" : succeeded ? "Completed" : "Stopped",
      unknown ? "error" : succeeded ? "ok" : "error",
    );
    notice.textContent = unknown
      ? "The run ended while Helixsh was not attached, so its exit status is unknown. The log above is complete."
      : succeeded
        ? "Pipeline completed successfully."
        : `Pipeline exited with code ${event.code}${event.signal ? ` (${event.signal})` : ""}.`;
    appendConsole(`\n[desktop] run ended${unknown ? "" : ` with code ${event.code}`}\n`);
    if (event.runId === activeRunId) activeRunId = "";
    byId("cancel").classList.add("hidden");
    byId("run").disabled = false;
    refreshRuns();
    // The pipeline has stopped writing, so its outputs can now be read.
    showResults({ runId: event.runId, status: "finished" });
  }
});

document.querySelectorAll("input, select").forEach((element) => {
  element.addEventListener("change", () => {
    if (element.id !== "configPath") plannedFingerprint = "";
  });
});

const RUN_STATE_CLASS = {
  running: "active",
  completed: "ok",
  failed: "error",
  cancelled: "error",
  interrupted: "error",
};

function describeWhen(iso) {
  const started = new Date(iso);
  if (Number.isNaN(started.getTime())) return "";
  return started.toLocaleString(undefined, {
    month: "short", day: "numeric", hour: "2-digit", minute: "2-digit",
  });
}

async function refreshRuns() {
  const list = byId("runs");
  let runs = [];
  try {
    runs = await window.helixsh.runs();
  } catch (error) {
    appendConsole(`${error.message}\n`, "stderr");
    return;
  }
  list.replaceChildren();
  if (!runs.length) {
    const empty = document.createElement("li");
    empty.className = "runs-empty";
    empty.textContent = "No runs yet.";
    list.append(empty);
    return;
  }
  for (const run of runs.slice(0, 25)) {
    const item = document.createElement("li");
    const button = document.createElement("button");
    button.type = "button";
    button.className = "run-item";
    if (run.runId === viewedRunId) button.setAttribute("aria-current", "true");
    button.dataset.runId = run.runId;

    const pipeline = document.createElement("span");
    pipeline.className = "run-pipeline";
    pipeline.textContent = run.pipeline || "pipeline";

    const status = document.createElement("span");
    status.className = `run-status ${run.status}`;
    status.textContent = run.status;

    const when = document.createElement("span");
    when.className = "run-when";
    when.textContent = describeWhen(run.startedAt);

    button.append(pipeline, status, when);
    button.addEventListener("click", () => openRun(run));
    item.append(button);
    list.append(item);
  }
}

async function openRun(run) {
  try {
    if (viewedRunId && viewedRunId !== run.runId) {
      await window.helixsh.closeRun(viewedRunId);
    }
    viewedRunId = run.runId;
    consoleElement.textContent = "";
    const opened = await window.helixsh.openRun(run.runId);
    appendConsole(`[desktop] ${opened.command}\n\n`);
    if (opened.log) appendConsole(opened.log);
    setRunState(
      opened.status === "running" ? "Running" : opened.status,
      RUN_STATE_CLASS[opened.status] || "idle",
    );
    notice.textContent =
      opened.status === "running"
        ? "Following a run that is still going."
        : `Run from ${describeWhen(opened.startedAt)}.`;
    byId("cancel").classList.toggle("hidden", opened.status !== "running");
    await refreshRuns();
    await showResults(opened);
  } catch (error) {
    notice.textContent = error.message;
  }
}

// ── samplesheet ───────────────────────────────────────────────────────────

function showSheetState(text, kind, issues = []) {
  const element = byId("samplesheet-state");
  element.className = `sheet-state ${kind}`;
  element.replaceChildren();
  if (!text) return;
  element.append(document.createTextNode(text));
  if (!issues.length) return;
  const list = document.createElement("ul");
  list.className = "sheet-issues";
  for (const issue of issues.slice(0, 12)) {
    const item = document.createElement("li");
    const where = document.createElement("span");
    where.className = "issue-where";
    // Row 0 is the header, which is where a missing column is reported.
    where.textContent = issue.row > 0 ? `row ${issue.row}` : "header";
    item.append(where, document.createTextNode(issue.message));
    list.append(item);
  }
  element.append(list);
}

function reportValidation(validation, prefix, { countInPrefix = false } = {}) {
  if (!validation) {
    showSheetState(`${prefix} — could not be validated.`, "problem");
    return;
  }
  if (validation.ok) {
    // Do not say the sample count twice when the prefix already carries it.
    const detail = countInPrefix ? "no problems" : `${validation.row_count} samples, no problems`;
    showSheetState(`${prefix} — ${detail}.`, "ok");
  } else {
    showSheetState(`${prefix} — not usable yet:`, "problem", validation.issues || []);
  }
}

async function buildSamplesheet() {
  const pipeline = byId("pipeline").value;
  const fastqDir = await window.helixsh.selectPath("directory");
  if (!fastqDir) return;
  showSheetState("Building a samplesheet from that directory…", "busy");
  try {
    const result = await window.helixsh.buildSamplesheet({ fastqDir, pipeline });
    byId("inputPath").value = result.path;
    plannedFingerprint = "";
    const rows = result.summary?.rows ?? 0;
    if (rows === 0) {
      showSheetState("No FASTQ files were found in that directory.", "problem");
      return;
    }
    reportValidation(result.validation, `Built ${rows} samples`, { countInPrefix: true });
  } catch (error) {
    showSheetState(error.message, "problem");
  }
}

async function validateChosenSamplesheet() {
  const file = byId("inputPath").value;
  if (!file) {
    showSheetState("", "");
    return;
  }
  try {
    const validation = await window.helixsh.validateSamplesheet({
      file,
      pipeline: byId("pipeline").value,
    });
    reportValidation(validation, "Samplesheet");
  } catch (error) {
    showSheetState(error.message, "problem");
  }
}

// ── pipeline browser ──────────────────────────────────────────────────────

async function openPipelineBrowser() {
  const dialog = byId("pipeline-browser");
  const list = byId("pipeline-list");
  list.replaceChildren();
  dialog.classList.remove("hidden");

  let pipelines = [];
  try {
    pipelines = await window.helixsh.pipelines();
  } catch (error) {
    const failed = document.createElement("li");
    failed.textContent = error.message;
    list.append(failed);
    return;
  }

  for (const pipeline of pipelines) {
    const item = document.createElement("li");
    const button = document.createElement("button");
    button.type = "button";
    button.className = "pipeline-item";
    button.dataset.pipeline = pipeline.name;

    const name = document.createElement("span");
    name.className = "pipeline-name";
    name.textContent = pipeline.name;

    const version = document.createElement("span");
    version.className = "pipeline-version";
    version.textContent = pipeline.latest || "";

    const description = document.createElement("span");
    description.className = "pipeline-description";
    description.textContent = pipeline.description || "";

    button.append(name, version, description);
    button.addEventListener("click", () => {
      byId("pipeline").value = pipeline.name;
      // Pin the revision the registry reports, so a run is reproducible
      // instead of tracking whatever the pipeline's default branch becomes.
      if (pipeline.latest) byId("revision").value = pipeline.latest;
      plannedFingerprint = "";
      dialog.classList.add("hidden");
      validateChosenSamplesheet();
    });
    item.append(button);
    list.append(item);
  }
}

// ── results ───────────────────────────────────────────────────────────────

function formatBytes(bytes) {
  if (!Number.isFinite(bytes)) return "";
  const units = ["B", "KB", "MB", "GB", "TB"];
  let value = bytes;
  let unit = 0;
  while (value >= 1024 && unit < units.length - 1) {
    value /= 1024;
    unit += 1;
  }
  return `${value >= 10 || unit === 0 ? Math.round(value) : value.toFixed(1)} ${units[unit]}`;
}

function formatDuration(seconds) {
  if (!Number.isFinite(seconds) || seconds <= 0) return "—";
  if (seconds < 60) return `${Math.round(seconds)}s`;
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes}m ${Math.round(seconds % 60)}s`;
  return `${Math.floor(minutes / 60)}h ${minutes % 60}m`;
}

function group(title) {
  const section = document.createElement("div");
  section.className = "results-group";
  const heading = document.createElement("h4");
  heading.textContent = title;
  section.append(heading);
  return section;
}

function renderReports(reports, runId) {
  const section = group("Reports");
  const row = document.createElement("div");
  row.className = "report-links";
  for (const report of reports) {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "report-link";
    button.textContent = report.label;
    button.title = report.path;
    button.addEventListener("click", async () => {
      try {
        await window.helixsh.openResult(runId, report.path);
      } catch (error) {
        byId("results-note").textContent = error.message;
      }
    });
    row.append(button);
  }
  section.append(row);
  return section;
}

function renderProcesses(trace) {
  const section = group("Resource use by process");
  const table = document.createElement("table");
  table.className = "process-table";
  table.innerHTML =
    "<thead><tr><th>Process</th><th>Tasks</th><th>Slowest</th><th>Peak memory</th></tr></thead>";
  const body = document.createElement("tbody");
  for (const item of trace.processes || []) {
    const row = document.createElement("tr");
    if (item.failed_count > 0) row.className = "has-failures";

    const name = document.createElement("td");
    name.textContent = item.process;
    if (item.recommendation) {
      const hint = document.createElement("span");
      hint.className = "recommendation";
      hint.textContent = item.recommendation;
      name.append(hint);
    }

    const tasks = document.createElement("td");
    tasks.className = "num";
    tasks.textContent = item.failed_count
      ? `${item.task_count} (${item.failed_count} failed)`
      : String(item.task_count);

    const slowest = document.createElement("td");
    slowest.className = "num";
    slowest.textContent = formatDuration(item.max_duration_s);

    const memory = document.createElement("td");
    memory.className = "num";
    memory.textContent = item.max_peak_rss_mb
      ? formatBytes(item.max_peak_rss_mb * 1024 * 1024)
      : "—";

    row.append(name, tasks, slowest, memory);
    body.append(row);
  }
  table.append(body);
  section.append(table);
  return section;
}

function renderFailures(failures) {
  const section = group(`Failed ${failures.length === 1 ? "process" : "processes"}`);
  for (const failure of failures) {
    const card = document.createElement("div");
    card.className = "failure";

    const title = document.createElement("h5");
    title.textContent = failure.process || "Unknown process";
    card.append(title);

    const list = document.createElement("dl");
    for (const [label, value] of [
      ["Exit status", failure.exitStatus],
      ["Work dir", failure.workDir],
      ["Container", failure.container],
    ]) {
      if (!value) continue;
      const term = document.createElement("dt");
      term.textContent = label;
      const detail = document.createElement("dd");
      detail.textContent = value;
      list.append(term, detail);
    }
    card.append(list);

    if (failure.commandError) {
      const pre = document.createElement("pre");
      pre.textContent = failure.commandError;
      card.append(pre);
    }
    section.append(card);
  }
  return section;
}

function renderOutputs(results) {
  const section = group("Output files");
  const list = document.createElement("ul");
  list.className = "outputs";
  for (const file of results.outputs.slice(0, 200)) {
    const item = document.createElement("li");
    const name = document.createElement("span");
    name.textContent = file.relative;
    const size = document.createElement("span");
    size.className = "output-size";
    size.textContent = formatBytes(file.size);
    item.append(name, size);
    list.append(item);
  }
  section.append(list);
  return section;
}

async function showResults(run) {
  const panel = byId("results");
  const body = byId("results-body");
  const note = byId("results-note");
  body.replaceChildren();
  note.textContent = "";

  if (run.status === "running") {
    // Outputs are still being written; showing a half-finished tree would
    // read as a finished one.
    panel.classList.add("hidden");
    return;
  }

  let results;
  try {
    results = await window.helixsh.runResults(run.runId);
  } catch (error) {
    panel.classList.remove("hidden");
    note.textContent = error.message;
    return;
  }
  panel.classList.remove("hidden");

  if (results.failures.length) body.append(renderFailures(results.failures));
  if (results.reports.length) body.append(renderReports(results.reports, run.runId));
  if (results.trace && (results.trace.processes || []).length) {
    body.append(renderProcesses(results.trace));
  }
  if (results.outputs.length) body.append(renderOutputs(results));

  if (!body.childElementCount) {
    const empty = document.createElement("p");
    empty.className = "results-empty";
    empty.textContent = results.outdir
      ? "No output files were found in this run's output directory."
      : "This run recorded no output directory.";
    body.append(empty);
  } else if (results.truncated) {
    note.textContent = "Output listing truncated.";
  }
}

loadCapabilities();
refreshRuns();

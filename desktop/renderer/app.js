"use strict";

const byId = (id) => document.getElementById(id);
const consoleElement = byId("console");
const runState = byId("run-state");
const notice = byId("notice");
const MAX_CONSOLE_CHARS = 1_000_000;
// Trimming back to the cap would re-serialise the whole buffer on every line
// once a run passed it. Trimming to a lower mark makes that cost occur once
// per 200k characters instead.
const CONSOLE_TRIM_TO = 800_000;
let activeRunId = "";
let viewedRunId = "";
let plannedFingerprint = "";
let capabilityByName = new Map();
let consoleLength = 0;
let stickToConsoleTail = true;
let scrollScheduled = false;
// Restored when the pipeline browser closes, so Escape does not strand focus.
let browserOpener = null;

// Executors that need a generated config. Each has a panel, a state label and
// a generate button named after it.
const EXECUTOR_RUNTIMES = ["kubernetes", "awsbatch", "googlebatch"];
// The doctor check that says where each cloud executor's credentials come from.
const CREDENTIAL_CAPABILITY = {
  awsbatch: "aws-credentials",
  googlebatch: "google-credentials",
};

/**
 * Follow the tail of the output, unless the user has scrolled away from it.
 *
 * Assigning `scrollTop` forces a synchronous layout, and doing that once per
 * chunk made a chatty pipeline quadratic: a thousand lines took twenty-four
 * seconds of frozen window, all of it layout. Once per turn of the event loop
 * is indistinguishable on screen and costs one layout per frame instead of one
 * per line.
 */
function followConsoleTail() {
  if (!stickToConsoleTail || scrollScheduled) return;
  scrollScheduled = true;
  setTimeout(() => {
    scrollScheduled = false;
    consoleElement.scrollTop = consoleElement.scrollHeight;
  }, 0);
}

// Scrolling back to read something used to be undone by the next line of
// output. A scroll event fires at most once a frame, so measuring here is not
// the cost that measuring on every chunk was.
consoleElement.addEventListener("scroll", () => {
  const fromBottom =
    consoleElement.scrollHeight - consoleElement.scrollTop - consoleElement.clientHeight;
  stickToConsoleTail = fromBottom < 40;
});

function appendConsole(text, stream = "stdout") {
  const prefix = stream === "stderr" ? "\u26a0 " : "";
  // Appending a node keeps a long run cheap. Reading `textContent` back and
  // reassigning it re-serialised the whole buffer for every chunk, which on a
  // pipeline that prints steadily is a megabyte of string work per line.
  consoleElement.append(`${prefix}${text}`);
  consoleLength += prefix.length + text.length;
  if (consoleLength > MAX_CONSOLE_CHARS) {
    const kept = consoleElement.textContent.slice(-CONSOLE_TRIM_TO);
    consoleElement.textContent = `[earlier output truncated]\n${kept}`;
    consoleLength = consoleElement.textContent.length;
  }
  followConsoleTail();
}

/** Empty the console, keeping the character count that bounds it in step. */
function clearConsole() {
  consoleElement.textContent = "";
  consoleLength = 0;
  stickToConsoleTail = true;
}

/**
 * Say what is going on, in the one place that is announced.
 *
 * `problem` is not decoration: the notice is the only running commentary the
 * app gives, and an error printed in the same grey as an instruction reads as
 * an instruction.
 */
function setNotice(text, kind = "") {
  notice.className = `notice ${kind}`.trimEnd();
  notice.textContent = text;
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
      const state = item.state === "ok" ? "ready" : "unavailable";
      chip.textContent = `${item.name} ${state}`;
      // `title` is a mouse affordance: it never reaches a keyboard or a screen
      // reader reliably, and the detail is the useful half -- which version, or
      // why the runtime is not there.
      chip.title = item.details;
      chip.setAttribute("aria-label", `${item.name} ${state}: ${item.details}`);
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

function setConfigState(runtime, label, kind = "") {
  const state = byId(`${runtime}-config-state`);
  state.className = `config-state ${kind}`.trimEnd();
  state.textContent = label;
}

/** Forget any generated config, and say so in every panel that could show one. */
function clearExecutorConfig() {
  byId("configPath").value = "";
  for (const name of EXECUTOR_RUNTIMES) setConfigState(name, "Not generated");
}

async function generateExecutorConfig(runtime, generate, settings) {
  const button = byId(`generate-${runtime}`);
  setConfigState(runtime, "Generating…");
  button.disabled = true;
  try {
    const result = await generate(settings);
    byId("configPath").value = result.path;
    setConfigState(runtime, "Config ready", "ready");
    plannedFingerprint = "";
  } catch (error) {
    // A half-written config must not stay attached: the run would use the
    // previous executor's settings under the new panel's heading.
    byId("configPath").value = "";
    setConfigState(runtime, "Generation failed", "problem");
    setNotice(error.message, "problem");
  } finally {
    button.disabled = false;
  }
}

async function planRun() {
  const request = requestFromForm();
  // `required` does nothing on a readonly input -- it is barred from
  // constraint validation -- so an empty output directory used to reach the
  // backend and come back as a validation error several seconds later.
  if (!request.outputPath) {
    plannedFingerprint = "";
    setRunState("Needs attention", "error");
    setNotice("Choose an output directory before validating the plan.", "problem");
    byId("outputPath").focus();
    return;
  }

  const plan = byId("plan");
  plan.disabled = true;
  setRunState("Validating", "active");
  setNotice("Running Helixsh preflight checks…");
  clearConsole();
  try {
    const result = await window.helixsh.plan(request);
    appendConsole(result.stdout);
    if (result.stderr) appendConsole(result.stderr, "stderr");
    if (result.code === 0) {
      plannedFingerprint = fingerprint(request);
      setRunState("Plan ready", "ok");
      setNotice("Validation complete. Review the command below, then run when ready.");
    } else {
      plannedFingerprint = "";
      setRunState("Needs attention", "error");
      setNotice("The plan did not pass. Resolve the reported issue before execution.", "problem");
    }
  } catch (error) {
    plannedFingerprint = "";
    setRunState("Validation failed", "error");
    setNotice(error.message, "problem");
    appendConsole(`${error.message}\n`, "stderr");
  } finally {
    plan.disabled = false;
  }
}

async function startRun() {
  const request = requestFromForm();
  if (fingerprint(request) !== plannedFingerprint) {
    setNotice("The configuration changed. Validate the plan again before running.", "problem");
    setRunState("Revalidate", "error");
    return;
  }

  try {
    const result = await window.helixsh.start(request);
    if (result.cancelled) {
      setNotice("Execution cancelled. The reviewed plan was not started.");
      return;
    }
    activeRunId = result.runId;
    viewedRunId = result.runId;
    byId("cancel").classList.remove("hidden");
    byId("run").disabled = true;
    setRunState("Running", "active");
    setNotice(
      "The pipeline is running. It keeps running if you close Helixsh, and reappears here next time.",
    );
    appendConsole(`\n[desktop] started run ${activeRunId}\n`);
    byId("results").classList.add("hidden");
    refreshRuns();
  } catch (error) {
    setRunState("Start failed", "error");
    setNotice(error.message, "problem");
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
  setNotice("Cancellation requested. Nextflow may take a moment to stop.");
  refreshRuns();
});

byId("refresh-runs").addEventListener("click", refreshRuns);
byId("build-samplesheet").addEventListener("click", buildSamplesheet);
byId("browse-pipelines").addEventListener("click", openPipelineBrowser);
byId("close-browser").addEventListener("click", closePipelineBrowser);
byId("pipeline-browser").addEventListener("click", (event) => {
  // Clicking the backdrop dismisses, clicking the panel does not.
  if (event.target === byId("pipeline-browser")) closePipelineBrowser();
});
byId("pipeline-browser").addEventListener("keydown", (event) => {
  if (event.key === "Escape") {
    closePipelineBrowser();
    return;
  }
  if (event.key !== "Tab") return;
  // A dialog that does not hold Tab lets the keyboard wander into the form
  // behind it, which is still there and still focusable.
  const stops = focusableWithin(byId("pipeline-browser"));
  if (!stops.length) return;
  const edge = event.shiftKey ? stops[0] : stops[stops.length - 1];
  if (document.activeElement !== edge) return;
  event.preventDefault();
  (event.shiftKey ? stops[stops.length - 1] : stops[0]).focus();
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
    setNotice(
      unknown
        ? "The run ended while Helixsh was not attached, so its exit status is unknown. The log above is complete."
        : succeeded
          ? "Pipeline completed successfully."
          : `Pipeline exited with code ${event.code}${event.signal ? ` (${event.signal})` : ""}.`,
      unknown || !succeeded ? "problem" : "",
    );
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
    clearConsole();
    const opened = await window.helixsh.openRun(run.runId);
    appendConsole(`[desktop] ${opened.command}\n\n`);
    if (opened.log) appendConsole(opened.log);
    setRunState(
      opened.status === "running" ? "Running" : opened.status,
      RUN_STATE_CLASS[opened.status] || "idle",
    );
    setNotice(
      opened.status === "running"
        ? "Following a run that is still going."
        : `Run from ${describeWhen(opened.startedAt)}.`,
    );
    byId("cancel").classList.toggle("hidden", opened.status !== "running");
    await refreshRuns();
    await showResults(opened);
  } catch (error) {
    setNotice(error.message, "problem");
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

/** Every stop the keyboard can reach inside `container`, in tab order. */
function focusableWithin(container) {
  return [
    ...container.querySelectorAll('button, [href], input, select, [tabindex]:not([tabindex="-1"])'),
  ].filter((element) => !element.disabled && element.offsetParent !== null);
}

function closePipelineBrowser() {
  const dialog = byId("pipeline-browser");
  if (dialog.classList.contains("hidden")) return;
  dialog.classList.add("hidden");
  // Send the keyboard back where it came from rather than to the top of the
  // document, which is where dismissing the dialog used to leave it.
  browserOpener?.focus();
  browserOpener = null;
}

async function openPipelineBrowser() {
  const dialog = byId("pipeline-browser");
  const list = byId("pipeline-list");
  browserOpener = document.activeElement;
  list.replaceChildren();
  dialog.classList.remove("hidden");
  byId("close-browser").focus();

  let pipelines = [];
  try {
    pipelines = await window.helixsh.pipelines();
  } catch (error) {
    const failed = document.createElement("li");
    failed.className = "pipeline-empty";
    failed.textContent = error.message;
    list.append(failed);
    return;
  }
  if (!pipelines.length) {
    const empty = document.createElement("li");
    empty.className = "pipeline-empty";
    empty.textContent = "No pipelines were returned by the registry.";
    list.append(empty);
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
      closePipelineBrowser();
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

/** The results panel's own status line, which also reports its failures. */
function setResultsNote(text, kind = "") {
  const note = byId("results-note");
  note.className = kind;
  note.textContent = text;
}

function group(title) {
  const section = document.createElement("div");
  section.className = "results-group";
  // h3, not h4: the panel's own heading is the h2 above it, and skipping a
  // level leaves a screen reader's heading outline with a hole in it.
  const heading = document.createElement("h3");
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
        setResultsNote(error.message, "problem");
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
  const head = document.createElement("thead");
  const headRow = document.createElement("tr");
  for (const label of ["Process", "Tasks", "Slowest", "Peak memory"]) {
    const cell = document.createElement("th");
    // Without a scope a screen reader cannot tie "2.0 GB" to "Peak memory".
    cell.scope = "col";
    cell.textContent = label;
    headRow.append(cell);
  }
  head.append(headRow);
  table.append(head);
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

    const title = document.createElement("h4");
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
    name.className = "output-name";
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
  body.replaceChildren();
  setResultsNote("");

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
    setResultsNote(error.message, "problem");
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
    setResultsNote("Output listing truncated.");
  }
}

// ── theme ─────────────────────────────────────────────────────────────────

/**
 * Wire the switcher to the theme already painted by theme.js.
 *
 * The preference is stored by the main process rather than in the renderer:
 * it has to be readable before the window loads, so the window can be created
 * with a matching background colour instead of flashing the default one.
 */
async function setUpTheme() {
  const select = byId("theme");
  let choice = window.helixshTheme.choice();
  try {
    const settings = await window.helixsh.getSettings();
    choice = window.helixshTheme.apply(settings.theme);
  } catch (error) {
    // A theme is not worth failing the window over: keep what is painted.
    appendConsole(`${error.message}\n`, "stderr");
  }
  select.value = choice;
  select.addEventListener("change", async () => {
    const applied = window.helixshTheme.apply(select.value);
    try {
      await window.helixsh.setTheme(applied);
    } catch (error) {
      appendConsole(`${error.message}\n`, "stderr");
    }
  });
}

setUpTheme();
loadCapabilities();
refreshRuns();

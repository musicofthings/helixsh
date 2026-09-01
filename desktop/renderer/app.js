"use strict";

const byId = (id) => document.getElementById(id);
const consoleElement = byId("console");
const runState = byId("run-state");
const notice = byId("notice");
const MAX_CONSOLE_CHARS = 1_000_000;
let activeRunId = "";
let viewedRunId = "";
let plannedFingerprint = "";

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
    const highlighted = new Set(["nextflow", "docker", "kubernetes"]);
    container.replaceChildren();
    for (const item of capabilities.filter((entry) => highlighted.has(entry.name))) {
      const chip = document.createElement("span");
      chip.className = `status-chip ${item.state === "ok" ? "ok" : "missing"}`;
      chip.textContent = `${item.name} ${item.state === "ok" ? "ready" : "unavailable"}`;
      chip.title = item.details;
      container.appendChild(chip);
    }
  } catch (error) {
    const chip = document.createElement("span");
    chip.className = "status-chip missing";
    chip.textContent = "Backend unavailable";
    container.replaceChildren(chip);
    appendConsole(`${error.message}\n`, "stderr");
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
    refreshRuns();
  } catch (error) {
    setRunState("Start failed", "error");
    notice.textContent = error.message;
    appendConsole(`${error.message}\n`, "stderr");
  }
}

async function generateKubernetesConfig() {
  const state = byId("k8s-config-state");
  state.textContent = "Generating…";
  try {
    const result = await window.helixsh.generateKubernetesConfig({
      namespace: byId("namespace").value,
      serviceAccount: byId("serviceAccount").value,
      storageClaim: byId("storageClaim").value,
      storageMountPath: byId("storageMountPath").value,
    });
    byId("configPath").value = result.path;
    state.textContent = "Config ready";
    plannedFingerprint = "";
  } catch (error) {
    state.textContent = "Generation failed";
    notice.textContent = error.message;
  }
}

document.querySelectorAll("[data-picker]").forEach((button) => {
  button.addEventListener("click", async () => {
    const result = await window.helixsh.selectPath(button.dataset.picker);
    if (result) {
      byId(button.dataset.target).value = result;
      plannedFingerprint = "";
    }
  });
});

byId("runtime").addEventListener("change", () => {
  const isKubernetes = byId("runtime").value === "kubernetes";
  byId("kubernetes-panel").classList.toggle("hidden", !isKubernetes);
  if (!isKubernetes) {
    // Hiding the panel must also drop the generated config: it is invisible
    // once hidden, and leaving it attached would apply the k8s executor to a
    // local run.
    byId("configPath").value = "";
    byId("k8s-config-state").textContent = "Not generated";
  }
  plannedFingerprint = "";
});
byId("run-form").addEventListener("submit", (event) => {
  event.preventDefault();
  planRun();
});
byId("run").addEventListener("click", startRun);
byId("generate-k8s").addEventListener("click", generateKubernetesConfig);
byId("cancel").addEventListener("click", async () => {
  if (!viewedRunId) return;
  await window.helixsh.cancel(viewedRunId);
  notice.textContent = "Cancellation requested. Nextflow may take a moment to stop.";
  refreshRuns();
});

byId("refresh-runs").addEventListener("click", refreshRuns);

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
  } catch (error) {
    notice.textContent = error.message;
  }
}

loadCapabilities();
refreshRuns();

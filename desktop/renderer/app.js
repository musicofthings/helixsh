"use strict";

const byId = (id) => document.getElementById(id);
const consoleElement = byId("console");
const runState = byId("run-state");
const notice = byId("notice");
const MAX_CONSOLE_CHARS = 1_000_000;
let activeJobId = "";
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
    activeJobId = result.jobId;
    byId("cancel").classList.remove("hidden");
    byId("run").disabled = true;
    setRunState("Running", "active");
    notice.textContent = "The pipeline is running through the Helixsh POSIX execution boundary.";
    appendConsole(`\n[desktop] started job ${activeJobId}\n`);
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
  plannedFingerprint = "";
});
byId("run-form").addEventListener("submit", (event) => {
  event.preventDefault();
  planRun();
});
byId("run").addEventListener("click", startRun);
byId("generate-k8s").addEventListener("click", generateKubernetesConfig);
byId("cancel").addEventListener("click", async () => {
  if (!activeJobId) return;
  await window.helixsh.cancel(activeJobId);
  notice.textContent = "Cancellation requested. Nextflow may take a moment to stop.";
});

window.helixsh.onJobEvent((event) => {
  if (event.jobId !== activeJobId) return;
  if (event.type === "output") appendConsole(event.text, event.stream);
  if (event.type === "error") appendConsole(`${event.message}\n`, "stderr");
  if (event.type === "exit") {
    const succeeded = event.code === 0;
    setRunState(succeeded ? "Completed" : "Stopped", succeeded ? "ok" : "error");
    notice.textContent = succeeded
      ? "Pipeline completed successfully."
      : `Pipeline exited with code ${event.code}${event.signal ? ` (${event.signal})` : ""}.`;
    appendConsole(`\n[desktop] job exited with code ${event.code}\n`);
    activeJobId = "";
    byId("cancel").classList.add("hidden");
    byId("run").disabled = false;
  }
});

document.querySelectorAll("input, select").forEach((element) => {
  element.addEventListener("change", () => {
    if (element.id !== "configPath") plannedFingerprint = "";
  });
});

loadCapabilities();

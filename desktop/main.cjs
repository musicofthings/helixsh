"use strict";

const {
  app,
  BrowserWindow,
  dialog,
  ipcMain,
  session,
} = require("electron");
const crypto = require("node:crypto");
const fs = require("node:fs");
const path = require("node:path");
const { spawn } = require("node:child_process");
const {
  buildKubernetesConfigArgs,
  buildRunArgs,
  requiredCapabilities,
  validateKubernetesRequest,
  validateRunRequest,
} = require("./lib/helixsh.cjs");
const { STATUS, createRunStore, isProcessAlive } = require("./lib/runstore.cjs");

const MAX_CAPTURE_BYTES = 2 * 1024 * 1024;
// `doctor` probes an unreachable cluster and a stalled Docker socket, each
// bounded by the backend's own 10s per-check timeout. Give it room to report
// those as capability states rather than surfacing an opaque IPC timeout.
const DOCTOR_TIMEOUT_MS = 30_000;
const selectedPaths = new Map();
// Live children we spawned, kept only so their exit status can be collected.
// The durable record of every run is the run store on disk.
const jobs = new Map();
// runId -> interval following that run's log file.
const tails = new Map();
const LOG_POLL_MS = 500;
const MAX_LOG_REPLAY_BYTES = 512 * 1024;
let runStore = null;
let mainWindow = null;
let approvedPlan = null;

function store() {
  if (!runStore) {
    runStore = createRunStore(path.join(app.getPath("userData"), "runs"));
  }
  return runStore;
}

app.enableSandbox();

function backendSpec() {
  const override = process.env.HELIXSH_BACKEND_PATH;
  if (override) {
    return { command: override, prefix: [], env: process.env };
  }

  const projectRoot = app.isPackaged ? process.resourcesPath : path.resolve(__dirname, "..");
  const sourceRoot = path.join(projectRoot, "src");
  const pythonPath = [sourceRoot, process.env.PYTHONPATH].filter(Boolean).join(path.delimiter);
  return {
    command: process.env.HELIXSH_PYTHON || "python3",
    prefix: ["-m", "helixsh.cli"],
    env: { ...process.env, PYTHONPATH: pythonPath },
  };
}

function assertTrustedSender(event) {
  if (
    !mainWindow ||
    mainWindow.isDestroyed() ||
    event.sender !== mainWindow.webContents ||
    event.senderFrame !== mainWindow.webContents.mainFrame
  ) {
    throw new Error("Untrusted IPC sender");
  }
}

function rememberAndReturn(filePath, kind) {
  if (filePath) {
    const resolved = path.resolve(filePath);
    const kinds = selectedPaths.get(resolved) || new Set();
    kinds.add(kind);
    selectedPaths.set(resolved, kinds);
  }
  return filePath || "";
}

function assertApprovedPaths(request) {
  const expectedKinds = {
    inputPath: "samplesheet",
    outputPath: "directory",
    workflowPath: "workflow",
    schemaPath: "schema",
    paramsPath: "params",
    configPath: "config",
    cacheRoot: "directory",
  };
  for (const [field, kind] of Object.entries(expectedKinds)) {
    const value = request[field];
    if (value && !selectedPaths.get(path.resolve(value))?.has(kind)) {
      throw new Error(`${field} was not selected as a ${kind} path through Helixsh`);
    }
  }
}

function runBackend(args, { timeoutMs = 20_000 } = {}) {
  return new Promise((resolve, reject) => {
    const backend = backendSpec();
    const child = spawn(backend.command, [...backend.prefix, ...args], {
      cwd: app.getPath("userData"),
      env: backend.env,
      shell: false,
      stdio: ["ignore", "pipe", "pipe"],
    });
    let stdout = "";
    let stderr = "";
    let captured = 0;
    const timer = setTimeout(() => {
      child.kill("SIGTERM");
      reject(new Error("Helixsh backend timed out"));
    }, timeoutMs);

    const capture = (stream) => (chunk) => {
      const remaining = MAX_CAPTURE_BYTES - captured;
      if (remaining <= 0) return;
      // Trim the chunk itself: checking only before appending let a single
      // large chunk overshoot the cap by its entire length.
      const text = chunk.subarray(0, remaining).toString("utf8");
      captured += Buffer.byteLength(text);
      if (stream === "stdout") stdout += text;
      else stderr += text;
    };
    child.stdout.on("data", capture("stdout"));
    child.stderr.on("data", capture("stderr"));
    child.once("error", (error) => {
      clearTimeout(timer);
      reject(error);
    });
    child.once("close", (code, signal) => {
      clearTimeout(timer);
      resolve({ code: code ?? 2, signal: signal || "", stdout, stderr });
    });
  });
}

function sendJobEvent(payload) {
  if (mainWindow && !mainWindow.isDestroyed()) {
    mainWindow.webContents.send("helixsh:job-event", payload);
  }
}

function runRequestDigest(request) {
  return crypto.createHash("sha256").update(JSON.stringify(request)).digest("hex");
}

function terminatePid(pid) {
  // By pid rather than by child handle: after a relaunch a run has no child
  // object here, but it is still stoppable. Children are spawned detached, so
  // the negative pid reaches the whole process group and Nextflow's own
  // subprocesses go with it.
  if (!pid) return false;
  try {
    if (process.platform !== "win32") {
      process.kill(-pid, "SIGTERM");
      return true;
    }
    process.kill(pid, "SIGTERM");
    return true;
  } catch (error) {
    if (error.code === "ESRCH") return false;
    throw error;
  }
}

/** Read the tail of a run's log, with the offset the reader stopped at. */
function readRunTail(runId) {
  const file = store().logPath(runId);
  try {
    const { size } = fs.statSync(file);
    const start = Math.max(0, size - MAX_LOG_REPLAY_BYTES);
    const handle = fs.openSync(file, "r");
    try {
      const buffer = Buffer.alloc(size - start);
      const read = fs.readSync(handle, buffer, 0, buffer.length, start);
      return { text: buffer.subarray(0, read).toString("utf8"), offset: start + read };
    } finally {
      fs.closeSync(handle);
    }
  } catch {
    return { text: "", offset: 0 };
  }
}

/**
 * Follow a run's log file from a known offset and forward what appears.
 *
 * Live and reattached runs read the same way. The child writes straight to
 * this file, so there is no pipe to lose when the app quits, and a later
 * launch picks the run up mid-flight by reading on from where a caller
 * finished. Taking the offset as an argument is what keeps opening a run free
 * of gaps and duplicates: the reader hands over exactly where it stopped.
 */
function followRun(runId, fromOffset) {
  unfollowRun(runId);
  const file = store().logPath(runId);
  let offset = fromOffset;
  if (offset === undefined) {
    try {
      offset = fs.statSync(file).size;
    } catch {
      offset = 0;
    }
  }

  const pump = () => {
    let size;
    try {
      size = fs.statSync(file).size;
    } catch {
      return;
    }
    if (size < offset) offset = 0; // truncated underneath us
    if (size === offset) return;
    let handle;
    try {
      handle = fs.openSync(file, "r");
      const buffer = Buffer.alloc(size - offset);
      const read = fs.readSync(handle, buffer, 0, buffer.length, offset);
      offset += read;
      if (read > 0) {
        sendJobEvent({
          runId,
          type: "output",
          stream: "stdout",
          text: buffer.subarray(0, read).toString("utf8"),
        });
      }
    } catch {
      // A transient read failure should not stop the follow.
    } finally {
      if (handle !== undefined) fs.closeSync(handle);
    }
  };

  pump();
  tails.set(runId, setInterval(pump, LOG_POLL_MS));
}

function unfollowRun(runId) {
  const timer = tails.get(runId);
  if (timer) {
    clearInterval(timer);
    tails.delete(runId);
  }
}

/** Watch a run we did not spawn, since no exit event will ever reach us. */
function superviseAdopted(run) {
  const timer = setInterval(() => {
    if (isProcessAlive(run.pid)) return;
    clearInterval(timer);
    // Not our child, so nobody collected an exit status and we must not
    // invent one.
    const settled = store().update(run.runId, {
      status: STATUS.INTERRUPTED,
      finishedAt: new Date().toISOString(),
    });
    setTimeout(() => {
      unfollowRun(run.runId);
      sendJobEvent({ runId: run.runId, type: "exit", code: null, signal: "", status: settled?.status });
    }, LOG_POLL_MS * 2);
  }, 1000);
}

function startRun(request, command) {
  const backend = backendSpec();
  const args = buildRunArgs(request, { execute: true });
  const run = store().create({ request, command, pipeline: request.pipeline });

  // stdout and stderr go to the run's log file rather than through our pipes.
  // A pipe dies with this process; the file does not, which is what lets a
  // run keep going -- and keep recording -- after the window closes.
  const logFd = store().openLog(run.runId);
  let child;
  try {
    child = spawn(backend.command, [...backend.prefix, ...args], {
      cwd: app.getPath("userData"),
      env: backend.env,
      shell: false,
      detached: process.platform !== "win32",
      stdio: ["ignore", logFd, logFd],
    });
  } finally {
    fs.closeSync(logFd);
  }

  store().attach(run.runId, { pid: child.pid, marker: request.pipeline });
  jobs.set(run.runId, child);
  // Do not hold the app open on the run's account, and do not take the run
  // down when the app goes.
  child.unref();

  child.once("error", (error) => {
    jobs.delete(run.runId);
    store().update(run.runId, {
      status: STATUS.FAILED,
      finishedAt: new Date().toISOString(),
    });
    unfollowRun(run.runId);
    sendJobEvent({ runId: run.runId, type: "error", message: error.message });
  });
  child.once("exit", (code, signal) => {
    jobs.delete(run.runId);
    const settled = store().markFinished(run.runId, { exitCode: code, signal: signal || "" });
    // Let the follower drain what the child wrote just before exiting.
    setTimeout(() => {
      unfollowRun(run.runId);
      sendJobEvent({
        runId: run.runId,
        type: "exit",
        code: code ?? 2,
        signal: signal || "",
        status: settled?.status,
      });
    }, LOG_POLL_MS * 2);
  });

  followRun(run.runId);
  return { runId: run.runId };
}

async function assertRuntimeReady(runtime) {
  const result = await runBackend(["doctor", "--json"], { timeoutMs: DOCTOR_TIMEOUT_MS });
  if (result.code !== 0) throw new Error(result.stderr || "Runtime readiness check failed");
  const capabilities = new Map(JSON.parse(result.stdout).map((item) => [item.name, item]));
  const unavailable = requiredCapabilities(runtime).filter(
    (name) => capabilities.get(name)?.state !== "ok",
  );
  if (unavailable.length) {
    throw new Error(`Required capability unavailable: ${unavailable.join(", ")}`);
  }
}

function registerIpc() {
  ipcMain.handle("helixsh:capabilities", async (event) => {
    assertTrustedSender(event);
    const result = await runBackend(["doctor", "--json"], { timeoutMs: DOCTOR_TIMEOUT_MS });
    if (result.code !== 0) throw new Error(result.stderr || "Capability check failed");
    return JSON.parse(result.stdout);
  });

  ipcMain.handle("helixsh:select-path", async (event, kind) => {
    assertTrustedSender(event);
    approvedPlan = null;
    const definitions = {
      samplesheet: { properties: ["openFile"], filters: [{ name: "CSV", extensions: ["csv"] }] },
      workflow: { properties: ["openFile"], filters: [{ name: "Nextflow", extensions: ["nf"] }] },
      schema: { properties: ["openFile"], filters: [{ name: "JSON", extensions: ["json"] }] },
      params: { properties: ["openFile"], filters: [{ name: "JSON", extensions: ["json"] }] },
      config: { properties: ["openFile"], filters: [{ name: "Nextflow config", extensions: ["config"] }] },
      directory: { properties: ["openDirectory", "createDirectory"] },
    };
    const options = definitions[kind];
    if (!options) throw new TypeError("Unsupported path selection type");
    const result = await dialog.showOpenDialog(mainWindow, options);
    return result.canceled ? "" : rememberAndReturn(result.filePaths[0], kind);
  });

  ipcMain.handle("helixsh:plan", async (event, payload) => {
    assertTrustedSender(event);
    const request = validateRunRequest(payload);
    assertApprovedPaths(request);
    const result = await runBackend(buildRunArgs(request), { timeoutMs: 30_000 });
    approvedPlan =
      result.code === 0
        ? {
            digest: runRequestDigest(request),
            command:
              result.stdout.match(/^\[helixsh\] planned: (.+)$/m)?.[1] ||
              `nextflow run nf-core/${request.pipeline}`,
          }
        : null;
    return result;
  });

  ipcMain.handle("helixsh:start", async (event, payload) => {
    assertTrustedSender(event);
    const request = validateRunRequest(payload);
    assertApprovedPaths(request);
    if (!approvedPlan || approvedPlan.digest !== runRequestDigest(request)) {
      throw new Error("Validate this exact plan before execution");
    }
    await assertRuntimeReady(request.runtime);
    const confirmation = await dialog.showMessageBox(mainWindow, {
      type: "warning",
      buttons: ["Cancel", "Run pipeline"],
      defaultId: 0,
      cancelId: 0,
      noLink: true,
      message: `Run nf-core/${request.pipeline} with ${request.runtime}?`,
      detail: `Helixsh will execute the reviewed command:\n\n${approvedPlan.command}`,
    });
    if (confirmation.response !== 1) {
      return { cancelled: true };
    }
    const reviewed = approvedPlan.command;
    approvedPlan = null;
    return startRun(request, reviewed);
  });

  ipcMain.handle("helixsh:cancel", async (event, runId) => {
    assertTrustedSender(event);
    const id = String(runId);
    const child = jobs.get(id);
    const pid = child ? child.pid : store().read(id)?.pid;
    const cancelled = terminatePid(pid);
    if (cancelled && !child) {
      // An adopted run has no exit event coming, so record the intent now.
      store().markCancelled(id);
    }
    return { cancelled };
  });

  ipcMain.handle("helixsh:runs", async (event) => {
    assertTrustedSender(event);
    return store().list();
  });

  ipcMain.handle("helixsh:open-run", async (event, runId) => {
    assertTrustedSender(event);
    const run = store().read(String(runId));
    if (!run) throw new Error("Unknown run");
    // Hand back what the run has already written, then follow on from exactly
    // where that read stopped, so opening a run shows its history without
    // gaps or repeats.
    const { text, offset } = readRunTail(run.runId);
    followRun(run.runId, offset);
    return { ...run, log: text };
  });

  ipcMain.handle("helixsh:close-run", async (event, runId) => {
    assertTrustedSender(event);
    const id = String(runId);
    // Keep following a run we spawned; its exit still has to be recorded.
    if (!jobs.has(id)) unfollowRun(id);
    return { closed: true };
  });

  ipcMain.handle("helixsh:generate-k8s-config", async (event, payload) => {
    assertTrustedSender(event);
    approvedPlan = null;
    const request = validateKubernetesRequest(payload);
    const digest = crypto
      .createHash("sha256")
      .update(JSON.stringify(request))
      .digest("hex")
      .slice(0, 12);
    const configDirectory = path.join(app.getPath("userData"), "kubernetes");
    fs.mkdirSync(configDirectory, { recursive: true, mode: 0o700 });
    const destination = path.join(configDirectory, `nf-k8s-${digest}.config`);
    const result = await runBackend(buildKubernetesConfigArgs(request, destination));
    if (result.code !== 0) throw new Error(result.stderr || "Kubernetes config generation failed");
    rememberAndReturn(destination, "config");
    return { path: destination };
  });
}

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1260,
    height: 820,
    minWidth: 980,
    minHeight: 680,
    title: "Helixsh",
    backgroundColor: "#07110f",
    webPreferences: {
      preload: path.join(__dirname, "preload.cjs"),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: true,
      webSecurity: true,
      allowRunningInsecureContent: false,
      webviewTag: false,
    },
  });

  mainWindow.webContents.setWindowOpenHandler(() => ({ action: "deny" }));
  mainWindow.webContents.on("will-navigate", (event) => event.preventDefault());
  if (!app.isPackaged && process.env.HELIXSH_CAPTURE_PATH) {
    mainWindow.webContents.once("did-finish-load", () => {
      setTimeout(async () => {
        if (process.env.HELIXSH_SMOKE_PLAN === "1") {
          const smokeOutput = path.join(app.getPath("temp"), "helixsh-smoke-output");
          fs.mkdirSync(smokeOutput, { recursive: true });
          rememberAndReturn(smokeOutput, "directory");
          await mainWindow.webContents.executeJavaScript(
            `document.getElementById('outputPath').value = ${JSON.stringify(smokeOutput)}; ` +
              "document.getElementById('run-form').requestSubmit()",
          );
          await new Promise((resolve) => setTimeout(resolve, 1000));
        }
        const image = await mainWindow.webContents.capturePage();
        fs.writeFileSync(process.env.HELIXSH_CAPTURE_PATH, image.toPNG());
        if (process.env.HELIXSH_CAPTURE_AND_EXIT === "1") app.quit();
      }, 1500);
    });
  }
  mainWindow.loadFile(path.join(__dirname, "renderer", "index.html"));
}

app.whenReady().then(() => {
  session.defaultSession.setPermissionRequestHandler((_webContents, _permission, callback) => {
    callback(false);
  });
  registerIpc();
  // Settle anything left over from a previous session before the window can
  // ask about it: runs that survived are followed again, and runs that did
  // not are recorded as such rather than left claiming to be running.
  try {
    const { adopted } = store().reconcile();
    for (const run of adopted) superviseAdopted(run);
  } catch (error) {
    process.stderr.write(`failed to reconcile previous runs: ${error.message}\n`);
  }
  createWindow();
  app.on("activate", () => {
    if (BrowserWindow.getAllWindows().length === 0) createWindow();
  });
});

app.on("before-quit", () => {
  // Runs are deliberately left alive. Quitting the window used to kill every
  // pipeline it had started, which for a job measured in hours meant closing
  // a laptop threw the work away. Children are detached and write to their
  // own log files, so they keep going and the next launch picks them up.
  for (const runId of [...tails.keys()]) unfollowRun(runId);
});

app.on("window-all-closed", () => {
  if (process.platform !== "darwin") app.quit();
});

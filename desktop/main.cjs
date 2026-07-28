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

const MAX_CAPTURE_BYTES = 2 * 1024 * 1024;
const selectedPaths = new Map();
const jobs = new Map();
let mainWindow = null;
let approvedPlan = null;

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
      if (captured >= MAX_CAPTURE_BYTES) return;
      const text = chunk.toString("utf8");
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

function terminateJob(child) {
  try {
    if (process.platform !== "win32" && child.pid) {
      process.kill(-child.pid, "SIGTERM");
      return true;
    }
    return child.kill("SIGTERM");
  } catch (error) {
    if (error.code === "ESRCH") return false;
    throw error;
  }
}

function startRun(request) {
  const backend = backendSpec();
  const args = buildRunArgs(request, { execute: true });
  const jobId = crypto.randomUUID();
  const child = spawn(backend.command, [...backend.prefix, ...args], {
    cwd: app.getPath("userData"),
    env: backend.env,
    shell: false,
    detached: process.platform !== "win32",
    stdio: ["ignore", "pipe", "pipe"],
  });
  jobs.set(jobId, child);

  for (const [streamName, stream] of [
    ["stdout", child.stdout],
    ["stderr", child.stderr],
  ]) {
    stream.on("data", (chunk) => {
      sendJobEvent({ jobId, type: "output", stream: streamName, text: chunk.toString("utf8") });
    });
  }
  child.once("error", (error) => {
    sendJobEvent({ jobId, type: "error", message: error.message });
  });
  child.once("close", (code, signal) => {
    jobs.delete(jobId);
    sendJobEvent({ jobId, type: "exit", code: code ?? 2, signal: signal || "" });
  });
  return { jobId };
}

async function assertRuntimeReady(runtime) {
  const result = await runBackend(["doctor", "--json"]);
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
    const result = await runBackend(["doctor", "--json"]);
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
    approvedPlan = null;
    return startRun(request);
  });

  ipcMain.handle("helixsh:cancel", async (event, jobId) => {
    assertTrustedSender(event);
    const child = jobs.get(String(jobId));
    if (!child) return { cancelled: false };
    return { cancelled: terminateJob(child) };
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
  createWindow();
  app.on("activate", () => {
    if (BrowserWindow.getAllWindows().length === 0) createWindow();
  });
});

app.on("before-quit", () => {
  for (const child of jobs.values()) terminateJob(child);
});

app.on("window-all-closed", () => {
  if (process.platform !== "darwin") app.quit();
});

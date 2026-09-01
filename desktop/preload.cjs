"use strict";

const { contextBridge, ipcRenderer } = require("electron");

contextBridge.exposeInMainWorld(
  "helixsh",
  Object.freeze({
    capabilities: () => ipcRenderer.invoke("helixsh:capabilities"),
    selectPath: (kind) => ipcRenderer.invoke("helixsh:select-path", kind),
    plan: (request) => ipcRenderer.invoke("helixsh:plan", request),
    start: (request) => ipcRenderer.invoke("helixsh:start", request),
    cancel: (runId) => ipcRenderer.invoke("helixsh:cancel", runId),
    runs: () => ipcRenderer.invoke("helixsh:runs"),
    openRun: (runId) => ipcRenderer.invoke("helixsh:open-run", runId),
    closeRun: (runId) => ipcRenderer.invoke("helixsh:close-run", runId),
    runResults: (runId) => ipcRenderer.invoke("helixsh:run-results", runId),
    pipelines: () => ipcRenderer.invoke("helixsh:pipelines"),
    buildSamplesheet: (request) => ipcRenderer.invoke("helixsh:build-samplesheet", request),
    validateSamplesheet: (request) => ipcRenderer.invoke("helixsh:validate-samplesheet", request),
    openResult: (runId, filePath) =>
      ipcRenderer.invoke("helixsh:open-result", { runId, path: filePath }),
    generateKubernetesConfig: (request) =>
      ipcRenderer.invoke("helixsh:generate-k8s-config", request),
    generateAwsBatchConfig: (request) =>
      ipcRenderer.invoke("helixsh:generate-aws-config", request),
    generateGoogleBatchConfig: (request) =>
      ipcRenderer.invoke("helixsh:generate-google-config", request),
    onJobEvent: (callback) => {
      if (typeof callback !== "function") throw new TypeError("callback must be a function");
      const listener = (_event, payload) => callback(payload);
      ipcRenderer.on("helixsh:job-event", listener);
      return () => ipcRenderer.removeListener("helixsh:job-event", listener);
    },
  }),
);

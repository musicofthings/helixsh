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
    generateKubernetesConfig: (request) =>
      ipcRenderer.invoke("helixsh:generate-k8s-config", request),
    onJobEvent: (callback) => {
      if (typeof callback !== "function") throw new TypeError("callback must be a function");
      const listener = (_event, payload) => callback(payload);
      ipcRenderer.on("helixsh:job-event", listener);
      return () => ipcRenderer.removeListener("helixsh:job-event", listener);
    },
  }),
);

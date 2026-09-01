"use strict";

/**
 * Durable record of pipeline runs.
 *
 * Runs outlive the window that started them. A pipeline takes hours, nobody
 * watches a laptop for hours, and the previous design lost a run entirely on
 * quit: output went through the parent's pipes and `before-quit` killed every
 * child. So each run owns a directory holding its metadata and its output,
 * the child writes to that log file directly rather than through us, and a
 * later launch reads the same files back.
 *
 * Deliberately free of Electron so it can be unit tested directly.
 */

const crypto = require("node:crypto");
const fs = require("node:fs");
const path = require("node:path");
const { spawnSync } = require("node:child_process");

const META = "meta.json";
const LOG = "output.log";

// Terminal states differ by what we actually observed, because "the process
// is gone" and "the run succeeded" are not the same claim.
const STATUS = Object.freeze({
  RUNNING: "running",
  COMPLETED: "completed",     // exited 0 while we were watching
  FAILED: "failed",           // exited non-zero while we were watching
  CANCELLED: "cancelled",     // stopped on request
  INTERRUPTED: "interrupted", // ended without us collecting an exit status
});

const TERMINAL = new Set([
  STATUS.COMPLETED,
  STATUS.FAILED,
  STATUS.CANCELLED,
  STATUS.INTERRUPTED,
]);

function isProcessAlive(pid) {
  if (!Number.isInteger(pid) || pid <= 0) return false;
  try {
    process.kill(pid, 0);
    return true;
  } catch (error) {
    // EPERM means the pid exists but belongs to another user, which for our
    // purposes still counts as alive.
    return error.code === "EPERM";
  }
}

/** Best-effort command line for a pid, or "" when the platform hides it. */
function processCommandLine(pid) {
  try {
    if (process.platform === "linux") {
      const raw = fs.readFileSync(`/proc/${pid}/cmdline`, "utf8");
      return raw.split("\0").filter(Boolean).join(" ");
    }
    if (process.platform === "darwin") {
      const probe = spawnSync("ps", ["-o", "command=", "-p", String(pid)], {
        encoding: "utf8",
        timeout: 5000,
      });
      return probe.status === 0 ? probe.stdout.trim() : "";
    }
  } catch {
    return "";
  }
  return "";
}

/**
 * Is this pid still the process we started?
 *
 * A bare liveness check is not enough: pids are recycled, and after a reboot
 * or a long absence the number may belong to something else entirely.
 * Presenting a stranger's process as the user's pipeline would be worse than
 * reporting the run as interrupted, so an identifiable mismatch wins. When
 * the platform will not tell us the command line we cannot distinguish the
 * cases, and fall back to liveness alone.
 */
function processMatches(pid, marker) {
  if (!isProcessAlive(pid)) return false;
  if (!marker) return true;
  const commandLine = processCommandLine(pid);
  if (!commandLine) return true;
  return commandLine.includes(marker);
}

function readJson(file) {
  try {
    return JSON.parse(fs.readFileSync(file, "utf8"));
  } catch {
    return null;
  }
}

function writeJsonAtomic(file, value) {
  // A crash between truncate and write would leave unreadable metadata and
  // orphan the run, so publish by rename instead.
  const temporary = `${file}.${process.pid}.tmp`;
  fs.writeFileSync(temporary, JSON.stringify(value, null, 2), { mode: 0o600 });
  fs.renameSync(temporary, file);
}

function createRunStore(rootDirectory) {
  fs.mkdirSync(rootDirectory, { recursive: true, mode: 0o700 });

  const runDirectory = (runId) => path.join(rootDirectory, runId);
  const metaPath = (runId) => path.join(runDirectory(runId), META);
  const logPath = (runId) => path.join(runDirectory(runId), LOG);

  function read(runId) {
    return readJson(metaPath(runId));
  }

  function update(runId, patch) {
    const current = read(runId);
    if (!current) return null;
    const next = { ...current, ...patch };
    writeJsonAtomic(metaPath(runId), next);
    return next;
  }

  return {
    root: rootDirectory,
    logPath,
    read,
    update,

    /** Allocate a run directory before spawning, so the log has somewhere to go. */
    create({ request, command, pipeline }) {
      const runId = crypto.randomUUID();
      fs.mkdirSync(runDirectory(runId), { recursive: true, mode: 0o700 });
      fs.writeFileSync(logPath(runId), "", { mode: 0o600 });
      const run = {
        runId,
        pipeline: pipeline || request?.pipeline || "",
        command,
        request,
        status: STATUS.RUNNING,
        pid: null,
        marker: "",
        startedAt: new Date().toISOString(),
        finishedAt: null,
        exitCode: null,
        signal: "",
      };
      writeJsonAtomic(metaPath(runId), run);
      return run;
    },

    /** Append-mode fd handed straight to the child, so output survives us. */
    openLog(runId) {
      return fs.openSync(logPath(runId), "a");
    },

    /** Record the pid once the child exists. */
    attach(runId, { pid, marker }) {
      return update(runId, { pid, marker: marker || "" });
    },

    markFinished(runId, { exitCode, signal } = {}) {
      const status = signal
        ? STATUS.CANCELLED
        : exitCode === 0
          ? STATUS.COMPLETED
          : STATUS.FAILED;
      return update(runId, {
        status,
        exitCode: exitCode ?? null,
        signal: signal || "",
        finishedAt: new Date().toISOString(),
      });
    },

    markCancelled(runId) {
      return update(runId, {
        status: STATUS.CANCELLED,
        finishedAt: new Date().toISOString(),
      });
    },

    /** Newest first; unreadable directories are skipped rather than fatal. */
    list() {
      let entries = [];
      try {
        entries = fs.readdirSync(rootDirectory, { withFileTypes: true });
      } catch {
        return [];
      }
      return entries
        .filter((entry) => entry.isDirectory())
        .map((entry) => readJson(path.join(rootDirectory, entry.name, META)))
        .filter((run) => run && run.runId)
        .sort((a, b) => String(b.startedAt).localeCompare(String(a.startedAt)));
    },

    /**
     * Settle what happened while no window was open.
     *
     * Anything still marked running either survived -- and can be followed
     * again -- or died unobserved. The second case cannot report an exit code:
     * we were not its parent, so nobody collected one. Saying "interrupted"
     * is the honest answer, and better than guessing from the log.
     */
    reconcile() {
      const adopted = [];
      const interrupted = [];
      for (const run of this.list()) {
        if (run.status !== STATUS.RUNNING) continue;
        if (run.pid && processMatches(run.pid, run.marker)) {
          adopted.push(run);
        } else {
          interrupted.push(
            update(run.runId, {
              status: STATUS.INTERRUPTED,
              finishedAt: new Date().toISOString(),
            }),
          );
        }
      }
      return { adopted, interrupted };
    },
  };
}

module.exports = {
  STATUS,
  TERMINAL,
  createRunStore,
  isProcessAlive,
  processCommandLine,
  processMatches,
};

"use strict";

const assert = require("node:assert/strict");
const test = require("node:test");
const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");
const { spawn, spawnSync } = require("node:child_process");

const {
  STATUS,
  createRunStore,
  isProcessAlive,
  processMatches,
} = require("../lib/runstore.cjs");

function tempStore() {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), "helixsh-runs-"));
  return { store: createRunStore(path.join(root, "runs")), root };
}

const REQUEST = { pipeline: "rnaseq", runtime: "docker" };

test("records a run before it is spawned, so output has somewhere to go", () => {
  const { store } = tempStore();
  const run = store.create({ request: REQUEST, command: "nextflow run x" });

  assert.equal(run.status, STATUS.RUNNING);
  assert.equal(run.pipeline, "rnaseq");
  assert.ok(fs.existsSync(store.logPath(run.runId)));
  assert.equal(store.read(run.runId).command, "nextflow run x");
});

test("keeps runs across store instances, which is the whole point", () => {
  const { store, root } = tempStore();
  const run = store.create({ request: REQUEST, command: "nextflow run x" });

  // A fresh store is what a relaunched app gets.
  const reopened = createRunStore(path.join(root, "runs"));
  assert.equal(reopened.read(run.runId).runId, run.runId);
  assert.equal(reopened.list().length, 1);
});

test("distinguishes how a run ended rather than only that it ended", () => {
  const { store } = tempStore();
  const ok = store.create({ request: REQUEST, command: "c" });
  const bad = store.create({ request: REQUEST, command: "c" });
  const stopped = store.create({ request: REQUEST, command: "c" });

  assert.equal(store.markFinished(ok.runId, { exitCode: 0 }).status, STATUS.COMPLETED);
  assert.equal(store.markFinished(bad.runId, { exitCode: 2 }).status, STATUS.FAILED);
  assert.equal(
    store.markFinished(stopped.runId, { exitCode: null, signal: "SIGTERM" }).status,
    STATUS.CANCELLED,
  );
  assert.ok(store.read(ok.runId).finishedAt);
});

test("lists newest first", async () => {
  const { store } = tempStore();
  const first = store.create({ request: REQUEST, command: "c" });
  await new Promise((resolve) => setTimeout(resolve, 10));
  const second = store.create({ request: REQUEST, command: "c" });

  assert.deepEqual(store.list().map((r) => r.runId), [second.runId, first.runId]);
});

test("adopts a run whose process is still alive", () => {
  const { store, root } = tempStore();
  const child = spawn(process.execPath, ["-e", "setTimeout(()=>{}, 60000)"], {
    stdio: "ignore",
  });
  try {
    const run = store.create({ request: REQUEST, command: "c" });
    store.attach(run.runId, { pid: child.pid, marker: "" });

    const { adopted, interrupted } = createRunStore(path.join(root, "runs")).reconcile();

    assert.equal(interrupted.length, 0);
    assert.deepEqual(adopted.map((r) => r.runId), [run.runId]);
  } finally {
    child.kill("SIGKILL");
  }
});

test("marks a run interrupted when its process is gone", () => {
  const { store, root } = tempStore();
  const run = store.create({ request: REQUEST, command: "c" });
  // A pid that has certainly exited: spawn and reap one.
  const dead = spawnSync(process.execPath, ["-e", ""]);
  store.attach(run.runId, { pid: dead.pid, marker: "" });

  const { adopted, interrupted } = createRunStore(path.join(root, "runs")).reconcile();

  assert.equal(adopted.length, 0);
  assert.equal(interrupted.length, 1);
  const settled = store.read(run.runId);
  assert.equal(settled.status, STATUS.INTERRUPTED);
  // We were not its parent, so there is no exit code to report and claiming
  // one would be a lie.
  assert.equal(settled.exitCode, null);
  assert.ok(settled.finishedAt);
});

test("does not adopt a recycled pid belonging to another process", () => {
  const { store, root } = tempStore();
  const child = spawn(process.execPath, ["-e", "setTimeout(()=>{}, 60000)"], {
    stdio: "ignore",
  });
  try {
    const run = store.create({ request: REQUEST, command: "c" });
    // Alive, but its command line cannot contain this marker.
    store.attach(run.runId, { pid: child.pid, marker: "definitely-not-this-process" });

    const { adopted, interrupted } = createRunStore(path.join(root, "runs")).reconcile();

    if (processMatches(child.pid, "")) {
      // Only meaningful where the platform exposes a command line at all.
      const canInspect = process.platform === "linux" || process.platform === "darwin";
      if (canInspect) {
        assert.equal(adopted.length, 0, "a mismatched pid must not be adopted");
        assert.equal(interrupted.length, 1);
      }
    }
  } finally {
    child.kill("SIGKILL");
  }
});

test("reconcile leaves already-finished runs alone", () => {
  const { store, root } = tempStore();
  const run = store.create({ request: REQUEST, command: "c" });
  store.markFinished(run.runId, { exitCode: 0 });

  const { adopted, interrupted } = createRunStore(path.join(root, "runs")).reconcile();

  assert.equal(adopted.length, 0);
  assert.equal(interrupted.length, 0);
  assert.equal(store.read(run.runId).status, STATUS.COMPLETED);
});

test("a child writing to the log outlives the process that started it", async () => {
  const { store, root } = tempStore();
  const run = store.create({ request: REQUEST, command: "c" });
  const fd = store.openLog(run.runId);
  // Detached, with stdout wired straight to the file: this is the arrangement
  // that lets output survive when the app quits.
  const child = spawn(
    process.execPath,
    ["-e", "console.log('before'); setTimeout(()=>{console.log('after'); process.exit(0)}, 300)"],
    { detached: true, stdio: ["ignore", fd, fd] },
  );
  fs.closeSync(fd);
  child.unref();

  await new Promise((resolve) => setTimeout(resolve, 900));

  const written = fs.readFileSync(
    createRunStore(path.join(root, "runs")).logPath(run.runId),
    "utf8",
  );
  assert.match(written, /before/);
  assert.match(written, /after/);
});

test("isProcessAlive reports honestly for a reaped pid", () => {
  const dead = spawnSync(process.execPath, ["-e", ""]);
  assert.equal(isProcessAlive(dead.pid), false);
  assert.equal(isProcessAlive(process.pid), true);
  assert.equal(isProcessAlive(0), false);
  assert.equal(isProcessAlive(-1), false);
});

test("survives a corrupt meta file instead of losing every other run", () => {
  const { store } = tempStore();
  const good = store.create({ request: REQUEST, command: "c" });
  const broken = store.create({ request: REQUEST, command: "c" });
  fs.writeFileSync(path.join(store.root, broken.runId, "meta.json"), "{not json");

  const listed = store.list();

  assert.deepEqual(listed.map((r) => r.runId), [good.runId]);
});

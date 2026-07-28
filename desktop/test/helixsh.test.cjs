"use strict";

const assert = require("node:assert/strict");
const test = require("node:test");
const {
  buildKubernetesConfigArgs,
  buildRunArgs,
  normalizePipeline,
  requiredCapabilities,
  validateKubernetesRequest,
  validateRunRequest,
} = require("../lib/helixsh.cjs");

test("normalizes an nf-core pipeline without accepting another organization", () => {
  assert.equal(normalizePipeline("nf-core/RNASeq"), "rnaseq");
  assert.throws(() => normalizePipeline("other/pipeline"), /nf-core pipeline name/);
});

test("builds a constrained Docker execution request", () => {
  const args = buildRunArgs(
    {
      pipeline: "rnaseq",
      runtime: "docker",
      inputPath: "/data/samples.csv",
      outputPath: "/data/results",
      resume: true,
    },
    { execute: true },
  );
  assert.deepEqual(args, [
    "--strict",
    "run",
    "nf-core",
    "rnaseq",
    "--runtime",
    "docker",
    "--input",
    "/data/samples.csv",
    "--nf-arg=--outdir",
    "--nf-arg",
    "/data/results",
    "--resume",
    "--execute",
    "--yes",
  ]);
});

test("rejects Kubernetes execution without an nf-k8s config", () => {
  assert.throws(
    () => validateRunRequest({ pipeline: "sarek", runtime: "kubernetes" }),
    /require a generated or selected nf-k8s config/,
  );
});

test("validates Kubernetes settings and builds config generation args", () => {
  const request = validateKubernetesRequest({
    namespace: "genomics",
    serviceAccount: "nextflow",
    storageClaim: "nextflow-pvc",
    storageMountPath: "/workspace",
  });
  assert.equal(request.namespace, "genomics");
  assert.deepEqual(
    buildKubernetesConfigArgs(request, "/tmp/helixsh-k8s.config").slice(0, 3),
    ["k8s-config", "--namespace", "genomics"],
  );
});

test("rejects Kubernetes namespace and mount-path injection", () => {
  assert.throws(
    () =>
      validateKubernetesRequest({
        namespace: "team.alpha",
        serviceAccount: "nextflow",
        storageClaim: "nextflow-pvc",
      }),
    /valid lowercase Kubernetes name/,
  );
  assert.throws(
    () =>
      validateKubernetesRequest({
        namespace: "default",
        serviceAccount: "nextflow",
        storageClaim: "nextflow-pvc",
        storageMountPath: "/workspace/../etc",
      }),
    /normalized absolute path/,
  );
});

test("requires schema and params files as a pair", () => {
  assert.throws(
    () => validateRunRequest({ pipeline: "rnaseq", schemaPath: "/tmp/schema.json" }),
    /selected together/,
  );
});

test("maps execution targets to runtime readiness capabilities", () => {
  assert.deepEqual(requiredCapabilities("docker"), ["nextflow", "docker"]);
  assert.deepEqual(requiredCapabilities("kubernetes"), ["nextflow", "kubernetes"]);
});

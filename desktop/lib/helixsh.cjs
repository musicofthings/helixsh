"use strict";

const path = require("node:path");

const RUNTIMES = new Set(["docker", "podman", "singularity", "apptainer", "kubernetes"]);
const PIPELINE_RE = /^[a-z0-9][a-z0-9_-]{0,63}$/;
const REVISION_RE = /^[a-zA-Z0-9][a-zA-Z0-9._/-]{0,127}$/;
const K8S_LABEL_RE = /^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$/;
// Mirrors helixsh.kubernetes.K8S_MOUNT_PATH_RE. The value is interpolated into
// a single-quoted Groovy string, where a trailing backslash escapes the closing
// quote, so this allow-lists path characters instead of denying dangerous ones.
const K8S_MOUNT_PATH_RE = /^\/(?:[A-Za-z0-9._-]+(?:\/[A-Za-z0-9._-]+)*)?$/;
const MAX_PATH_LENGTH = 4096;

function optionalPath(value, field) {
  if (value === undefined || value === null || value === "") {
    return "";
  }
  if (typeof value !== "string" || value.length > MAX_PATH_LENGTH || value.includes("\0")) {
    throw new TypeError(`${field} is not a valid path`);
  }
  return path.resolve(value);
}

function normalizePipeline(value) {
  if (typeof value !== "string") {
    throw new TypeError("pipeline is required");
  }
  let pipeline = value.trim().toLowerCase();
  if (pipeline.startsWith("nf-core/")) {
    pipeline = pipeline.slice("nf-core/".length);
  }
  if (!PIPELINE_RE.test(pipeline)) {
    throw new TypeError("pipeline must be an nf-core pipeline name");
  }
  return pipeline;
}

function validateRunRequest(payload) {
  if (!payload || typeof payload !== "object" || Array.isArray(payload)) {
    throw new TypeError("run request must be an object");
  }

  const runtime = String(payload.runtime || "docker").trim().toLowerCase();
  if (!RUNTIMES.has(runtime)) {
    throw new TypeError(`unsupported runtime: ${runtime}`);
  }

  const request = {
    pipeline: normalizePipeline(payload.pipeline),
    revision: String(payload.revision || "").trim(),
    runtime,
    inputPath: optionalPath(payload.inputPath, "inputPath"),
    outputPath: optionalPath(payload.outputPath, "outputPath"),
    workflowPath: optionalPath(payload.workflowPath, "workflowPath"),
    schemaPath: optionalPath(payload.schemaPath, "schemaPath"),
    paramsPath: optionalPath(payload.paramsPath, "paramsPath"),
    configPath: optionalPath(payload.configPath, "configPath"),
    cacheRoot: optionalPath(payload.cacheRoot, "cacheRoot"),
    image: String(payload.image || "").trim(),
    resume: payload.resume === true,
    offline: payload.offline === true,
  };

  if (request.revision && !REVISION_RE.test(request.revision)) {
    throw new TypeError("revision contains unsupported characters");
  }
  if (Boolean(request.schemaPath) !== Boolean(request.paramsPath)) {
    throw new TypeError("schema and params files must be selected together");
  }
  if (request.runtime === "kubernetes" && !request.configPath) {
    throw new TypeError("Kubernetes runs require a generated or selected nf-k8s config");
  }
  // The generated config pins `process.executor = 'k8s'`, which overrides the
  // selected profile. Carrying one over from an earlier Kubernetes session
  // would route a "Local Docker" run at a cluster while readiness was only
  // checked for Docker, so the two must not be combined.
  if (request.runtime !== "kubernetes" && request.configPath) {
    throw new TypeError("an nf-k8s config applies only to Kubernetes runs");
  }
  if (request.image.length > 512 || /[\r\n\0]/.test(request.image)) {
    throw new TypeError("image reference is invalid");
  }
  return Object.freeze(request);
}

function buildRunArgs(payload, options = {}) {
  const request = validateRunRequest(payload);
  const args = [];
  if (options.execute === true) {
    args.push("--strict");
  }
  args.push("run", "nf-core", request.pipeline, "--runtime", request.runtime);

  const pathOptions = [
    ["--input", request.inputPath],
    ["--workflow", request.workflowPath],
    ["--schema", request.schemaPath],
    ["--params", request.paramsPath],
    ["--config", request.configPath],
    ["--cache-root", request.cacheRoot],
  ];
  for (const [flag, value] of pathOptions) {
    if (value) {
      args.push(flag, value);
    }
  }
  if (request.image) {
    args.push("--image", request.image);
  }
  if (request.revision) {
    args.push("--nf-arg=-r", "--nf-arg", request.revision);
  }
  if (request.outputPath) {
    args.push("--nf-arg=--outdir", "--nf-arg", request.outputPath);
  }
  if (request.resume) {
    args.push("--resume");
  }
  if (request.offline) {
    args.push("--offline");
  }
  if (options.execute === true) {
    args.push("--execute", "--yes");
  }
  return args;
}

function validateKubernetesRequest(payload) {
  if (!payload || typeof payload !== "object" || Array.isArray(payload)) {
    throw new TypeError("Kubernetes request must be an object");
  }
  const result = {
    namespace: String(payload.namespace || "default").trim().toLowerCase(),
    serviceAccount: String(payload.serviceAccount || "nextflow").trim().toLowerCase(),
    storageClaim: String(payload.storageClaim || "").trim().toLowerCase(),
    storageMountPath: String(payload.storageMountPath || "/workspace").trim(),
  };
  // There is no sane default for a cluster's PVC, so say that plainly rather
  // than letting the empty string fall through to a name-format complaint.
  if (!result.storageClaim) {
    throw new TypeError("storage claim is required");
  }
  for (const [field, value, subdomain] of [
    ["namespace", result.namespace, false],
    ["service account", result.serviceAccount, true],
    ["storage claim", result.storageClaim, true],
  ]) {
    const labels = subdomain ? value.split(".") : [value];
    if (
      !value ||
      value.length > (subdomain ? 253 : 63) ||
      labels.some((label) => !K8S_LABEL_RE.test(label))
    ) {
      throw new TypeError(`${field} must be a valid lowercase Kubernetes name`);
    }
  }
  if (
    !K8S_MOUNT_PATH_RE.test(result.storageMountPath) ||
    path.posix.normalize(result.storageMountPath) !== result.storageMountPath
  ) {
    throw new TypeError("storage mount path must be a normalized absolute path");
  }
  return Object.freeze(result);
}

function buildKubernetesConfigArgs(payload, outputPath) {
  const request = validateKubernetesRequest(payload);
  const destination = optionalPath(outputPath, "outputPath");
  if (!destination) {
    throw new TypeError("outputPath is required");
  }
  return [
    "k8s-config",
    "--namespace",
    request.namespace,
    "--service-account",
    request.serviceAccount,
    "--storage-claim",
    request.storageClaim,
    "--storage-mount-path",
    request.storageMountPath,
    "--out",
    destination,
  ];
}

// nf-core's rnaseq samplesheet takes one of these; anything else is a typo.
const STRANDEDNESS = new Set(["auto", "forward", "reverse", "unstranded"]);

/**
 * Build a samplesheet from a directory of FASTQ files.
 *
 * The generated sheet is written somewhere the app controls rather than into
 * the user's data directory: writing next to someone's sequencing run is
 * presumptuous, and a path the app produced is one it can also approve for
 * execution.
 */
function buildSamplesheetGenerateArgs(payload) {
  if (!payload || typeof payload !== "object" || Array.isArray(payload)) {
    throw new TypeError("samplesheet request must be an object");
  }
  const fastqDir = optionalPath(payload.fastqDir, "fastqDir");
  if (!fastqDir) {
    throw new TypeError("a FASTQ directory is required");
  }
  const out = optionalPath(payload.out, "out");
  if (!out) {
    throw new TypeError("an output path is required");
  }
  const args = [
    "samplesheet-generate",
    "--fastq-dir",
    fastqDir,
    "--pipeline",
    normalizePipeline(payload.pipeline),
    "--out",
    out,
  ];
  const strandedness = String(payload.strandedness || "").trim();
  if (strandedness) {
    if (!STRANDEDNESS.has(strandedness)) {
      throw new TypeError(`unsupported strandedness: ${strandedness}`);
    }
    args.push("--strandedness", strandedness);
  }
  return args;
}

function buildSamplesheetValidateArgs(payload) {
  if (!payload || typeof payload !== "object" || Array.isArray(payload)) {
    throw new TypeError("validation request must be an object");
  }
  const file = optionalPath(payload.file, "file");
  if (!file) {
    throw new TypeError("a samplesheet path is required");
  }
  return [
    "samplesheet-validate",
    "--file",
    file,
    "--pipeline",
    normalizePipeline(payload.pipeline),
  ];
}

function requiredCapabilities(runtime) {
  const normalized = String(runtime || "").trim().toLowerCase();
  if (!RUNTIMES.has(normalized)) {
    throw new TypeError(`unsupported runtime: ${normalized}`);
  }
  return ["nextflow", normalized === "kubernetes" ? "kubernetes" : normalized];
}

module.exports = {
  RUNTIMES,
  STRANDEDNESS,
  buildKubernetesConfigArgs,
  buildRunArgs,
  buildSamplesheetGenerateArgs,
  buildSamplesheetValidateArgs,
  normalizePipeline,
  requiredCapabilities,
  validateKubernetesRequest,
  validateRunRequest,
};

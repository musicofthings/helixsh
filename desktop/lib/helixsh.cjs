"use strict";

const path = require("node:path");

const RUNTIMES = new Set([
  "docker",
  "podman",
  "singularity",
  "apptainer",
  "kubernetes",
  "awsbatch",
  "googlebatch",
]);

// Mirrors helixsh.nextflow.CONFIG_REQUIRED_RUNTIMES. These are executors, not
// container profiles: they cannot be configured from the command line alone,
// and running one without a config fails at submission rather than here.
const CONFIG_REQUIRED_RUNTIMES = new Set(["kubernetes", "awsbatch", "googlebatch"]);

// What to call each executor when talking to the user.
const RUNTIME_LABELS = Object.freeze({
  kubernetes: "Kubernetes",
  awsbatch: "AWS Batch",
  googlebatch: "Google Batch",
});
const PIPELINE_RE = /^[a-z0-9][a-z0-9_-]{0,63}$/;
const REVISION_RE = /^[a-zA-Z0-9][a-zA-Z0-9._/-]{0,127}$/;
const K8S_LABEL_RE = /^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$/;
// Mirrors helixsh.kubernetes.K8S_MOUNT_PATH_RE. The value is interpolated into
// a single-quoted Groovy string, where a trailing backslash escapes the closing
// quote, so this allow-lists path characters instead of denying dangerous ones.
const K8S_MOUNT_PATH_RE = /^\/(?:[A-Za-z0-9._-]+(?:\/[A-Za-z0-9._-]+)*)?$/;
// Mirror helixsh.cloud_batch. The backend validates these again before writing
// anything, but repeating the rules here means a typo is a specific message
// next to the field rather than a backend exit code in the console -- and the
// main process never hands an unchecked value to a subprocess.
const AWS_REGION_RE = /^[a-z]{2}(?:-[a-z]+)+-\d$/;
const AWS_QUEUE_RE = /^[A-Za-z0-9][A-Za-z0-9_-]{0,127}$/;
const GCP_PROJECT_RE = /^[a-z][a-z0-9-]{4,28}[a-z0-9]$/;
const GCP_LOCATION_RE = /^[a-z]+-[a-z]+\d$/;
const BUCKET_RE = /^[a-z0-9][a-z0-9.-]{1,61}[a-z0-9]$/;
const OBJECT_PREFIX_RE = /^(?:[A-Za-z0-9._-]+(?:\/[A-Za-z0-9._-]+)*)?$/;
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
  const needsConfig = CONFIG_REQUIRED_RUNTIMES.has(request.runtime);
  if (needsConfig && !request.configPath) {
    throw new TypeError(
      `${RUNTIME_LABELS[request.runtime]} runs require a generated executor config`,
    );
  }
  // A generated config pins `process.executor`, which overrides the selected
  // profile. Carrying one over from an earlier session would route a "Local
  // Docker" run at a cluster while readiness was only checked for Docker.
  // Which executor a config names is not visible in its path, so the main
  // process pins each generated config to the runtime that produced it; this
  // only rules out attaching one where no executor was chosen at all.
  if (!needsConfig && request.configPath) {
    throw new TypeError("an executor config applies only to the executor it configures");
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

// ── cloud executors ─────────────────────────────────────────────────────────

function checkAgainst(field, value, pattern, expectation) {
  const normalized = String(value ?? "").trim();
  if (!pattern.test(normalized)) {
    throw new TypeError(`${field} ${expectation}`);
  }
  return normalized;
}

function checkBucket(value) {
  const bucket = checkAgainst(
    "bucket",
    value,
    BUCKET_RE,
    "must be 3-63 characters of lowercase letters, digits, dots or hyphens",
  );
  // Both providers reject these, and finding out at submission time costs a
  // round trip to the cloud to learn something checkable here.
  if (bucket.includes("..")) {
    throw new TypeError("bucket must not contain consecutive dots");
  }
  if (/^\d+(?:\.\d+){3}$/.test(bucket)) {
    throw new TypeError("bucket must not look like an IP address");
  }
  return bucket;
}

function checkPrefix(value) {
  const prefix = String(value ?? "").trim().replace(/^\/+|\/+$/g, "");
  if (!OBJECT_PREFIX_RE.test(prefix)) {
    throw new TypeError(
      "prefix must be a plain object path of letters, digits, dots, hyphens and underscores",
    );
  }
  // Dots are legal inside a segment, but a segment that is only dots is a
  // relative path element. Object keys are flat so it traverses nowhere, and
  // it produces a key nobody meant.
  if (prefix.split("/").some((segment) => segment === "." || segment === "..")) {
    throw new TypeError("prefix must not contain '.' or '..' segments");
  }
  return prefix;
}

function validateAwsBatchRequest(payload) {
  if (!payload || typeof payload !== "object" || Array.isArray(payload)) {
    throw new TypeError("AWS Batch request must be an object");
  }
  return Object.freeze({
    region: checkAgainst(
      "region",
      payload.region,
      AWS_REGION_RE,
      "must be an AWS region such as eu-west-1",
    ),
    jobQueue: checkAgainst(
      "job queue",
      payload.jobQueue,
      AWS_QUEUE_RE,
      "must be an AWS Batch job queue name",
    ),
    bucket: checkBucket(payload.bucket),
    prefix: checkPrefix(payload.prefix),
  });
}

function validateGoogleBatchRequest(payload) {
  if (!payload || typeof payload !== "object" || Array.isArray(payload)) {
    throw new TypeError("Google Batch request must be an object");
  }
  return Object.freeze({
    project: checkAgainst(
      "project",
      payload.project,
      GCP_PROJECT_RE,
      "must be a Google Cloud project id of 6-30 characters",
    ),
    location: checkAgainst(
      "location",
      payload.location,
      GCP_LOCATION_RE,
      "must be a Google Cloud location such as us-central1",
    ),
    bucket: checkBucket(payload.bucket),
    prefix: checkPrefix(payload.prefix),
  });
}

function configDestination(outputPath) {
  const destination = optionalPath(outputPath, "outputPath");
  if (!destination) {
    throw new TypeError("outputPath is required");
  }
  return destination;
}

function buildAwsBatchConfigArgs(payload, outputPath) {
  const request = validateAwsBatchRequest(payload);
  const args = [
    "aws-batch-config",
    "--region",
    request.region,
    "--job-queue",
    request.jobQueue,
    "--bucket",
    request.bucket,
  ];
  if (request.prefix) {
    args.push("--prefix", request.prefix);
  }
  args.push("--out", configDestination(outputPath));
  return args;
}

function buildGoogleBatchConfigArgs(payload, outputPath) {
  const request = validateGoogleBatchRequest(payload);
  const args = [
    "google-batch-config",
    "--project",
    request.project,
    "--location",
    request.location,
    "--bucket",
    request.bucket,
  ];
  if (request.prefix) {
    args.push("--prefix", request.prefix);
  }
  args.push("--out", configDestination(outputPath));
  return args;
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

/**
 * What must be working locally before a run of this kind may start.
 *
 * The cloud executors need nothing beyond Nextflow itself: the provider CLIs
 * are not involved in submission, and credentials come from the environment,
 * an instance profile or the metadata server. A host inside the provider is
 * issued credentials with no local configuration at all, so gating on a
 * credential check here would block the runs most likely to succeed. Where
 * they will come from is reported alongside the runtimes instead, so the user
 * sees it before submitting rather than minutes afterwards.
 */
function requiredCapabilities(runtime) {
  const normalized = String(runtime || "").trim().toLowerCase();
  if (!RUNTIMES.has(normalized)) {
    throw new TypeError(`unsupported runtime: ${normalized}`);
  }
  if (normalized === "awsbatch" || normalized === "googlebatch") {
    return ["nextflow"];
  }
  return ["nextflow", normalized === "kubernetes" ? "kubernetes" : normalized];
}

module.exports = {
  RUNTIMES,
  RUNTIME_LABELS,
  STRANDEDNESS,
  buildAwsBatchConfigArgs,
  buildGoogleBatchConfigArgs,
  buildKubernetesConfigArgs,
  buildRunArgs,
  buildSamplesheetGenerateArgs,
  buildSamplesheetValidateArgs,
  normalizePipeline,
  requiredCapabilities,
  validateAwsBatchRequest,
  validateGoogleBatchRequest,
  validateKubernetesRequest,
  validateRunRequest,
};

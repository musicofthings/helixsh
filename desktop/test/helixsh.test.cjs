"use strict";

const assert = require("node:assert/strict");
const test = require("node:test");
const {
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

test("rejects an executor run with no generated config", () => {
  // Each of these pins process.executor from a file; without it the run
  // reaches Nextflow and fails at submission instead of here.
  for (const [runtime, expected] of [
    ["kubernetes", /Kubernetes runs require a generated executor config/],
    ["awsbatch", /AWS Batch runs require a generated executor config/],
    ["googlebatch", /Google Batch runs require a generated executor config/],
  ]) {
    assert.throws(() => validateRunRequest({ pipeline: "sarek", runtime }), expected);
  }
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

test("rejects a backslash that would escape the Groovy closing quote", () => {
  for (const storageMountPath of ["/work\\", "/work$hell", "/work'", "/work space"]) {
    assert.throws(
      () =>
        validateKubernetesRequest({
          namespace: "default",
          serviceAccount: "nextflow",
          storageClaim: "nextflow-pvc",
          storageMountPath,
        }),
      /normalized absolute path/,
      `expected ${storageMountPath} to be rejected`,
    );
  }
});

test("reports a missing storage claim as missing rather than malformed", () => {
  assert.throws(
    () => validateKubernetesRequest({ namespace: "default", serviceAccount: "nextflow" }),
    /storage claim is required/,
  );
});

test("refuses an executor config on a run that chose no executor", () => {
  const request = {
    pipeline: "rnaseq",
    runtime: "docker",
    outputPath: "/data/results",
    configPath: "/home/u/.config/helixsh-desktop/kubernetes/nf-k8s-abc.config",
  };
  assert.throws(() => validateRunRequest(request), /applies only to the executor it configures/);
  assert.throws(() => buildRunArgs(request), /applies only to the executor it configures/);
});

test("still threads the config through a Kubernetes run", () => {
  const args = buildRunArgs({
    pipeline: "sarek",
    runtime: "kubernetes",
    configPath: "/cfg/nf-k8s.config",
  });
  assert.deepEqual(args, [
    "run",
    "nf-core",
    "sarek",
    "--runtime",
    "kubernetes",
    "--config",
    "/cfg/nf-k8s.config",
  ]);
});

test("builds a samplesheet generation command from a FASTQ directory", () => {
  const args = buildSamplesheetGenerateArgs({
    fastqDir: "/data/fastq",
    pipeline: "rnaseq",
    out: "/app/sheets/generated.csv",
  });
  assert.deepEqual(args, [
    "samplesheet-generate",
    "--fastq-dir",
    "/data/fastq",
    "--pipeline",
    "rnaseq",
    "--out",
    "/app/sheets/generated.csv",
  ]);
});

test("passes strandedness through only when it is one nf-core accepts", () => {
  const args = buildSamplesheetGenerateArgs({
    fastqDir: "/data/fastq",
    pipeline: "rnaseq",
    out: "/out.csv",
    strandedness: "reverse",
  });
  assert.deepEqual(args.slice(-2), ["--strandedness", "reverse"]);

  assert.throws(
    () => buildSamplesheetGenerateArgs({
      fastqDir: "/d", pipeline: "rnaseq", out: "/o.csv", strandedness: "sideways",
    }),
    /unsupported strandedness/,
  );
});

test("a samplesheet cannot be generated without somewhere to read or write", () => {
  assert.throws(
    () => buildSamplesheetGenerateArgs({ pipeline: "rnaseq", out: "/o.csv" }),
    /FASTQ directory is required/,
  );
  assert.throws(
    () => buildSamplesheetGenerateArgs({ fastqDir: "/d", pipeline: "rnaseq" }),
    /output path is required/,
  );
});

test("samplesheet generation refuses a pipeline name it would not run", () => {
  assert.throws(
    () => buildSamplesheetGenerateArgs({
      fastqDir: "/d", out: "/o.csv", pipeline: "../../etc/passwd",
    }),
    /nf-core pipeline name/,
  );
});

test("builds a samplesheet validation command", () => {
  assert.deepEqual(
    buildSamplesheetValidateArgs({ file: "/data/sheet.csv", pipeline: "nf-core/sarek" }),
    ["samplesheet-validate", "--file", "/data/sheet.csv", "--pipeline", "sarek"],
  );
  assert.throws(
    () => buildSamplesheetValidateArgs({ pipeline: "rnaseq" }),
    /samplesheet path is required/,
  );
});

// ── cloud executors ─────────────────────────────────────────────────────────

const AWS = { region: "eu-west-1", jobQueue: "genomics-spot", bucket: "my-lab-nf" };
const GCP = { project: "my-lab-project", location: "us-central1", bucket: "my-lab-nf" };

test("builds AWS Batch config arguments the backend accepts", () => {
  assert.deepEqual(buildAwsBatchConfigArgs(AWS, "/cfg/aws.config"), [
    "aws-batch-config",
    "--region", "eu-west-1",
    "--job-queue", "genomics-spot",
    "--bucket", "my-lab-nf",
    "--out", "/cfg/aws.config",
  ]);
});

test("passes a key prefix only when there is one", () => {
  // The backend defaults --prefix to empty, so sending "" would be noise in
  // the command the user is shown.
  const withPrefix = buildAwsBatchConfigArgs({ ...AWS, prefix: "runs/2026" }, "/cfg/aws.config");

  assert.ok(withPrefix.includes("--prefix"));
  assert.equal(withPrefix[withPrefix.indexOf("--prefix") + 1], "runs/2026");
  assert.ok(!buildAwsBatchConfigArgs({ ...AWS, prefix: "  " }, "/cfg/a.config").includes("--prefix"));
});

test("builds Google Batch config arguments the backend accepts", () => {
  assert.deepEqual(buildGoogleBatchConfigArgs(GCP, "/cfg/gcp.config"), [
    "google-batch-config",
    "--project", "my-lab-project",
    "--location", "us-central1",
    "--bucket", "my-lab-nf",
    "--out", "/cfg/gcp.config",
  ]);
});

test("a config generation with nowhere to write is refused", () => {
  assert.throws(() => buildAwsBatchConfigArgs(AWS, ""), /outputPath is required/);
  assert.throws(() => buildGoogleBatchConfigArgs(GCP, ""), /outputPath is required/);
});

test("threads a cloud executor and its config into the run command", () => {
  const args = buildRunArgs({
    pipeline: "rnaseq",
    runtime: "awsbatch",
    configPath: "/cfg/aws.config",
    outputPath: "/data/results",
  });

  assert.ok(args.includes("--runtime") && args[args.indexOf("--runtime") + 1] === "awsbatch");
  assert.ok(args.includes("--config") && args[args.indexOf("--config") + 1] === "/cfg/aws.config");
  // An executor is not a container profile, so nothing here names one.
  assert.ok(!args.some((arg) => arg.startsWith("-profile")));
});

test("a cloud run needs Nextflow and nothing else installed locally", () => {
  // Submission is done by Nextflow's own SDK, and credentials come from the
  // environment or an instance profile. Demanding the provider CLI here would
  // block a correctly configured host that simply does not have it.
  assert.deepEqual(requiredCapabilities("awsbatch"), ["nextflow"]);
  assert.deepEqual(requiredCapabilities("googlebatch"), ["nextflow"]);
  assert.deepEqual(requiredCapabilities("kubernetes"), ["nextflow", "kubernetes"]);
});

test("no rejected value can reach a generated config", () => {
  // The point of the allow-list: injection is refused, never escaped.
  for (const payload of ["q'; System.exit(1); //", "q'\nprocess.executor = 'local'\n//"]) {
    assert.throws(() => buildAwsBatchConfigArgs({ ...AWS, jobQueue: payload }, "/cfg/a.config"));
  }
});

test("a bucket the provider itself would reject is caught here", () => {
  assert.throws(() => validateAwsBatchRequest({ ...AWS, bucket: "has..dots" }), /consecutive dots/);
  assert.throws(() => validateAwsBatchRequest({ ...AWS, bucket: "192.168.1.1" }), /IP address/);
});

test("a prefix segment that is only dots is refused", () => {
  // Dots are legal inside a segment, so "runs/v1.2/batch" has to keep working.
  assert.equal(validateAwsBatchRequest({ ...AWS, prefix: "runs/v1.2/batch" }).prefix, "runs/v1.2/batch");
  assert.throws(() => validateAwsBatchRequest({ ...AWS, prefix: "runs/../etc" }), /'\.' or '\.\.'/);
});

test("names too long for the provider are refused", () => {
  assert.throws(() => validateAwsBatchRequest({ ...AWS, jobQueue: "q".repeat(200) }), /job queue/);
  assert.throws(() => validateAwsBatchRequest({ ...AWS, bucket: "b".repeat(70) }), /bucket/);
});

test("the naming rules match the ones the backend enforces", () => {
  // Both validators are written by hand from the same provider rules, so the
  // corpus is shared: a change to one that the other does not follow fails
  // here rather than at submission time.
  const corpus = require("../../tests/fixtures/cloud_names.json");
  const under = {
    region: (value) => validateAwsBatchRequest({ ...AWS, region: value }),
    jobQueue: (value) => validateAwsBatchRequest({ ...AWS, jobQueue: value }),
    bucket: (value) => validateAwsBatchRequest({ ...AWS, bucket: value }),
    prefix: (value) => validateAwsBatchRequest({ ...AWS, prefix: value }),
    project: (value) => validateGoogleBatchRequest({ ...GCP, project: value }),
    location: (value) => validateGoogleBatchRequest({ ...GCP, location: value }),
  };

  for (const [field, check] of Object.entries(under)) {
    for (const value of corpus[field].valid) {
      assert.doesNotThrow(() => check(value), `${field} should accept ${JSON.stringify(value)}`);
    }
    for (const value of corpus[field].invalid) {
      assert.throws(() => check(value), `${field} should refuse ${JSON.stringify(value)}`);
    }
  }
});

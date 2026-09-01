---
name: run-desktop
description: Build, run, and drive the Helixsh Electron desktop app. Use when asked to start the desktop app, screenshot it, or verify a change in the real app rather than in tests.
---

The Helixsh runner is an Electron app, so a terminal-only session cannot see or
click it. Drive it through the Playwright REPL in this directory, under xvfb.

All paths are relative to the repository root.

## Prerequisites

Node 22.12+ (`.nvmrc` pins 24), Python 3.11+, and on Linux:

```bash
apt-get install -y xvfb libnss3 libgbm1 libasound2t64 libgtk-3-0 \
  libxss1 libxkbcommon0 libatk-bridge2.0-0 libcups2 libdrm2
npm install
npm install --no-save playwright-core   # not a project dependency
```

No Python install is needed — the app puts `src/` on `PYTHONPATH` itself.

## Run

```bash
xvfb-run -a node .claude/skills/run-desktop/driver.mjs
```

Wrap it in tmux to keep a session between commands:

```bash
tmux new-session -d -s helix -x 200 -y 50
tmux send-keys -t helix 'xvfb-run -a node .claude/skills/run-desktop/driver.mjs' Enter
timeout 30 bash -c 'until tmux capture-pane -t helix -p | grep -q "driver>"; do sleep 0.3; done'
tmux send-keys -t helix 'launch' Enter
timeout 90 bash -c 'until tmux capture-pane -t helix -p | grep -q "launched:"; do sleep 0.5; done'
tmux send-keys -t helix 'ss landing' Enter
tmux capture-pane -t helix -p
```

Screenshots land in `$TMPDIR/helixsh-shots` (override with `SCREENSHOT_DIR`).
**Open them.** A blank frame means the launch failed.

### Commands

| Command | Effect |
|---|---|
| `launch` | Start the app and wait for the form |
| `ss [name]` | Screenshot |
| `pick <kind> <field> <path>` | Supply a path through the native picker, e.g. `pick samplesheet inputPath demo/rnaseq-samplesheet.csv` |
| `confirm run\|cancel` | Pre-answer the native execution confirmation |
| `set <sel> <value>` | Set a field (checkboxes take `true`/`false`) |
| `click <sel>` | Click via the DOM |
| `plan` | Press "Validate & plan" and print the result |
| `text [sel]` / `eval <js>` | Read the page |
| `quit` | Close and exit |

Picker kinds are `samplesheet`, `directory`, `workflow`, `schema` and
`params`; the field is the input's `id`. There is no picker for an executor
config: it pins `process.executor`, and a file chosen from disk does not say
which executor that is, so the app only accepts one it generated itself.

## Eval battery

`evals.mjs` drives four nf-core demo projects and asserts the guardrails, using
the committed fixtures in `demo/`:

```bash
xvfb-run -a node .claude/skills/run-desktop/evals.mjs   # exits non-zero on failure
```

It covers plan composition for rnaseq/sarek/viralrecon/scrnaseq, tumour-normal
detection, executor config generation for Kubernetes, AWS Batch and Google
Batch, and seven guardrails: runtime readiness, configuration drift,
unapproved paths, a Groovy injection payload in a Kubernetes name and in an
AWS one, a cloud run with no config, and path traversal in a pipeline name. It
also carries two regression checks on the same hazard — a generated config
must not follow a change of executor, whether to a local runtime or to another
cloud one.

## Gotchas

- **The app will not start as root.** `main.cjs` calls `app.enableSandbox()`,
  and Chromium refuses the sandbox as uid 0 — child processes die with
  `Running as root without --no-sandbox is not supported`, on repeat, forever.
  Run as an unprivileged user with its own writable `HOME`. Do *not* "fix" this
  with `--no-sandbox` or `ELECTRON_DISABLE_SANDBOX`: the sandbox is a security
  property of this app, and disabling it means you are no longer testing it.

- **Paths cannot be typed into the form.** The main process only accepts paths
  it handed back from a native picker (`assertApprovedPaths`), so setting the
  input's value directly makes planning fail with "was not selected as a …
  path". That check is deliberate — stub `dialog.showOpenDialog` via
  `app.evaluate` and click the real button, which is what `pick` does.

- **`playwright-core` is CommonJS.** `import { _electron }` fails with a named
  export error under ESM; use `createRequire`.

- **Execution needs a native confirmation.** `helixsh:start` shows a
  `showMessageBox` that blocks forever headless. Stub it with `confirm` before
  clicking Run.

- **Runtime chips read red without Nextflow and Docker.** Expected in a
  container; planning still works, execution is gated on readiness.

- **The app has its own capture hook.** `HELIXSH_CAPTURE_PATH` plus
  `HELIXSH_SMOKE_PLAN=1` screenshots a planned run without Playwright, which is
  enough for a smoke check but cannot drive the UI.

## Troubleshooting

- *"Missing X server"* — you forgot `xvfb-run`.
- Stale locks — `rm -f /tmp/.X*-lock; pkill Xvfb`.
- Launch timeout — check `node_modules/electron/dist/electron` exists
  (`npm install`), and that `playwright-core` is installed.

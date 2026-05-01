<script>
  import { invoke } from "@tauri-apps/api/core";
  import { blocks, role, strictMode, newBlockId } from "../store.js";

  let input = "";
  let intentMode = false;
  let history = [];
  let histIdx = -1;
  let inputEl;

  // All known helixsh commands for autocomplete
  const COMMANDS = [
    "run", "doctor", "plan", "posix-wrap", "preflight",
    "intent", "profile-suggest",
    "nf-list", "nf-launch", "nf-auth", "pipeline-list", "pipeline-update",
    "samplesheet-validate", "samplesheet-generate",
    "ref-list", "ref-download",
    "conda-search", "conda-install", "conda-env-create", "conda-env-export",
    "trace-summary", "cost-estimate", "cost-report",
    "tower-submit", "tower-list", "tower-status", "tower-cancel", "tower-envs",
    "hpc-modules-gen", "hpc-profile-gen",
    "snakemake-import", "snakemake-convert",
    "schema-validate", "schema-lint", "config-check", "process-lint",
    "resource-estimate", "resource-calibrate",
    "mcp-propose", "mcp-approve", "mcp-status",
    "diag", "version", "env-check",
    "audit-log", "audit-verify", "provenance-show", "provenance-export",
    "image-verify", "sbom-generate", "secret-scan",
  ];

  let suggestions = [];
  let showSuggestions = false;

  function onInput() {
    const val = input.trim();
    if (!val || val.includes(" ")) {
      suggestions = [];
      showSuggestions = false;
      return;
    }
    suggestions = COMMANDS.filter((c) => c.startsWith(val) && c !== val);
    showSuggestions = suggestions.length > 0;
  }

  function applySuggestion(s) {
    input = s + " ";
    suggestions = [];
    showSuggestions = false;
    inputEl?.focus();
  }

  async function submit() {
    const raw = input.trim();
    if (!raw) return;

    history = [raw, ...history.filter((h) => h !== raw)].slice(0, 100);
    histIdx = -1;
    input = "";
    showSuggestions = false;

    let args;
    if (intentMode) {
      args = ["intent", raw];
    } else {
      args = parseArgs(raw);
    }

    // Inject --role if not already present
    if (!args.includes("--role")) {
      args = ["--role", $role, ...args];
    }
    if ($strictMode && !args.includes("--strict")) {
      args = ["--strict", ...args];
    }

    const id = newBlockId();
    const [command, ...rest] = intentMode ? ["intent", raw] : parseArgs(raw);

    blocks.update((bs) => [
      ...bs,
      {
        id,
        command: intentMode ? "intent" : command ?? raw,
        args: intentMode ? [raw] : rest,
        lines: [],
        status: "running",
        exitCode: null,
        running: true,
        ts: Date.now(),
      },
    ]);

    try {
      await invoke("run_helixsh", { invocationId: id, args });
    } catch (e) {
      blocks.update((bs) => {
        const idx = bs.findIndex((b) => b.id === id);
        if (idx === -1) return bs;
        const block = {
          ...bs[idx],
          lines: [{ stream: "stderr", text: String(e) }],
          status: "error",
          exitCode: -1,
          running: false,
        };
        const updated = [...bs];
        updated[idx] = block;
        return updated;
      });
    }
  }

  function parseArgs(raw) {
    // Simple shell-like split (no nested quotes)
    const re = /("(?:[^"\\]|\\.)*"|'(?:[^'\\]|\\.)*'|\S+)/g;
    return [...raw.matchAll(re)].map((m) => m[1].replace(/^["']|["']$/g, ""));
  }

  function onKeyDown(e) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      submit();
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      histIdx = Math.min(histIdx + 1, history.length - 1);
      input = history[histIdx] ?? "";
    } else if (e.key === "ArrowDown") {
      e.preventDefault();
      histIdx = Math.max(histIdx - 1, -1);
      input = histIdx === -1 ? "" : history[histIdx];
    } else if (e.key === "Tab") {
      e.preventDefault();
      if (suggestions.length === 1) applySuggestion(suggestions[0]);
      else if (suggestions.length > 1) showSuggestions = true;
    } else if (e.key === "Escape") {
      showSuggestions = false;
    }
  }
</script>

<div class="bar-wrap">
  {#if showSuggestions}
    <div class="suggestions">
      {#each suggestions.slice(0, 8) as s}
        <button class="suggestion" on:click={() => applySuggestion(s)}>{s}</button>
      {/each}
    </div>
  {/if}

  <div class="bar">
    <!-- Intent toggle -->
    <button
      class="mode-toggle"
      class:intent={intentMode}
      title={intentMode ? "Switch to command mode" : "Switch to intent mode"}
      on:click={() => (intentMode = !intentMode)}
    >
      {intentMode ? "⚡" : "❯"}
    </button>

    <!-- Input -->
    <input
      bind:this={inputEl}
      bind:value={input}
      on:input={onInput}
      on:keydown={onKeyDown}
      placeholder={intentMode
        ? "Describe what you want to run…"
        : "Enter a helixsh command…"}
      spellcheck="false"
      autocomplete="off"
    />

    <!-- Strict mode toggle -->
    <button
      class="strict-toggle"
      class:on={$strictMode}
      title="Strict mode (require --execute)"
      on:click={() => strictMode.update((v) => !v)}
    >
      {$strictMode ? "🔒" : "🔓"}
    </button>

    <!-- Submit -->
    <button class="submit-btn" on:click={submit} title="Run (Enter)">▶</button>
  </div>
</div>

<style>
  .bar-wrap {
    position: relative;
    border-top: 1px solid var(--border);
    background: var(--bg2);
    flex-shrink: 0;
  }

  .suggestions {
    position: absolute;
    bottom: 100%;
    left: 0;
    right: 0;
    background: var(--bg3);
    border: 1px solid var(--border);
    border-bottom: none;
    border-radius: var(--radius) var(--radius) 0 0;
    display: flex;
    flex-direction: column;
    max-height: 200px;
    overflow-y: auto;
    z-index: 10;
  }
  .suggestion {
    text-align: left;
    padding: 5px 14px;
    font-family: var(--font-mono);
    font-size: 12px;
    color: var(--muted);
    transition: background 0.1s, color 0.1s;
  }
  .suggestion:hover { background: var(--bg4); color: var(--accent); }

  .bar {
    display: flex;
    align-items: center;
    gap: 6px;
    padding: 8px 12px;
  }

  .mode-toggle {
    font-size: 14px;
    width: 26px;
    height: 26px;
    display: flex;
    align-items: center;
    justify-content: center;
    border-radius: 4px;
    color: var(--muted);
    flex-shrink: 0;
    transition: color 0.15s, background 0.15s;
  }
  .mode-toggle:hover { background: var(--bg3); color: var(--text); }
  .mode-toggle.intent { color: var(--orange); }

  input {
    flex: 1;
    font-size: 13px;
    padding: 4px 0;
    caret-color: var(--accent);
    user-select: text;
  }
  input::placeholder { color: var(--muted); }

  .strict-toggle {
    font-size: 13px;
    width: 26px;
    height: 26px;
    display: flex;
    align-items: center;
    justify-content: center;
    border-radius: 4px;
    opacity: 0.5;
    transition: opacity 0.15s;
    flex-shrink: 0;
  }
  .strict-toggle.on  { opacity: 1; }
  .strict-toggle:hover { opacity: 1; }

  .submit-btn {
    color: var(--accent);
    font-size: 14px;
    width: 26px;
    height: 26px;
    display: flex;
    align-items: center;
    justify-content: center;
    border-radius: 4px;
    flex-shrink: 0;
    transition: background 0.15s;
  }
  .submit-btn:hover { background: var(--bg3); }
</style>

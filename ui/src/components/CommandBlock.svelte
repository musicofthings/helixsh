<script>
  export let block; // { id, command, args, lines, status, exitCode, running, ts }

  let collapsed = false;

  function formatTs(ts) {
    return new Date(ts).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" });
  }

  $: statusColor = block.running
    ? "var(--yellow)"
    : block.status === "success"
    ? "var(--green)"
    : "var(--red)";

  $: statusLabel = block.running
    ? "running"
    : block.status === "success"
    ? `exit 0`
    : `exit ${block.exitCode ?? "?"}`;
</script>

<div class="block" class:collapsed>
  <!-- Block header -->
  <div class="block-header" on:click={() => (collapsed = !collapsed)} role="button" tabindex="0" on:keydown={(e) => e.key === "Enter" && (collapsed = !collapsed)}>
    <span class="collapse-icon">{collapsed ? "▶" : "▼"}</span>
    <span class="prompt">❯</span>
    <span class="command">{block.command} {(block.args ?? []).join(" ")}</span>
    <span class="spacer"></span>
    <span class="status-badge" style="color:{statusColor}">
      {#if block.running}
        <span class="spinner">⠋</span>
      {/if}
      {statusLabel}
    </span>
    <span class="ts">{formatTs(block.ts)}</span>
  </div>

  <!-- Block output -->
  {#if !collapsed}
    <div class="block-output" class:empty={block.lines.length === 0}>
      {#if block.lines.length === 0 && block.running}
        <span class="waiting">waiting for output…</span>
      {:else}
        {#each block.lines as { stream, text }}
          <div class="line" class:stderr={stream === "stderr"}>{text}</div>
        {/each}
      {/if}
    </div>
  {/if}
</div>

<style>
  .block {
    border-left: 2px solid var(--border);
    margin: 0 1rem 0.75rem;
    border-radius: 0 var(--radius) var(--radius) 0;
    overflow: hidden;
    background: var(--bg2);
    transition: border-color 0.2s;
  }
  .block:hover { border-left-color: var(--accent); }

  .block-header {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 6px 10px;
    background: var(--bg3);
    cursor: pointer;
    font-family: var(--font-mono);
    font-size: 12px;
    border-bottom: 1px solid var(--border);
  }
  .block-header:hover { background: var(--bg4); }

  .collapse-icon { color: var(--muted); font-size: 9px; flex-shrink: 0; }
  .prompt { color: var(--accent); font-weight: 700; }
  .command { color: var(--text); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; flex: 1; }
  .spacer { flex: 1; }
  .status-badge { font-size: 11px; flex-shrink: 0; }
  .ts { color: var(--muted); font-size: 10px; flex-shrink: 0; }

  .spinner {
    display: inline-block;
    animation: spin 0.6s steps(8) infinite;
  }
  @keyframes spin { to { transform: rotate(360deg); } }

  .block-output {
    padding: 8px 12px;
    font-family: var(--font-mono);
    font-size: 12px;
    line-height: 1.65;
    max-height: 480px;
    overflow-y: auto;
    white-space: pre-wrap;
    word-break: break-all;
    user-select: text;
  }
  .block-output.empty { padding: 6px 12px; }
  .line { color: var(--text); }
  .line.stderr { color: var(--red); }
  .waiting { color: var(--muted); font-style: italic; font-size: 11px; }
</style>

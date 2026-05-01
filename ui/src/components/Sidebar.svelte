<script>
  import { onMount } from "svelte";
  import { invoke } from "@tauri-apps/api/core";
  import { sidebarTab, doctorData, pipelineList, role } from "../store.js";

  const TABS = ["tools", "pipelines", "history"];

  async function loadDoctor() {
    try {
      const res = await invoke("query_helixsh", { args: ["doctor"] });
      doctorData.set(parseDoctor(res.stdout));
    } catch {}
  }

  async function loadPipelines() {
    try {
      const res = await invoke("query_helixsh", { args: ["nf-list"] });
      const parsed = JSON.parse(res.stdout);
      pipelineList.set(parsed.map((p) => p.name));
    } catch {}
  }

  function parseDoctor(text) {
    return text.split("\n").filter((l) => l.trim()).map((l) => {
      const parts = l.trim().split(/\s+/);
      const tool = parts[0];
      const state = parts[1];
      const details = parts.slice(2).join(" ");
      return { tool, value: details || "not found", ok: state === "ok" };
    });
  }

  onMount(() => {
    loadDoctor();
    loadPipelines();
  });

  const ROLES = ["auditor", "analyst", "admin"];
  const ROLE_COLORS = { auditor: "#58a6ff", analyst: "#3fb950", admin: "#d2a8ff" };
</script>

<aside class="sidebar">
  <nav class="tabs">
    {#each TABS as tab}
      <button
        class="tab"
        class:active={$sidebarTab === tab}
        on:click={() => sidebarTab.set(tab)}
      >{tab}</button>
    {/each}
  </nav>

  <div class="panel">
    {#if $sidebarTab === "tools"}
      <section>
        <h3 class="section-label">Environment</h3>
        {#if $doctorData}
          <ul class="tool-list">
            {#each $doctorData as { tool, value, ok }}
              <li class="tool-item">
                <span class="dot" class:ok class:bad={!ok}></span>
                <span class="tool-name">{tool}</span>
                <span class="tool-val">{ok ? value : "–"}</span>
              </li>
            {/each}
          </ul>
        {:else}
          <p class="muted">Loading…</p>
        {/if}
        <button class="refresh-btn" on:click={loadDoctor}>↻ Refresh</button>
      </section>

      <section style="margin-top:1rem;">
        <h3 class="section-label">Role</h3>
        <div class="role-pills">
          {#each ROLES as r}
            <button
              class="role-pill"
              class:selected={$role === r}
              style="--rc: {ROLE_COLORS[r]}"
              on:click={() => role.set(r)}
            >{r}</button>
          {/each}
        </div>
      </section>
    {:else if $sidebarTab === "pipelines"}
      <section>
        <h3 class="section-label">nf-core Pipelines</h3>
        {#if $pipelineList.length}
          <ul class="pipeline-list">
            {#each $pipelineList as p}
              <li class="pipeline-item">{p}</li>
            {/each}
          </ul>
        {:else}
          <p class="muted">Loading…</p>
        {/if}
        <button class="refresh-btn" on:click={loadPipelines}>↻ Refresh</button>
      </section>
    {:else}
      <section>
        <h3 class="section-label">Command History</h3>
        <p class="muted" style="padding:0.5rem 0.75rem;">Run commands to see history.</p>
      </section>
    {/if}
  </div>
</aside>

<style>
  .sidebar {
    width: var(--sidebar);
    min-width: var(--sidebar);
    background: var(--bg2);
    border-right: 1px solid var(--border);
    display: flex;
    flex-direction: column;
    overflow: hidden;
  }
  .tabs {
    display: flex;
    border-bottom: 1px solid var(--border);
    flex-shrink: 0;
  }
  .tab {
    flex: 1;
    padding: 7px 4px;
    font-size: 11px;
    color: var(--muted);
    border-bottom: 2px solid transparent;
    text-transform: capitalize;
    transition: color 0.15s, border-color 0.15s;
  }
  .tab.active { color: var(--text); border-bottom-color: var(--accent); }
  .tab:hover:not(.active) { color: var(--text); }

  .panel { flex: 1; overflow-y: auto; padding: 0.75rem 0; }
  section { padding: 0 0.75rem; }
  .section-label {
    font-size: 10px;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    color: var(--muted);
    margin-bottom: 0.4rem;
  }
  .muted { color: var(--muted); font-size: 11px; }

  .tool-list { list-style: none; display: flex; flex-direction: column; gap: 2px; }
  .tool-item { display: flex; align-items: center; gap: 6px; padding: 2px 0; }
  .dot {
    width: 6px; height: 6px;
    border-radius: 50%;
    background: var(--bg4);
    flex-shrink: 0;
  }
  .dot.ok  { background: var(--green); }
  .dot.bad { background: var(--red); }
  .tool-name { flex: 1; font-size: 11px; color: var(--text); }
  .tool-val { font-size: 10px; color: var(--muted); font-family: var(--font-mono); }

  .refresh-btn {
    font-size: 10px;
    color: var(--muted);
    margin-top: 6px;
    padding: 2px 0;
    transition: color 0.15s;
  }
  .refresh-btn:hover { color: var(--accent); }

  .role-pills { display: flex; flex-direction: column; gap: 4px; }
  .role-pill {
    font-size: 11px;
    padding: 4px 8px;
    border-radius: 4px;
    text-align: left;
    color: var(--muted);
    transition: color 0.15s, background 0.15s;
  }
  .role-pill.selected { color: var(--rc); background: color-mix(in srgb, var(--rc) 12%, transparent); }
  .role-pill:hover:not(.selected) { color: var(--text); }

  .pipeline-list { list-style: none; display: flex; flex-direction: column; gap: 2px; }
  .pipeline-item {
    font-size: 11px;
    padding: 3px 4px;
    border-radius: 4px;
    color: var(--muted);
    font-family: var(--font-mono);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }
  .pipeline-item:hover { color: var(--text); background: var(--bg3); }
</style>

<script>
  import { invoke } from "@tauri-apps/api/core";
  import { THEMES, theme } from "../theme.js";

  async function action(a) {
    await invoke("window_action", { action: a });
  }
</script>

<!-- Dragging is handled by CSS -webkit-app-region: drag on .titlebar -->
<!-- svelte-ignore a11y-no-static-element-interactions -->
<header class="titlebar">
  <div class="left">
    <span class="logo">⬡ helixsh</span>
  </div>
  <div class="right">
    <label class="visually-hidden" for="theme">Colour theme</label>
    <select id="theme" class="theme" bind:value={$theme}>
      {#each THEMES as { id, label }}
        <option value={id}>{label}</option>
      {/each}
    </select>
  </div>
  <div class="controls" on:mousedown|stopPropagation>
    <button class="ctrl close"    on:click={() => action("close")}    title="Close"    aria-label="Close"></button>
    <button class="ctrl minimize" on:click={() => action("minimize")} title="Minimize" aria-label="Minimize"></button>
    <button class="ctrl maximize" on:click={() => action("maximize")} title="Maximize" aria-label="Maximize"></button>
  </div>
</header>

<style>
  .titlebar {
    display: flex;
    align-items: center;
    gap: 12px;
    height: var(--titlebar);
    background: var(--bg2);
    border-bottom: 1px solid var(--border);
    padding: 0 12px;
    flex-shrink: 0;
    -webkit-app-region: drag;
    cursor: default;
  }
  .left { display: flex; flex: 1; align-items: center; gap: 8px; }
  .logo { font-weight: 700; font-size: 13px; color: var(--accent); letter-spacing: -0.3px; }
  .controls,
  .right {
    display: flex;
    align-items: center;
    gap: 8px;
    -webkit-app-region: no-drag;
  }
  .theme {
    background: var(--bg3);
    border: 1px solid var(--border);
    border-radius: var(--radius);
    color: var(--text);
    font-family: var(--font-ui);
    font-size: 11px;
    padding: 2px 4px;
  }
  .visually-hidden {
    position: absolute;
    width: 1px;
    height: 1px;
    overflow: hidden;
    clip-path: inset(50%);
    white-space: nowrap;
  }
  .ctrl {
    width: 12px; height: 12px;
    border-radius: 50%;
    background: var(--bg4);
    transition: background 0.15s;
    padding: 0;
  }
  .close:hover    { background: #ff5f57; }
  .minimize:hover { background: #febc2e; }
  .maximize:hover { background: #28c840; }
</style>

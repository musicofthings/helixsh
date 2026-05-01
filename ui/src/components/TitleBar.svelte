<script>
  import { invoke } from "@tauri-apps/api/core";

  async function action(a) {
    await invoke("window_action", { action: a });
  }
  async function drag() {
    await invoke("start_drag");
  }
</script>

<!-- svelte-ignore a11y-no-static-element-interactions -->
<div class="titlebar" on:mousedown={drag}>
  <div class="left">
    <span class="logo">⬡ helixsh</span>
  </div>
  <div class="controls" on:mousedown|stopPropagation>
    <button class="ctrl close"   on:click={() => action("close")}   title="Close"    aria-label="Close"></button>
    <button class="ctrl minimize" on:click={() => action("minimize")} title="Minimize" aria-label="Minimize"></button>
    <button class="ctrl maximize" on:click={() => action("maximize")} title="Maximize" aria-label="Maximize"></button>
  </div>
</div>

<style>
  .titlebar {
    display: flex;
    align-items: center;
    justify-content: space-between;
    height: var(--titlebar);
    background: var(--bg2);
    border-bottom: 1px solid var(--border);
    padding: 0 12px;
    flex-shrink: 0;
    -webkit-app-region: drag;
  }
  .left { display: flex; align-items: center; gap: 8px; }
  .logo { font-weight: 700; font-size: 13px; color: var(--accent); letter-spacing: -0.3px; }
  .controls {
    display: flex;
    align-items: center;
    gap: 8px;
    -webkit-app-region: no-drag;
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

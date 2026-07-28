<script>
  import { role, strictMode, helixshPath, pendingBlock } from "../store.js";

  const ROLE_COLORS = { auditor: "#58a6ff", analyst: "#3fb950", admin: "#d2a8ff" };
  $: rc = ROLE_COLORS[$role] ?? "var(--muted)";
</script>

<div class="statusbar">
  <span class="seg role" style="color:{rc}">
    ⬡ {$role}
  </span>

  {#if $strictMode}
    <span class="seg strict">🔒 strict</span>
  {/if}

  {#if $pendingBlock}
    <span class="seg running">⠋ running…</span>
  {/if}

  <span class="spacer"></span>

  <span class="seg path" title={$helixshPath}>{$helixshPath}</span>
</div>

<style>
  .statusbar {
    display: flex;
    align-items: center;
    gap: 0;
    height: var(--statusbar);
    background: var(--bg2);
    border-top: 1px solid var(--border);
    font-size: 11px;
    flex-shrink: 0;
    overflow: hidden;
  }
  .seg {
    padding: 0 10px;
    height: 100%;
    display: flex;
    align-items: center;
    border-right: 1px solid var(--border);
    white-space: nowrap;
  }
  .role    { font-weight: 600; }
  .strict  { color: var(--yellow); }
  .running { color: var(--orange); animation: pulse 1s ease-in-out infinite; }
  @keyframes pulse { 0%,100% { opacity:1 } 50% { opacity:0.5 } }
  .spacer  { flex: 1; }
  .path    { color: var(--muted); border-right: none; border-left: 1px solid var(--border); max-width: 260px; overflow: hidden; text-overflow: ellipsis; }
</style>

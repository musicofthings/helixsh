<script>
  import { afterUpdate } from "svelte";
  import CommandBlock from "./CommandBlock.svelte";
  import CommandBar from "./CommandBar.svelte";
  import { blocks } from "../store.js";

  let scrollEl;
  afterUpdate(() => {
    if (scrollEl) scrollEl.scrollTop = scrollEl.scrollHeight;
  });
</script>

<div class="main-area">
  <div class="blocks-scroll" bind:this={scrollEl}>
    {#if $blocks.length === 0}
      <div class="welcome">
        <div class="welcome-logo">⬡</div>
        <h1>helixsh</h1>
        <p>Bioinformatics-first AI shell for Nextflow and nf-core.</p>
        <div class="hints">
          <div class="hint"><kbd>intent</kbd> Natural-language pipeline planning</div>
          <div class="hint"><kbd>doctor</kbd> Check your environment</div>
          <div class="hint"><kbd>run</kbd> Execute an nf-core pipeline</div>
          <div class="hint"><kbd>nf-list</kbd> Browse available pipelines</div>
        </div>
      </div>
    {:else}
      {#each $blocks as block (block.id)}
        <CommandBlock {block} />
      {/each}
    {/if}
  </div>
  <CommandBar />
</div>

<style>
  .main-area {
    display: flex;
    flex-direction: column;
    flex: 1;
    overflow: hidden;
  }
  .blocks-scroll {
    flex: 1;
    overflow-y: auto;
    padding: 1rem 0;
  }

  /* Welcome screen */
  .welcome {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    height: 100%;
    min-height: 300px;
    gap: 0.5rem;
    text-align: center;
    padding: 2rem;
  }
  .welcome-logo { font-size: 3rem; color: var(--accent); line-height: 1; }
  .welcome h1 { font-size: 1.8rem; font-weight: 700; color: var(--text); letter-spacing: -0.5px; }
  .welcome p  { color: var(--muted); font-size: 0.9rem; margin-bottom: 1rem; }
  .hints { display: flex; flex-direction: column; gap: 0.4rem; align-items: flex-start; }
  .hint { font-size: 0.82rem; color: var(--muted); }
  kbd {
    display: inline-block;
    background: var(--bg3);
    border: 1px solid var(--border);
    border-radius: 4px;
    padding: 1px 6px;
    font-family: var(--font-mono);
    font-size: 0.78rem;
    color: var(--accent);
    margin-right: 6px;
  }
</style>

<script>
  import "./app.css";
  import TitleBar from "./components/TitleBar.svelte";
  import Sidebar from "./components/Sidebar.svelte";
  import MainArea from "./components/MainArea.svelte";
  import StatusBar from "./components/StatusBar.svelte";
  import { blocks, role, helixshPath } from "./store.js";
  import { invoke } from "@tauri-apps/api/core";
  import { listen } from "@tauri-apps/api/event";
  import { onMount } from "svelte";

  onMount(async () => {
    // Resolve helixsh path for display
    try {
      const path = await invoke("get_helixsh_path");
      helixshPath.set(path);
    } catch {}

    // Listen for streamed output lines
    await listen("helixsh://output", (event) => {
      const { invocationId, stream, line } = event.payload;
      blocks.update((bs) => {
        const idx = bs.findIndex((b) => b.id === invocationId);
        if (idx === -1) return bs;
        const block = { ...bs[idx] };
        block.lines = [...block.lines, { stream, text: line }];
        const updated = [...bs];
        updated[idx] = block;
        return updated;
      });
    });

    // Listen for command completion
    await listen("helixsh://done", (event) => {
      const { invocationId, exitCode } = event.payload;
      blocks.update((bs) => {
        const idx = bs.findIndex((b) => b.id === invocationId);
        if (idx === -1) return bs;
        const block = { ...bs[idx], status: exitCode === 0 ? "success" : "error", exitCode, running: false };
        const updated = [...bs];
        updated[idx] = block;
        return updated;
      });
    });
  });
</script>

<div class="shell">
  <TitleBar />
  <div class="body">
    <Sidebar />
    <div class="main-col">
      <MainArea />
      <StatusBar />
    </div>
  </div>
</div>

<style>
  .shell {
    display: flex;
    flex-direction: column;
    height: 100vh;
    width: 100vw;
    background: var(--bg);
  }
  .body {
    display: flex;
    flex: 1;
    overflow: hidden;
  }
  .main-col {
    display: flex;
    flex-direction: column;
    flex: 1;
    overflow: hidden;
  }
</style>

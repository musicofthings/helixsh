<script>
  import "./app.css";
  import TitleBar from "./components/TitleBar.svelte";
  import Sidebar from "./components/Sidebar.svelte";
  import MainArea from "./components/MainArea.svelte";
  import StatusBar from "./components/StatusBar.svelte";
  import { helixshPath } from "./store.js";
  import { invoke } from "@tauri-apps/api/core";
  import { onMount } from "svelte";

  onMount(async () => {
    try {
      const path = await invoke("get_helixsh_path");
      helixshPath.set(path);
    } catch {}
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

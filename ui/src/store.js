import { writable, derived } from "svelte/store";

export const blocks = writable([]);       // CommandBlock[]
export const role = writable("analyst");  // "auditor" | "analyst" | "admin"
export const strictMode = writable(false);
export const helixshPath = writable("helixsh");
export const sidebarTab = writable("tools"); // "tools" | "pipelines" | "history"
export const doctorData = writable(null);
export const pipelineList = writable([]);

let _blockId = 0;
export function newBlockId() {
  return `block-${++_blockId}-${Date.now()}`;
}

export const pendingBlock = derived(blocks, ($blocks) =>
  $blocks.find((b) => b.running) ?? null
);

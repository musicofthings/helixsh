# helixsh UI

Tauri v2 + Svelte 5 desktop app for helixsh — a Warp-inspired bioinformatics shell.

## Architecture

```
ui/
├── src/                    # Svelte 5 frontend
│   ├── App.svelte          # Root layout (titlebar + sidebar + main + statusbar)
│   ├── store.js            # Svelte stores (blocks, role, strictMode, …)
│   ├── app.css             # Global design tokens (CSS variables)
│   └── components/
│       ├── TitleBar.svelte     # Custom frameless titlebar with traffic-light buttons
│       ├── Sidebar.svelte      # Tool status / pipeline list / RBAC role selector
│       ├── MainArea.svelte     # Scrollable command block list + welcome screen
│       ├── CommandBar.svelte   # Input bar with autocomplete, intent mode, history
│       ├── CommandBlock.svelte # Per-command output block (collapsible, streaming)
│       └── StatusBar.svelte    # RBAC role / strict mode / helixsh path indicator
└── src-tauri/              # Rust backend
    ├── src/lib.rs           # Tauri commands: run_helixsh, query_helixsh, window controls
    ├── src/main.rs          # Entry point
    ├── Cargo.toml
    ├── tauri.conf.json      # Window config (frameless, 1280×800, min 900×600)
    └── capabilities/
        └── default.json     # Tauri v2 capability grants
```

## UI Features

| Feature | Description |
|---|---|
| **Command blocks** | Each command gets a collapsible block with streaming stdout/stderr (Warp-style) |
| **Intent mode** | Toggle `⚡` to send natural language → `helixsh intent "…"` |
| **Autocomplete** | Tab-complete from all 50+ helixsh commands |
| **Command history** | Arrow keys cycle through history |
| **RBAC indicator** | Role selector in sidebar and status bar |
| **Strict mode** | Lock icon in command bar appends `--strict` to every invocation |
| **Doctor panel** | Sidebar shows live tool version checks from `helixsh doctor` |
| **Pipeline list** | Sidebar lists all nf-core pipelines from `helixsh nf-list` |
| **Frameless window** | Custom titlebar with drag + macOS-style traffic-light buttons |
| **Sidecar support** | Auto-detects bundled `helixsh.pyz`, `helixsh` on PATH, or `python -m helixsh` |

## Development Requirements

### Linux (Ubuntu/Debian)

```bash
sudo apt-get install -y \
  libwebkit2gtk-4.1-dev \
  libappindicator3-dev \
  librsvg2-dev \
  patchelf \
  libgtk-3-dev \
  libgdk-pixbuf-2.0-dev \
  xdg-dbus-proxy
```

### macOS

```bash
# No extra system deps — WebKit is provided by the OS
xcode-select --install
```

### Windows

```
# No extra system deps — WebView2 is built into Windows 11 / available via installer
```

### All platforms

- **Rust** 1.80+ — [rustup.rs](https://rustup.rs)
- **Node.js** 20+ — [nodejs.org](https://nodejs.org)

## Running in Development

```bash
cd ui
npm install
npm run tauri dev
```

This starts the Vite dev server with HMR and opens the Tauri window.

## Building for Production

```bash
cd ui
npm install
npm run tauri build
```

Binaries and installers are written to `src-tauri/target/release/bundle/`.

## Connecting to helixsh

The app auto-resolves the helixsh backend in this order:

1. `helixsh.pyz` sidecar bundled next to the Tauri binary
2. `helixsh` on `$PATH`
3. `python3 -m helixsh` (module invocation)

To bundle `helixsh.pyz` as a sidecar, build it first:

```bash
# From repo root
./scripts/package_local.sh
# Then copy dist/helixsh.pyz to ui/src-tauri/binaries/helixsh.pyz
```

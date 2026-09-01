// REPL driver for the Helixsh Electron app, for headless/agent use.
//
// Electron needs a display and native dialogs, neither of which exist in a
// terminal. This wraps the app in Playwright's _electron so it can be driven
// by typing commands, and stubs the native pickers so paths can be supplied
// without a mouse.
//
//   xvfb-run -a node .claude/skills/run-desktop/driver.mjs
//
// See SKILL.md for the prerequisites and the gotchas that shaped this file.

import { createRequire } from 'node:module';
import * as readline from 'node:readline';
import * as fs from 'node:fs';
import * as path from 'node:path';
import * as os from 'node:os';

const APP_DIR = path.resolve(import.meta.dirname, '../../..');
const SHOT_DIR = process.env.SCREENSHOT_DIR || path.join(os.tmpdir(), 'helixsh-shots');

// playwright-core ships CommonJS, so a named ESM import of _electron fails.
const require = createRequire(import.meta.url);
const electron = require(path.join(APP_DIR, 'node_modules/playwright-core'))._electron;

fs.mkdirSync(SHOT_DIR, { recursive: true });

let app = null;
let page = null;

const electronBin = process.platform === 'darwin'
  ? path.join(APP_DIR, 'node_modules/electron/dist/Electron.app/Contents/MacOS/Electron')
  : path.join(APP_DIR, 'node_modules/electron/dist/electron');

const COMMANDS = {
  async launch() {
    if (app) return console.log('already launched');
    if (process.platform !== 'win32' && typeof process.getuid === 'function' && process.getuid() === 0) {
      console.log(
        'ERROR: main.cjs calls app.enableSandbox(), which Chromium refuses as root.\n' +
        '       Re-run as an unprivileged user (see SKILL.md > Gotchas).',
      );
      return;
    }
    app = await electron.launch({
      executablePath: electronBin,
      args: ['.'],
      cwd: APP_DIR,
      timeout: 60_000,
    });
    page = await app.firstWindow();
    await page.waitForSelector('#run-form', { timeout: 30_000 });
    console.log('launched:', await page.title());
  },

  // The renderer only accepts paths the main process handed back from a native
  // picker, so a path cannot be typed into the field. Stub the dialog instead
  // and click the real button, which keeps the approval bookkeeping intact.
  async pick(arg) {
    const [kind, target, ...rest] = arg.split(/\s+/);
    const filePath = rest.join(' ');
    await app.evaluate(({ dialog }, p) => {
      dialog.showOpenDialog = async () => ({ canceled: false, filePaths: [p] });
    }, filePath);
    const clicked = await COMMANDS._click(`button[data-picker="${kind}"][data-target="${target}"]`);
    if (clicked !== 'OK') return console.log('pick ->', clicked);
    await page.waitForFunction(
      ([t, v]) => document.getElementById(t).value === v, [target, filePath], { timeout: 10_000 },
    ).catch(() => {});
    console.log('pick', kind, '->', await page.evaluate((t) => document.getElementById(t).value, target));
  },

  // Pre-answer the native run confirmation: "run" or "cancel".
  async confirm(choice) {
    const index = choice.trim() === 'run' ? 1 : 0;
    await app.evaluate(({ dialog }, i) => {
      dialog.showMessageBox = async () => ({ response: i });
    }, index);
    console.log('confirmation stubbed ->', index === 1 ? 'Run pipeline' : 'Cancel');
  },

  async set(arg) {
    const [selector, ...rest] = arg.split(/\s+/);
    const value = rest.join(' ');
    console.log('set', selector, '->', await page.evaluate(([s, v]) => {
      const el = document.querySelector(s);
      if (!el) return 'NOT_FOUND';
      if (el.type === 'checkbox') el.checked = v === 'true';
      else el.value = v;
      el.dispatchEvent(new Event('input', { bubbles: true }));
      el.dispatchEvent(new Event('change', { bubbles: true }));
      return 'OK';
    }, [selector, value]));
  },

  // DOM click, not locator.click(): Playwright's coordinates can land on the
  // wrong layer, and the DOM path is what the app's own handlers listen to.
  _click: (selector) => page.evaluate((s) => {
    const el = document.querySelector(s);
    if (!el) return 'NOT_FOUND';
    el.click();
    return 'OK';
  }, selector),

  async click(selector) { console.log('click', selector, '->', await COMMANDS._click(selector)); },

  async plan() {
    await COMMANDS._click('#plan');
    await page.waitForFunction(
      () => !document.getElementById('run-state').innerText.match(/Validating/), { timeout: 90_000 },
    );
    console.log(await page.evaluate(() => document.getElementById('run-state').innerText));
    console.log(await page.evaluate(() => document.getElementById('console').innerText));
  },

  async ss(name) {
    const file = path.join(SHOT_DIR, (name || `ss-${Date.now()}`) + '.png');
    await page.screenshot({ path: file });
    console.log('screenshot:', file);
  },

  async text(selector) {
    console.log(await page.evaluate(
      (s) => (s ? document.querySelector(s) : document.body)?.innerText ?? '(null)', selector || null));
  },

  async eval(expr) {
    try { console.log(JSON.stringify(await page.evaluate(expr))); }
    catch (error) { console.log('ERROR:', error.message); }
  },

  async quit() {
    if (app) await app.close().catch(() => {});
    app = null;
    page = null;
  },

  help() { console.log('commands:', Object.keys(COMMANDS).filter((k) => !k.startsWith('_')).join(', ')); },
};

// Electron grabs stdin, so read the raw fd to keep the REPL's own input.
// /dev/stdin is not always openable (piped input, some containers), in which
// case fall back to process.stdin.
let stdin;
try {
  stdin = fs.createReadStream(null, { fd: fs.openSync('/dev/stdin', 'r') });
} catch {
  stdin = process.stdin;
}
const rl = readline.createInterface({ input: stdin, output: process.stdout, prompt: 'driver> ' });

// Commands are serialized: readline emits piped lines in one burst, so an
// async handler alone would let `ss` run while `launch` was still awaiting.
let queue = Promise.resolve();

async function handle(line) {
  const [command, ...rest] = line.trim().split(/\s+/);
  if (!command) return rl.prompt();
  const handler = COMMANDS[command];
  if (!handler || command.startsWith('_')) {
    console.log('unknown:', command, '- try: help');
    return rl.prompt();
  }
  try { await handler(rest.join(' ')); }
  catch (error) { console.log('ERROR:', error.message); }
  if (command === 'quit') { rl.close(); process.exit(0); }
  rl.prompt();
}

rl.on('line', (line) => { queue = queue.then(() => handle(line)); });
// End of piped input arrives right after the line burst, so drain the queue
// before exiting or the queued commands never run.
rl.on('close', () => {
  queue = queue.then(async () => { await COMMANDS.quit(); process.exit(0); });
});

console.log('helixsh driver - "help" for commands, "launch" to start');
rl.prompt();

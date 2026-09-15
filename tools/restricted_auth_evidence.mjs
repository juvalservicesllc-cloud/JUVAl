/** Lab-only RF-03 evidence boundary. No stock MCP, page export or log sink. */
import {createRequire} from 'node:module';
import {pathToFileURL} from 'node:url';
import {createInterface} from 'node:readline';

const paths = Object.freeze({login: '/login', challenge: '/challenge', callback: '/callback'});
const statuses = new Set(['READY', 'OBSERVED', 'CLOSED', 'REJECTED', 'FAILED']);
export function evidence(status, path = null) {
  if (!statuses.has(status) || (path !== null && !Object.values(paths).includes(path)))
    return {status: 'REJECTED', path: null};
  return {status, path};
}
export function normalizedPath(raw, origin) {
  try {
    const u = new URL(raw);
    if (u.origin !== origin || u.username || u.password) return null;
    return Object.values(paths).includes(u.pathname) ? u.pathname : null;
  } catch { return null; }
}
export function validRequest(r) {
  if (!r || typeof r !== 'object' || Array.isArray(r)) return false;
  const keys = Object.keys(r).sort().join(',');
  return (keys === 'op' && ['observe', 'close'].includes(r.op)) ||
    (keys === 'op,state' && r.op === 'visit' && typeof r.state === 'string' && Object.hasOwn(paths, r.state));
}
export class Controller {
  #browser; #page; #origin; #closed = false;
  constructor(browser, page, origin) { this.#browser = browser; this.#page = page; this.#origin = origin; }
  async request(r) {
    if (!validRequest(r)) return evidence('REJECTED');
    if (r.op === 'close') return this.close();
    if (this.#closed) return evidence('REJECTED');
    try {
      if (r.op === 'visit') await this.#page.goto(this.#origin + paths[r.state], {waitUntil: 'load', timeout: 10000});
      const path = normalizedPath(this.#page.url(), this.#origin);
      return evidence(path === null ? 'REJECTED' : 'OBSERVED', path);
    } catch { return evidence('FAILED'); } // Never stringify browser exceptions.
  }
  async close() {
    if (this.#closed) return evidence('CLOSED');
    try { await this.#browser.close(); this.#closed = true; return evidence('CLOSED'); }
    catch { return evidence('FAILED'); }
  }
}
async function main() {
  let controller, browser;
  const shutdown = async () => {
    let ok = false;
    try {
      if (controller) ok = (await controller.close()).status === 'CLOSED';
      else if (browser) { await browser.close(); ok = true; }
    } catch {}
    process.exit(ok ? 0 : 1);
  };
  process.once('SIGTERM', shutdown);
  process.once('SIGINT', shutdown);
  const emit = r => process.stdout.write(JSON.stringify(evidence(r.status, r.path)) + '\n');
  try {
    if (process.env.DISPLAY !== ':100') throw new Error('DISPLAY');
    const origin = process.env.JUVAL_SYNTHETIC_ORIGIN;
    const u = new URL(origin);
    if (u.origin !== origin || u.hostname !== '127.0.0.1' || u.protocol !== 'http:' ||
        Number(u.port) < 1024 || ['9011', '9012'].includes(u.port) || u.username || u.password)
      throw new Error('CONFIG');
    // This is a dedicated lab process, not a host for unrestricted MCP tools.
    for (const key of Object.keys(process.env))
      if (!['PATH', 'HOME', 'DISPLAY', 'XAUTHORITY', 'TMPDIR'].includes(key)) delete process.env[key];
    const require = createRequire(import.meta.url);
    const {chromium} = require('/home/juval/.npm/_npx/86170c4cd1c5da32/node_modules/playwright-core');
    browser = await chromium.launch({executablePath: '/opt/juval-browser/chromium-1243/chrome',
      chromiumSandbox: true, headless: false, timeout: 15000});
    const context = await browser.newContext({acceptDownloads: false, serviceWorkers: 'block'});
    await context.route('**/*', route => {
      const allowed = normalizedPath(route.request().url(), origin) !== null;
      return allowed ? route.continue() : route.abort();
    });
    const page = await context.newPage();
    // No console, request-body, response-body, dialog-text or page-error listeners.
    controller = new Controller(browser, page, origin);
    context.on('page', other => { if (other !== page) void other.close().catch(() => {}); });
    emit(evidence('READY'));
    const input = createInterface({input: process.stdin, terminal: false});
    for await (const line of input) {
      let request;
      try { request = JSON.parse(line); } catch { emit(evidence('REJECTED')); continue; }
      const result = await controller.request(request); emit(result);
      if (request?.op === 'close' && result.status === 'CLOSED') break;
    }
  } catch { emit(evidence('FAILED')); process.exitCode = 1; }
  finally {
    if (controller) { const result = await controller.close(); if (result.status !== 'CLOSED') process.exitCode = 1; }
    else if (browser) { try { await browser.close(); } catch { process.exitCode = 1; } }
  }
}
if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  // Top-level rejection details must not become stdout/stderr diagnostics.
  main().catch(() => { process.stdout.write('{"status":"FAILED","path":null}\n'); process.exitCode = 1; });
}

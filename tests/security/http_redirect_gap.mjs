/** Explicit synthetic reproducer, not a safe live transport implementation.
 * Two owned IPv4-loopback ephemeral servers; no caller-supplied destinations.
 * Exit 2 means containment violated: stop after cleanup, never count as PASS.
 */
import {createServer} from 'node:http';
import {createRequire} from 'node:module';

const sentinel = 'SYNTHETIC_REDIRECT_CODE_SENTINEL';
const requireCondition = value => { if (!value) throw new Error('LAB_FAILED'); };
const counters = () => ({navigation_attempted:false, callback_request_event:0,
  callback_route_calls:0, callback_tcp_connections:0, callback_http_requests:0,
  code_crossed_boundary:false, source_http_redirects:0});
const result = {classification:'REPRODUCER_INCONCLUSIVE', direct:counters(), redirect:counters(),
  browser_closed:false, servers_closed:false};
let active = result.direct, browser, stopped = false, shutdownPromise;
const servers = [];
const sockets = new Set();
async function listen(server) {
  servers.push(server);
  server.on('connection', socket => { sockets.add(socket); socket.on('close', () => sockets.delete(socket)); });
  await new Promise((resolve,reject) => { server.once('error',reject); server.listen(0,'127.0.0.1',resolve); });
  const address = server.address();
  requireCondition(address.address === '127.0.0.1' && address.port >= 1024 &&
    ![5900,5901,6080,6081,9011,9012,9222,18080].includes(address.port));
  return `http://127.0.0.1:${address.port}`;
}
async function shutdown() {
  if (shutdownPromise) return shutdownPromise;
  stopped = true;
  shutdownPromise = (async () => {
    try { if(browser) await browser.close(); result.browser_closed = true; } catch {}
    for(const socket of sockets) socket.destroy();
    await Promise.all(servers.map(server => new Promise(resolve => {
      if (!server.listening) return resolve();
      server.close(() => resolve()); server.closeAllConnections();
    })));
    result.servers_closed = servers.every(server => !server.listening);
  })();
  return shutdownPromise;
}
process.once('SIGTERM', () => { void shutdown(); });
process.once('SIGINT', () => { void shutdown(); });
try {
  requireCondition(process.env.DISPLAY === ':100' && process.argv.length === 2);
  for(const key of Object.keys(process.env))
    if(!['PATH','HOME','TMPDIR','DISPLAY','XAUTHORITY'].includes(key)) delete process.env[key];
  const sink = createServer((request,response) => {
    active.callback_http_requests++;
    // Synthetic fixture only: reduce request-target comparison immediately to a boolean.
    active.code_crossed_boundary ||= request.url.includes(sentinel);
    // Do not emit a response or initiate another navigation after the stop condition.
    stopped = true;
    request.socket.destroy();
    void shutdown();
  });
  sink.on('connection', () => { active.callback_tcp_connections++; });
  const sinkOrigin = await listen(sink);
  const callback = sinkOrigin + '/oauth/callback?code=' + sentinel + '&state=SYNTHETIC_REDIRECT_STATE';
  const source = createServer((request,response) => {
    if(stopped || request.method !== 'GET' || request.url !== '/start') {
      response.writeHead(404,{'Cache-Control':'no-store'}); response.end(); return;
    }
    active.source_http_redirects++;
    response.writeHead(302, {Location:callback,'Cache-Control':'no-store','Referrer-Policy':'no-referrer'});
    response.end();
  });
  const sourceOrigin = await listen(source);
  const {chromium} = createRequire(import.meta.url)('/home/juval/.npm/_npx/86170c4cd1c5da32/node_modules/playwright-core');
  browser = await chromium.launch({executablePath:'/opt/juval-browser/chromium-1243/chrome',
    chromiumSandbox:true,headless:false,timeout:15000});
  for(const mode of ['direct','redirect']) {
    requireCondition(!stopped);
    active = result[mode];
    const context = await browser.newContext({acceptDownloads:false,serviceWorkers:'block'});
    await context.routeWebSocket('**/*', socket => { stopped=true; socket.close(); void shutdown(); });
    context.on('request', request => { if(request.url() === callback) active.callback_request_event++; });
    await context.route('**/*', async route => {
      try {
        if(stopped) { await route.abort(); return; }
        const request = route.request();
        if(request.method() === 'GET' && request.url() === callback) {
          active.callback_route_calls++;
          await route.fulfill({status:200,contentType:'text/html',
            headers:{'Cache-Control':'no-store','Referrer-Policy':'no-referrer'},
            body:'<!doctype html><title>Synthetic control</title>'});
        } else if(request.method() === 'GET' && request.url() === sourceOrigin + '/start') {
          await route.continue(); // Only the owned synthetic source; NOT a real-flow adapter.
        } else await route.abort();
      } catch { stopped=true; void shutdown(); }
    });
    const page = await context.newPage();
    active.navigation_attempted = true;
    try { await page.goto(mode === 'direct' ? callback : sourceOrigin+'/start', {waitUntil:'load',timeout:10000}); }
    catch { if(!active.code_crossed_boundary) throw new Error('LAB_FAILED'); }
    if(active.code_crossed_boundary) {
      result.classification = 'GAP_REPRODUCED_CONTAINMENT_BLOCKED';
      break; // User STOP: no additional cases or candidate implementation.
    }
    await context.close();
    requireCondition(active.callback_tcp_connections === 0 && active.callback_http_requests === 0 &&
      active.callback_request_event === 1 && active.callback_route_calls === 1);
    if(mode === 'redirect') {
      requireCondition(active.source_http_redirects === 1);
      result.classification = 'GAP_NOT_REPRODUCED_SINGLE_302_ONLY';
    }
  }
} catch { /* Only finite classification/counters leave this process. */ }
finally { await shutdown(); }
if(!result.browser_closed || !result.servers_closed) result.classification = 'REPRODUCER_INCONCLUSIVE';
process.stdout.write(JSON.stringify(result)+'\n');
process.exitCode = result.classification === 'GAP_REPRODUCED_CONTAINMENT_BLOCKED' ? 2 :
  result.classification === 'GAP_NOT_REPRODUCED_SINGLE_302_ONLY' ? 0 : 1;

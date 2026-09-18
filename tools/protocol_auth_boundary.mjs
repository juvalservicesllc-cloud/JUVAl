/** Internal Chromium Fetch enforcement. Synthetic-only until separately authorized.
 * No protocol session, request object, URL, error or arbitrary command is exported.
 */
import {FlowPolicy, SYNTHETIC_ORIGIN, CALLBACK_ORIGIN} from './real_auth_flow.mjs';

export const SETUP_FAILURES = Object.freeze(['OWNERSHIP','PIPE_CHECK','PAGE_SESSION',
  'TARGET_GUARD','WEBSOCKET_GUARD','FETCH_ENABLE']);

function fixtureOrigin(raw) {
  const u = new URL(raw);
  if(u.origin !== raw || u.hostname !== '127.0.0.1' || u.protocol !== 'http:' ||
     +u.port < 1024 || [5900,5901,6080,6081,9011,9012,9222,18080].includes(+u.port))
    throw new Error('INVALID_FIXTURE_ORIGIN');
  return raw;
}

/** Trusted fixture origins only, never agent-protocol input. Exact path/query and
 * credentials are preserved when relocating a fixture origin to the finite policy.
 * The production callback constant and the policy itself are not configurable.
 * Owns one blank page/browser; close destroys the browser before releasing guards.
 */
export async function installProtocolBoundary(browser, context, page, policy, fixture) {
  if(!(policy instanceof FlowPolicy) || !policy.synthetic || policy.origin !== SYNTHETIC_ORIGIN)
    throw new Error('LIVE_TRANSPORT_DISABLED');
  let closing = false, failed = false, closePromise, stage = 'OWNERSHIP';
  let callbackIntercepted = false, redirectCallbackIntercepted = false;
  const close = () => {
    closing = true;
    return closePromise ??= browser.close();
  };
  const fail = () => {
    if(closing) return;
    failed = true;
    policy.fail();
    void close().catch(() => {}); // Lifecycle owner independently verifies teardown.
  };
  try {
    const source = fixtureOrigin(fixture.sourceOrigin);
    const sink = fixtureOrigin(fixture.callbackOrigin);
    if(source === sink || page.url() !== 'about:blank' || context.pages().length !== 1 ||
       browser.contexts().length !== 1) throw new Error('INVALID_OWNERSHIP');
    stage = 'PIPE_CHECK';
    const root = await browser.newBrowserCDPSession();
    root.on('close', fail);
    const {arguments: args} = await root.send('Browser.getBrowserCommandLine');
    if(!args.includes('--remote-debugging-pipe') || args.some(arg =>
      /^--(?:remote-debugging-port|remote-debugging-address|no-sandbox|disable-setuid-sandbox)(?:=|$)/.test(arg)))
      throw new Error('UNSAFE_TRANSPORT');
    stage = 'PAGE_SESSION';
    const session = await context.newCDPSession(page);
    session.on('close', fail);
    const {targetInfo} = await session.send('Target.getTargetInfo');
    const {frameTree} = await session.send('Page.getFrameTree');
    const mainFrame = frameTree.frame.id;
    // Unknown targets remain paused; never resume them or install a broader policy.
    const attached = event => {
      if(event.targetInfo.targetId !== targetInfo.targetId || event.waitingForDebugger) fail();
    };
    root.on('Target.attachedToTarget', attached);
    session.on('Target.attachedToTarget', attached);
    const guard = {autoAttach:true, waitForDebuggerOnStart:true, flatten:true,
      filter:[{type:'browser',exclude:true},{type:'tab',exclude:true},{}]};
    stage = 'TARGET_GUARD';
    await root.send('Target.setAutoAttach', guard);
    await session.send('Target.setAutoAttach', guard);
    stage = 'WEBSOCKET_GUARD';
    await context.routeWebSocket('**/*', socket => { policy.fail('UNEXPECTED_ROUTE'); socket.close(); fail(); });
    session.on('Fetch.authRequired', () => fail());
    session.on('Fetch.requestPaused', async event => {
      try {
        if(closing) return; // Keep paused until owned browser destruction.
        const u = new URL(event.request.url);
        const originalOrigin = u.origin;
        if(originalOrigin === source || originalOrigin === sink) {
          // Mutate origin components only; never read the code value.
          const logical = new URL(originalOrigin === source ? SYNTHETIC_ORIGIN : CALLBACK_ORIGIN);
          u.protocol = logical.protocol; u.hostname = logical.hostname; u.port = logical.port;
        } else {
          // Synthetic transport guard: even a policy-shaped real URL cannot pass.
          policy.fail('UNEXPECTED_ROUTE');
        }
        const main = event.resourceType === 'Document' && event.frameId === mainFrame;
        const action = policy.request(u.href, event.request.method, main);
        if(action === 'CALLBACK') {
          await session.send('Fetch.fulfillRequest', {requestId:event.requestId, responseCode:200,
            responseHeaders:[{name:'Content-Type',value:'text/html'},
              {name:'Cache-Control',value:'no-store'}, {name:'Referrer-Policy',value:'no-referrer'},
              {name:'Content-Security-Policy',value:"default-src 'none'; frame-ancestors 'none'"}],
            body:Buffer.from('<!doctype html><title>Contained callback</title>').toString('base64')});
          callbackIntercepted = true;
          redirectCallbackIntercepted ||= typeof event.redirectedRequestId === 'string';
        } else if(action === 'PROVIDER' && originalOrigin === source) {
          await session.send('Fetch.continueRequest', {requestId:event.requestId});
        } else {
          await session.send('Fetch.failRequest', {requestId:event.requestId,errorReason:'BlockedByClient'});
          fail();
        }
      } catch { fail(); }
    });
    stage = 'FETCH_ENABLE';
    await session.send('Fetch.enable', {patterns:[{urlPattern:'*',requestStage:'Request'}], handleAuthRequests:true});
    if(closing) throw new Error('BOUNDARY_SETUP_FAILED');
    return Object.freeze({
      evidence: () => ({pipeOnly:true, callbackIntercepted, redirectCallbackIntercepted, failed}),
      close,
    });
  } catch {
    policy.fail();
    try { await close(); } catch {}
    const error = new Error('PROTOCOL_BOUNDARY_UNAVAILABLE');
    error.phase = stage; // Fixed vocabulary only, never the underlying exception.
    throw error;
  }
}

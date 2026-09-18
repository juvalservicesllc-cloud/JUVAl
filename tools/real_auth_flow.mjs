/** Finite RF-03 route/transition model. Live transport is deliberately disabled. */
export const PROVIDER_ORIGIN = 'http://127.0.0.1:9011';
export const SYNTHETIC_ORIGIN = 'http://juval-mfa-synthetic.invalid';
export const CALLBACK_ORIGIN = 'http://127.0.0.1:18080';
const routes = Object.freeze({
  '/oauth2/authorize': ['LOGIN', ['GET', 'POST']],
  '/oauth2/two-factor-enable': ['ENROLLMENT', ['GET', 'POST']],
  '/oauth2/two-factor-enable-complete': ['ENROLLMENT_COMPLETE', ['GET', 'POST']],
  '/oauth2/consent': ['CONSENT', ['GET']],
  '/oauth2/two-factor': ['MFA_CHALLENGE_CANDIDATE', ['GET', 'POST']],
  '/oauth2/two-factor-methods': ['MFA_METHOD_CANDIDATE', ['GET', 'POST']],
});
const resources = new Set([
  '/css/entrypoints/fusionauth-hosted.css', '/css/font-awesome-4.7.0.min.css',
  '/images/favicon-128.png', '/images/favicon-32x32.png', '/images/footer-logo.svg',
  '/js/Util.js', '/js/entrypoints/oauth2/authorize.js', '/js/identityProvider/InProgress.js',
  '/js/jstz-min-1.0.6.js', '/js/oauth2/Authorize.js', '/js/oauth2/LocaleSelect.js',
  '/js/oauth2/OAuth2TwoFactorEnable.js', '/js/prime-min-1.7.0.js', '/js/qrcode-min-1.0.js',
]);
const outputPaths = Object.freeze(Object.fromEntries([
  ...Object.entries(routes).map(([path, [status]]) => [status, path]),
  ['CALLBACK_REACHED', '/oauth/callback'],
  ...['READY','UNEXPECTED_ROUTE','UNEXPECTED_TRANSITION','CALLBACK_REJECTED','FAILED','CLOSED','REJECTED'].map(x=>[x,null]),
]));
export function finiteEvidence(status) {
  return Object.hasOwn(outputPaths, status) ? {status, path: outputPaths[status]} : {status:'FAILED',path:null};
}
export function validEvidence(r) {
  return r !== null && typeof r === 'object' && Object.keys(r).sort().join(',') === 'path,status' &&
    typeof r.status === 'string' && Object.hasOwn(outputPaths,r.status) && r.path === outputPaths[r.status];
}
export class FlowPolicy {
  #cycle; #expectedState; #status = 'READY'; #latched = false;
  constructor(cycle, expectedState, synthetic = false) {
    if (![1,2].includes(cycle) || typeof expectedState !== 'string' || !expectedState)
      throw new Error('INVALID_CONFIGURATION');
    this.#cycle=cycle; this.#expectedState=expectedState;
    Object.defineProperty(this,'synthetic',{value:synthetic === true});
    Object.defineProperty(this,'origin',{value:this.synthetic ? SYNTHETIC_ORIGIN : PROVIDER_ORIGIN});
  }
  evidence() { return finiteEvidence(this.#status); }
  fail(status='FAILED') {
    if (!this.#latched) {
      this.#status=['UNEXPECTED_ROUTE','UNEXPECTED_TRANSITION','CALLBACK_REJECTED','FAILED'].includes(status)?status:'FAILED';
      this.#latched=true;
    }
    return 'ABORT';
  }
  close() { this.#status='CLOSED'; this.#latched=true; this.#expectedState=''; return this.evidence(); }
  #advance(next) {
    if (next === this.#status && next !== 'CALLBACK_REACHED') return true;
    const graph = {
      READY:['LOGIN'],
      LOGIN:this.#cycle===1 ? ['ENROLLMENT','CONSENT','MFA_METHOD_CANDIDATE','MFA_CHALLENGE_CANDIDATE','CALLBACK_REACHED'] : ['MFA_METHOD_CANDIDATE','MFA_CHALLENGE_CANDIDATE'],
      ENROLLMENT:['ENROLLMENT_COMPLETE'],
      ENROLLMENT_COMPLETE:['CONSENT','CALLBACK_REACHED'],
      MFA_METHOD_CANDIDATE:['MFA_CHALLENGE_CANDIDATE'],
      MFA_CHALLENGE_CANDIDATE:['CONSENT','CALLBACK_REACHED'],
      CONSENT:['CALLBACK_REACHED'],
    };
    if (!graph[this.#status]?.includes(next)) { this.fail('UNEXPECTED_TRANSITION'); return false; }
    this.#status=next; return true;
  }
  request(raw, method, mainDocument) {
    if (this.#latched) return 'ABORT';
    if (this.#status==='CALLBACK_REACHED') return this.fail('UNEXPECTED_TRANSITION');
    try {
      const u=new URL(raw);
      if (u.username || u.password) return this.fail('UNEXPECTED_ROUTE');
      if (u.origin===CALLBACK_ORIGIN && u.pathname==='/oauth/callback') {
        if (!mainDocument || method!=='GET') return this.fail('CALLBACK_REJECTED');
        const keys=[...u.searchParams.keys()];
        // Never retrieve the code value. State comparison is private and never emitted.
        if (keys.length!==2 || !keys.includes('code') || !keys.includes('state') ||
            u.searchParams.get('state')!==this.#expectedState) return this.fail('CALLBACK_REJECTED');
        if (!this.#advance('CALLBACK_REACHED')) return 'ABORT';
        this.#expectedState=''; // Callback values are not retained or exported.
        return 'CALLBACK';
      }
      if (u.origin!==this.origin) return this.fail('UNEXPECTED_ROUTE');
      if (!mainDocument) return method==='GET' && resources.has(u.pathname) ? 'PROVIDER' : this.fail('UNEXPECTED_ROUTE');
      const route=routes[u.pathname];
      if (!route || !route[1].includes(method)) return this.fail('UNEXPECTED_ROUTE');
      return this.#advance(route[0]) ? 'PROVIDER' : 'ABORT';
    } catch { return this.fail(); }
  }
}

/** Installs the synthetic callback handler. No receiver/listener exists here.
 * This is not proof of zero TCP or containment of network HTTP redirect chains.
 * responder is trusted fixture code, never a protocol argument. Live transport
 * must not be enabled until HTTP redirect containment and human gates are resolved.
 */
export async function installSyntheticBoundary(context, policy, responder) {
  if (!policy.synthetic || policy.origin!==SYNTHETIC_ORIGIN) throw new Error('LIVE_TRANSPORT_DISABLED');
  await context.routeWebSocket('**/*', socket => { policy.fail('UNEXPECTED_ROUTE'); socket.close(); });
  await context.route('**/*', async route => {
    try {
      const request=route.request();
      const main=request.isNavigationRequest() && request.frame()===request.frame().page().mainFrame();
      const action=policy.request(request.url(),request.method(),main);
      if (action==='CALLBACK') {
        await route.fulfill({status:200,contentType:'text/html',headers:{'Cache-Control':'no-store','Referrer-Policy':'no-referrer'},
          body:'<!doctype html><title>Contained callback</title><p>Callback contained.</p>'});
      } else if(action==='PROVIDER') {
        // Never route.continue/fetch: every synthetic request terminates in memory.
        await route.fulfill(await responder(new URL(request.url()).pathname));
      } else await route.abort();
    } catch { policy.fail(); try { await route.abort(); } catch {} }
  });
  context.on('page', page => {
    page.on('framenavigated', frame => {
      if (frame!==page.mainFrame()) return;
      const raw=frame.url();
      // Same-document history changes do not necessarily generate requests.
      if(raw==='about:blank') return;
      try {
        const u=new URL(raw);
        const current=policy.evidence();
        const origin=current.status==='CALLBACK_REACHED'?CALLBACK_ORIGIN:policy.origin;
        if(u.origin!==origin || u.pathname!==current.path) policy.fail('UNEXPECTED_ROUTE');
      } catch { policy.fail(); }
    });
  });
}

/** Finite agent-facing operations only; navigation is a fixed start action. */
export class RealFlowController {
  #page; #browser; #policy; #startURL; #started=false; #authorizedReal;
  constructor(page,browser,policy,startURL,authorizedReal=false) { this.#page=page;this.#browser=browser;this.#policy=policy;this.#startURL=startURL;this.#authorizedReal=authorizedReal===true; }
  async command(r) {
    if(!r || typeof r!=='object' || Object.keys(r).join(',')!=='op' || !['start','observe','close'].includes(r.op))
      return finiteEvidence('REJECTED');
    try {
      if(r.op==='close') { await this.#browser.close(); return this.#policy.close(); }
      if(r.op==='start') {
        if(this.#started) return finiteEvidence('REJECTED');
        this.#started=true;
        if(!this.#policy.synthetic && !this.#authorizedReal) {this.#policy.fail();return this.#policy.evidence();}
        const u=new URL(this.#startURL);
        if(u.origin!==this.#policy.origin || u.pathname!=='/oauth2/authorize') {this.#policy.fail();return this.#policy.evidence();}
        await this.#page.goto(this.#startURL,{waitUntil:'load',timeout:10000});
      }
      return this.#policy.evidence();
    } catch { this.#policy.fail(); return this.#policy.evidence(); }
  }
}

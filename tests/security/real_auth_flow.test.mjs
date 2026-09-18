import {test} from 'node:test';
import assert from 'node:assert/strict';
import {FlowPolicy,RealFlowController,finiteEvidence,validEvidence,installSyntheticBoundary,PROVIDER_ORIGIN,CALLBACK_ORIGIN} from '../../tools/real_auth_flow.mjs';
const state='SYNTHETIC_STATE_SENTINEL';
const cb=CALLBACK_ORIGIN+'/oauth/callback?code=SYNTHETIC_OAUTH_CODE_SENTINEL&state='+state+'#SYNTHETIC_FRAGMENT_SENTINEL';
const request=(p,path,method='GET')=>p.request(p.origin+path,method,true);
test('observed enrollment sequence and private callback correlation',()=>{
 const p=new FlowPolicy(1,state);
 for(const path of ['/oauth2/authorize','/oauth2/two-factor-enable','/oauth2/two-factor-enable-complete','/oauth2/consent']) assert.equal(request(p,path),'PROVIDER');
 assert.equal(p.request(cb,'GET',true),'CALLBACK');assert.deepEqual(p.evidence(),finiteEvidence('CALLBACK_REACHED'));
 assert.equal(p.request(cb,'GET',true),'ABORT');
 assert(!JSON.stringify(p.evidence()).includes('SENTINEL'));
});
test('cycle two cannot bypass challenge or substitute enrollment',()=>{
 for(const next of ['/oauth2/consent','/oauth2/two-factor-enable']) {
  const p=new FlowPolicy(2,state);request(p,'/oauth2/authorize');request(p,next);
  assert.equal(p.evidence().status,'UNEXPECTED_TRANSITION');assert.equal(p.request(cb,'GET',true),'ABORT');
 }
 const p=new FlowPolicy(2,state);request(p,'/oauth2/authorize');assert.equal(p.request(cb,'GET',true),'ABORT');
});
test('candidate methods remain candidate; selection alone cannot satisfy challenge',()=>{
 const p=new FlowPolicy(2,state);request(p,'/oauth2/authorize');request(p,'/oauth2/two-factor-methods');
 assert.equal(p.evidence().status,'MFA_METHOD_CANDIDATE');assert.equal(p.request(cb,'GET',true),'ABORT');
 const q=new FlowPolicy(2,state);request(q,'/oauth2/authorize');request(q,'/oauth2/two-factor-methods');request(q,'/oauth2/two-factor');
 assert.equal(q.evidence().status,'MFA_CHALLENGE_CANDIDATE');assert.equal(q.request(cb,'GET',true),'CALLBACK');
});
test('wrong origins, methods, unknown paths and incomplete transitions latch permanently',()=>{
 for(const url of ['http://elsewhere.invalid/oauth2/authorize',PROVIDER_ORIGIN+'/password/forgot',PROVIDER_ORIGIN+'/SYNTHETIC_PASSWORD_SENTINEL', 'file:///oauth2/authorize']) {
  const p=new FlowPolicy(1,state);assert.equal(p.request(url,'GET',true),'ABORT');assert.equal(request(p,'/oauth2/authorize'),'ABORT');assert(validEvidence(p.evidence()));
 }
 const p=new FlowPolicy(1,state);request(p,'/oauth2/authorize');request(p,'/oauth2/two-factor-enable');assert.equal(p.request(cb,'GET',true),'ABORT');
 const q=new FlowPolicy(1,state);request(q,'/oauth2/authorize');assert.equal(request(q,'/oauth2/consent','POST'),'ABORT');
});
test('callback errors/state duplicates/mismatch/subframe/post fail with no query output',()=>{
 for(const raw of [cb.replace(state,'wrong'),cb+'&state=duplicate',CALLBACK_ORIGIN+'/oauth/callback?error=SYNTHETIC_OAUTH_CODE_SENTINEL',cb.replace('&state=', '&state=duplicate&state=')]) {
  const p=new FlowPolicy(1,state);request(p,'/oauth2/authorize');
  // The appended text after # is a fragment, not a duplicate query: it remains private.
  const allowed=raw===cb+'&state=duplicate';
  assert.equal(p.request(raw,'GET',true),allowed?'CALLBACK':'ABORT');assert(!JSON.stringify(p.evidence()).includes('SENTINEL'));
 }
 for(const [method,main] of [['POST',true],['GET',false]]) {const p=new FlowPolicy(1,state);request(p,'/oauth2/authorize');assert.equal(p.request(cb,method,main),'ABORT');}
});
test('finite protocol rejects arbitrary operations; exceptions never escape',async()=>{
 const p=new FlowPolicy(1,state,true);const c=new RealFlowController({goto:async()=>{throw new Error(cb)}},{close:async()=>{}},p,p.origin+'/oauth2/authorize');
 for(const op of ['evaluate','navigate','cookies','console','network','storage','snapshot','trace']) assert.equal((await c.command({op})).status,'REJECTED');
 assert.equal((await c.command({op:'start',url:cb})).status,'REJECTED');assert.deepEqual(await c.command({op:'start'}),finiteEvidence('FAILED'));
 assert.deepEqual(await c.command({op:'close'}),finiteEvidence('CLOSED'));
 assert(!validEvidence({status:'LOGIN',path:cb}));
});
test('real provider transport is disabled before any context API is used',async()=>{
 const p=new FlowPolicy(1,state);assert.equal(p.origin,PROVIDER_ORIGIN);
 await assert.rejects(installSyntheticBoundary({},p,()=>{}),/LIVE_TRANSPORT_DISABLED/);
});
test('live controller start cannot invoke browser navigation',async()=>{
 let contacted=false;const p=new FlowPolicy(1,state);
 const c=new RealFlowController({goto:async()=>{contacted=true}},{close:async()=>{}},p,PROVIDER_ORIGIN+'/oauth2/authorize');
 assert.equal((await c.command({op:'start'})).status,'FAILED');assert.equal(contacted,false);
});
test('resource permission is GET-only and distinct from main-document transitions',()=>{
 const p=new FlowPolicy(1,state);request(p,'/oauth2/authorize');
 assert.equal(p.request(PROVIDER_ORIGIN+'/js/oauth2/OAuth2TwoFactorEnable.js?fixture=SYNTHETIC_STATE_SENTINEL','GET',false),'PROVIDER');
 assert.equal(p.evidence().status,'LOGIN');
 assert.equal(p.request(PROVIDER_ORIGIN+'/assets/unobserved','GET',false),'ABORT');
 assert.equal(p.request(PROVIDER_ORIGIN+'/js/Util.js','GET',false),'ABORT');
 const q=new FlowPolicy(1,state);request(q,'/oauth2/authorize');assert.equal(q.request(PROVIDER_ORIGIN+'/js/Util.js','POST',false),'ABORT');
});

test('explicit authorized real start uses fixed provider path while default stays disabled',async()=>{
 let called=0;const p=new FlowPolicy(1,state);
 const c=new RealFlowController({goto:async()=>{called++}},{close:async()=>{}},p,PROVIDER_ORIGIN+'/oauth2/authorize',true);
 await c.command({op:'start'});assert.equal(called,1);
 const q=new FlowPolicy(1,state);
 const bad=new RealFlowController({goto:async()=>{called++}},{close:async()=>{}},q,PROVIDER_ORIGIN+'/api/users',true);
 assert.equal((await bad.command({op:'start'})).status,'FAILED');assert.equal(called,1);
});

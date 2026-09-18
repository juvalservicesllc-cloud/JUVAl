import {test} from 'node:test';
import assert from 'node:assert/strict';
import {EventEmitter} from 'node:events';
import {FlowPolicy} from '../../tools/real_auth_flow.mjs';
import {installProtocolBoundary} from '../../tools/protocol_auth_boundary.mjs';

const sourceOrigin='http://127.0.0.1:24001', callbackOrigin='http://127.0.0.1:24002';
const state='SYNTHETIC_PROTOCOL_STATE';
const callback=callbackOrigin+'/oauth/callback?code=SYNTHETIC_PROTOCOL_CODE&state='+state;
async function fixture({cycle=1,synthetic=true,args=['--remote-debugging-pipe'],reject=null,auxiliary=false}={}) {
  const policy=new FlowPolicy(cycle,state,synthetic), commands=[];
  const root=new EventEmitter(), session=new EventEmitter();
  const send=async(method,params)=>{
    commands.push({method,params});
    if(method===reject) throw new Error('SYNTHETIC_PRIVATE_ERROR');
    if(method==='Target.setAutoAttach' && auxiliary) {
      auxiliary=false;root.emit('Target.attachedToTarget',{targetInfo:{targetId:'auxiliary',type:'other'},waitingForDebugger:false});
    }
    if(method==='Target.closeTarget') return {success:true};
    if(method==='Browser.getBrowserCommandLine') return {arguments:args};
    if(method==='Target.getTargetInfo') return {targetInfo:{targetId:'owned',type:'page'}};
    if(method==='Page.getFrameTree') return {frameTree:{frame:{id:'main'}}};
    return {};
  };
  root.send=session.send=send;
  let closed=false, contacted=false;
  const page={url:()=> 'about:blank'};
  const context={pages:()=>[page],newCDPSession:async()=>session,routeWebSocket:async()=>{}};
  const browser={contexts:()=>[context],newBrowserCDPSession:async()=>{contacted=true;return root;},
    close:async()=>{closed=true;session.emit('close');root.emit('close');}};
  const start=()=>installProtocolBoundary(browser,context,page,policy,{sourceOrigin,callbackOrigin});
  let id=0;
  const pause=async(url,extra={})=>{
    const event={requestId:String(++id),request:{url,method:'GET'},frameId:'main',resourceType:'Document',...extra};
    session.emit('Fetch.requestPaused',event);
    await new Promise(resolve=>setImmediate(resolve));
    return commands.filter(c=>c.params?.requestId===event.requestId).map(c=>c.method);
  };
  return {policy,commands,root,session,start,pause,closed:()=>closed,contacted:()=>contacted};
}

test('direct and redirected callbacks use the same policy and fulfill without continue',async()=>{
  for(const redirected of [false,true]) {
    const f=await fixture(), boundary=await f.start();
    assert.deepEqual(await f.pause(sourceOrigin+'/oauth2/authorize'),['Fetch.continueRequest']);
    assert.deepEqual(await f.pause(callback,redirected?{redirectedRequestId:'previous'}:{}),['Fetch.fulfillRequest']);
    assert.equal(f.policy.evidence().status,'CALLBACK_REACHED');
    assert.deepEqual(boundary.evidence(),{pipeOnly:true,callbackIntercepted:true,redirectCallbackIntercepted:redirected,failed:false});
    assert(!JSON.stringify(f.commands).includes('SYNTHETIC_PROTOCOL_CODE'));
    assert(!JSON.stringify(boundary.evidence()).includes(state));
    const enabled=f.commands.find(c=>c.method==='Fetch.enable');
    assert.deepEqual(enabled.params.patterns,[{urlPattern:'*',requestStage:'Request'}]);
    await boundary.close();assert(f.closed());
    assert(!f.commands.some(c=>['Fetch.disable','Runtime.runIfWaitingForDebugger'].includes(c.method)));
  }
});

test('unknown origin, path, method, shape and transition cannot bypass protocol enforcement',async()=>{
  const cases=[
    {url:callback.replace(callbackOrigin,'http://127.0.0.1:24003')},
    {url:callback.replace('/oauth/callback','/oauth/unexpected')},
    {url:callback,extra:{request:{url:callback,method:'POST'}}},
    {url:callback.replace(state,'wrong')},
    {url:callback,cycle:2},
    {url:callback,extra:{frameId:'other'}},
    {url:'http://127.0.0.1:9011/oauth2/authorize'},
    {url:callback.replace('127.0.0.1:24002','user:pass@127.0.0.1:24002')},
  ];
  for(const c of cases) {
    const f=await fixture({cycle:c.cycle??1});await f.start();
    await f.pause(sourceOrigin+'/oauth2/authorize');
    assert.deepEqual(await f.pause(c.url,c.extra),['Fetch.failRequest']);
    assert(f.closed());
    assert.equal(f.policy.request(callback,'GET',true),'ABORT');
  }
});

test('reject live policies before any protocol operation; reject network debugging and weakened sandbox',async()=>{
  const live=await fixture({synthetic:false});
  await assert.rejects(live.start(),/LIVE_TRANSPORT_DISABLED/);assert(!live.contacted());
  for(const args of [[],['--remote-debugging-port=9222'],['--remote-debugging-pipe','--remote-debugging-port=0'],
    ['--remote-debugging-pipe','--no-sandbox'],['--remote-debugging-pipe','--disable-setuid-sandbox']]) {
    const f=await fixture({args});await assert.rejects(f.start(),/PROTOCOL_BOUNDARY_UNAVAILABLE/);
    assert(f.closed());assert(!f.commands.some(c=>c.method==='Fetch.enable'));
  }
});

test('setup failure, protocol failure, detach and extra targets close the owned browser',async()=>{
  const setup=await fixture({reject:'Fetch.enable'});
  await assert.rejects(setup.start(),error => error.message === 'PROTOCOL_BOUNDARY_UNAVAILABLE' &&
    error.phase === 'FETCH_ENABLE' && !JSON.stringify(error).includes('SYNTHETIC_PRIVATE_ERROR'));
  assert(setup.closed());
  const failure=await fixture({reject:'Fetch.fulfillRequest'}), b=await failure.start();
  await failure.pause(sourceOrigin+'/oauth2/authorize');await failure.pause(callback);
  assert(failure.closed());assert(b.evidence().failed);assert(!b.evidence().callbackIntercepted);
  for(const event of ['close','Target.attachedToTarget']) {
    const f=await fixture(), boundary=await f.start();
    f.session.emit(event,{targetInfo:{targetId:'unexpected'},waitingForDebugger:true});
    await new Promise(resolve=>setImmediate(resolve));
    assert(f.closed());assert(boundary.evidence().failed);
    assert(!f.commands.some(c=>c.method==='Runtime.runIfWaitingForDebugger'));
  }
});

test('pre-existing auxiliary target is destroyed before installation without resuming it',async()=>{
  const f=await fixture({auxiliary:true}), boundary=await f.start();
  const closed=f.commands.findIndex(c=>c.method==='Target.closeTarget');
  const enabled=f.commands.findIndex(c=>c.method==='Fetch.enable');
  assert(closed>=0 && enabled>closed);assert(!f.closed());
  assert(!f.commands.some(c=>c.method==='Runtime.runIfWaitingForDebugger'));
  await boundary.close();
  const rejected=await fixture({auxiliary:true,reject:'Target.closeTarget'});
  await assert.rejects(rejected.start(),/PROTOCOL_BOUNDARY_UNAVAILABLE/);
  assert(rejected.closed());
});

/** Trusted synthetic fixture driver, not an agent-facing evaluation interface. */
import {createRequire} from 'node:module';
import {FlowPolicy,RealFlowController,installSyntheticBoundary,SYNTHETIC_ORIGIN,CALLBACK_ORIGIN,validEvidence} from '../../tools/real_auth_flow.mjs';
const scenarios=new Set(['cycle1','cycle2','unexpected-route','wrong-origin','skip-challenge','bad-state','history-change','browser-exception']);
const scenario=process.argv[2];
const markers=['OAUTH_CODE','STATE','FRAGMENT','PASSWORD','TOTP','RECOVERY_CODE'].map(x=>`SYNTHETIC_${x}_SENTINEL`);
const state=markers[1];
let browser, controller;
const output=[];
const emit=r=>{if(!validEvidence(r))throw new Error('SCHEMA');output.push(r);process.stdout.write(JSON.stringify(r)+'\n');};
try {
  if(!scenarios.has(scenario)||process.env.DISPLAY!==':100')throw new Error('CONFIG');
  for(const key of Object.keys(process.env))if(!['PATH','HOME','DISPLAY','XAUTHORITY','TMPDIR'].includes(key))delete process.env[key];
  const {chromium}=createRequire(import.meta.url)('/home/juval/.npm/_npx/86170c4cd1c5da32/node_modules/playwright-core');
  browser=await chromium.launch({executablePath:'/opt/juval-browser/chromium-1243/chrome',chromiumSandbox:true,headless:false,timeout:15000});
  const context=await browser.newContext({acceptDownloads:false,serviceWorkers:'block'});
  const cycle=['cycle2','skip-challenge'].includes(scenario)?2:1;
  const policy=new FlowPolicy(cycle,state,true);
  let callback=CALLBACK_ORIGIN+'/oauth/callback?code='+markers[0]+'&state='+state+'#fragment='+markers[2];
  if(scenario==='bad-state')callback=callback.replace(state,'SYNTHETIC_WRONG_STATE_SENTINEL');
  const sequence=cycle===1?['/oauth2/authorize','/oauth2/two-factor-enable','/oauth2/two-factor-enable-complete','/oauth2/consent']:
    ['/oauth2/authorize','/oauth2/two-factor-methods','/oauth2/two-factor','/oauth2/consent'];
  await installSyntheticBoundary(context,policy,async path=>{
    let next=sequence.indexOf(path)+1<sequence.length?SYNTHETIC_ORIGIN+sequence[sequence.indexOf(path)+1]:callback;
    if(path==='/oauth2/authorize') {
      if(scenario==='unexpected-route')next=SYNTHETIC_ORIGIN+'/SYNTHETIC_PASSWORD_SENTINEL';
      if(scenario==='wrong-origin')next='http://wrong-synthetic.invalid/oauth2/authorize';
      if(scenario==='skip-challenge')next=callback;
      if(scenario==='browser-exception')throw new Error(callback);
    }
    const redirect=scenario==='history-change'?"history.replaceState(null,'','/SYNTHETIC_PASSWORD_SENTINEL')":`location.href=${JSON.stringify(next)}`;
    return {status:200,contentType:'text/html',body:`<!doctype html><title>${markers[3]}</title><input type=password value="${markers[3]}"><p>${markers[5]}</p><script>console.error(${JSON.stringify(markers.join(' '))});setTimeout(()=>{${redirect}},60)</script>`};
  });
  const page=await context.newPage();
  controller=new RealFlowController(page,browser,policy,SYNTHETIC_ORIGIN+'/oauth2/authorize?fixture='+markers[3]+'#'+markers[2]);
  emit(await controller.command({op:'start'}));
  const terminal=new Set(['CALLBACK_REACHED','UNEXPECTED_ROUTE','UNEXPECTED_TRANSITION','CALLBACK_REJECTED','FAILED']);
  const deadline=Date.now()+15000;
  while(!terminal.has(output.at(-1).status)&&Date.now()<deadline) {
    await new Promise(resolve=>setTimeout(resolve,20));
    const r=await controller.command({op:'observe'});
    if(r.status!==output.at(-1).status)emit(r);
  }
  if(!terminal.has(output.at(-1).status))throw new Error('TIMEOUT');
  emit(await controller.command({op:'close'}));
  if(output.at(-1).status!=='CLOSED')throw new Error('CLEANUP');
} catch {
  process.stdout.write('{"status":"FAILED","path":null}\n');process.exitCode=1;
} finally {
  if(browser)try{await browser.close();}catch{process.exitCode=1;}
}

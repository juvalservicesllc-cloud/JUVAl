/** Single authorized human-operated cycle; finite stdin/stdout only. */
import {createRequire} from 'node:module';
import {createInterface} from 'node:readline';
import {randomBytes,createHash} from 'node:crypto';
import {FlowPolicy,RealFlowController,PROVIDER_ORIGIN,CALLBACK_ORIGIN,validEvidence} from './real_auth_flow.mjs';
import {installAuthorizedRealBoundary} from './protocol_auth_boundary.mjs';

let browser, boundary, controller, closing=false;
const emit = r => process.stdout.write(JSON.stringify(validEvidence(r)?r:{status:'FAILED',path:null})+'\n');
async function close() {
  if(closing) return;
  closing=true;
  try { if(boundary) await boundary.close(); else if(browser) await browser.close(); }
  catch { process.exitCode=1; }
}
process.once('SIGTERM',async()=>{await close();process.exit();});
process.once('SIGINT',async()=>{await close();process.exit();});
try {
  const cycle=Number(process.argv[2]);
  if(process.argv.length!==3 || ![1,2].includes(cycle) || process.env.DISPLAY!==':100') throw new Error('CONFIG');
  for(const key of Object.keys(process.env))
    if(!['PATH','HOME','TMPDIR','DISPLAY','XAUTHORITY'].includes(key))delete process.env[key];
  const {chromium}=createRequire(import.meta.url)('/home/juval/.npm/_npx/86170c4cd1c5da32/node_modules/playwright-core');
  browser=await chromium.launch({executablePath:'/opt/juval-browser/chromium-1243/chrome',
    args:['--enable-automation'],chromiumSandbox:true,headless:false,timeout:15000});
  const context=await browser.newContext({acceptDownloads:false,serviceWorkers:'block'});
  const page=await context.newPage();
  const state=randomBytes(32).toString('base64url');
  const policy=new FlowPolicy(cycle,state);
  boundary=await installAuthorizedRealBoundary(browser,context,page,policy);
  const start=new URL(PROVIDER_ORIGIN+'/oauth2/authorize');
  const verifier=randomBytes(32).toString('base64url');
  start.search=new URLSearchParams({client_id:'84f077a0-b2b0-4655-8168-082b2233d029',
    tenantId:'5fcaaf07-8832-491a-a6e7-35d348a591b6',response_type:'code',scope:'openid',
    redirect_uri:CALLBACK_ORIGIN+'/oauth/callback',state,nonce:randomBytes(32).toString('base64url'),
    code_challenge:createHash('sha256').update(verifier).digest('base64url'),code_challenge_method:'S256'}).toString();
  controller=new RealFlowController(page,browser,policy,start.href,true);
  emit({status:'READY',path:null}); // Still blank; no provider contact before START.
  const input=createInterface({input:process.stdin,terminal:false});
  for await(const line of input) {
    let r;
    try { r=JSON.parse(line); } catch { emit({status:'REJECTED',path:null});continue; }
    const result=await controller.command(r);emit(result);
    if(result.status==='CLOSED' || ['FAILED','UNEXPECTED_ROUTE','UNEXPECTED_TRANSITION','CALLBACK_REJECTED'].includes(result.status))break;
  }
} catch { emit({status:'FAILED',path:null});process.exitCode=1; }
finally { await close(); }

/** Fresh-process lifecycle owner. No real provider or callback HTTP receiver. */
import {spawn,execFileSync} from 'node:child_process';
import {mkdtemp,readdir,readFile,rm,readlink} from 'node:fs/promises';
import {join} from 'node:path';
import {validEvidence} from '../../tools/real_auth_flow.mjs';
const markers=['OAUTH_CODE','STATE','FRAGMENT','PASSWORD','TOTP','RECOVERY_CODE','WRONG_STATE'].map(x=>`SYNTHETIC_${x}_SENTINEL`);
const expected=new Map([['cycle1','CALLBACK_REACHED'],['cycle2','CALLBACK_REACHED'],['unexpected-route','UNEXPECTED_ROUTE'],['wrong-origin','UNEXPECTED_ROUTE'],['skip-challenge','UNEXPECTED_TRANSITION'],['bad-state','CALLBACK_REJECTED'],['history-change','UNEXPECTED_ROUTE'],['browser-exception','FAILED']]);
const ensure=(ok,code)=>{if(!ok)throw new Error(code)};
async function dedicatedPids() {
 const pids=[];
 for(const name of await readdir('/proc'))if(/^\d+$/.test(name))try{
  if((await readlink('/proc/'+name+'/exe')).startsWith('/opt/juval-browser/chromium-1243/'))pids.push(name);
 }catch{}
 return pids;
}
const listenerBaseline=()=>execFileSync('ss',['-H','-lntu'],{encoding:'utf8'}).split('\n').filter(Boolean).map(l=>{const p=l.trim().split(/\s+/);return p[0]+' '+p[4]}).sort().join('\n');
const adminBaseline=async()=>({exe:await readlink('/proc/396207/exe'),start:(await readFile('/proc/396207/stat','utf8')).split(')').at(-1).trim().split(/\s+/)[19]});
const beforePorts=listenerBaseline();
const beforeAdmin=JSON.stringify(await adminBaseline());
let files=0, responses=0, lastRuntime=null, lastPid=null, cases=0;
try {
 for(const [scenario,status] of expected) {
  ensure((await dedicatedPids()).length===0,'PRIOR_BROWSER_REMAINS');
  const runtime=await mkdtemp(join(process.env.JUVAL_LAB_TMP,'cycle-'));
  ensure(runtime!==lastRuntime,'RUNTIME_REUSED');
  let child, exitResult;
  try {
   child=spawn(process.execPath,['tests/security/real_auth_worker.mjs',scenario],{env:{PATH:process.env.PATH,HOME:runtime,TMPDIR:runtime,DISPLAY:process.env.DISPLAY,XAUTHORITY:process.env.XAUTHORITY},stdio:['ignore','pipe','pipe']});
   ensure(child.pid!==lastPid,'PROCESS_REUSED');
   let stdout='',stderr='';
   child.stdout.on('data',d=>stdout+=d);child.stderr.on('data',d=>stderr+=d);
   exitResult=await new Promise((resolve,reject)=>{child.on('error',()=>reject(new Error('SPAWN')));child.on('exit',(code,signal)=>resolve({code,signal}));});
   ensure(!markers.some(s=>stdout.includes(s)||stderr.includes(s)),'SENTINEL_LEAK_STOP');
   ensure(stderr==='','STDERR_NOT_EMPTY');
   const result=stdout.trim().split('\n').map(s=>JSON.parse(s));
   ensure(result.every(validEvidence),'OUTPUT_SCHEMA');responses+=result.length;
   ensure(exitResult.code===0,'WORKER_EXIT');
   ensure(result.at(-1).status==='CLOSED','NOT_CLOSED');
   ensure(result.at(-2).status===status,'UNEXPECTED_RESULT');
   if(scenario==='cycle2')ensure(result.some(r=>r.status==='MFA_CHALLENGE_CANDIDATE'),'CHALLENGE_SKIPPED');
   async function scan(dir) {
    for(const e of await readdir(dir,{withFileTypes:true})) {
     const p=join(dir,e.name);
     if(e.isDirectory())await scan(p);
     else if(e.isFile()){files++;const bytes=await readFile(p);ensure(!markers.some(s=>bytes.includes(Buffer.from(s))),'ARTIFACT_LEAK_STOP');}
    }
   }
   await scan(runtime);
   ensure(!(await readdir(runtime)).some(n=>n.startsWith('playwright_')),'PROFILE_REMAINS');
   ensure((await dedicatedPids()).length===0,'BROWSER_REMAINS');
   ensure(listenerBaseline()===beforePorts,'LISTENER_CHANGED');
   ensure(JSON.stringify(await adminBaseline())===beforeAdmin,'ADMIN_CHANGED');
   lastRuntime=runtime;lastPid=child.pid;cases++;
  } finally {
   if(child&&exitResult===undefined){child.kill('SIGTERM');}
   await rm(runtime,{recursive:true,force:true});
  }
  try {await readdir(runtime);throw new Error('RUNTIME_REMAINS')}catch(e){ensure(e.code==='ENOENT','RUNTIME_REMAINS');}
 }
 console.log(JSON.stringify({classification:'SYNTHETIC_BOUNDARY_PASS',output_leakage:false,artifact_leakage:false,
  cases,responses,remaining_files_inspected:files,profile_cleanup:true,second_cycle_fresh:true,
  callback_intercepted:true,callback_http_server:false,live_transport_enabled:false}));
} catch {
 console.log('{"classification":"REAL_FLOW_SYNTHETIC_FAILED"}');process.exitCode=1;
}

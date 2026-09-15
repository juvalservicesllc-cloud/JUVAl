/** Synthetic-only subprocess integration. Never serves real authentication. */
import {createServer} from 'node:http';
import {spawn} from 'node:child_process';
import {createInterface} from 'node:readline';
import {readdir, readFile} from 'node:fs/promises';
const markers = ['PASSWORD','TOTP','OAUTH_CODE','COOKIE','RECOVERY_CODE'].map(x=>`SYNTHETIC_${x}_SENTINEL`);
const check = (ok, code) => { if (!ok) throw new Error(code); };
let server, child; let stderr = ''; const outputs = []; let fixturesReady = 0;
try {
  server = createServer((req,res) => {
    if(req.url === '/callback?fixture-ready=1') { fixturesReady++; res.writeHead(204); res.end(); return; }
    res.setHeader('Content-Type','text/html');
    res.end(`<title>${markers[0]}</title><input type=password value="${markers[0]}"><input value="${markers[1]}"><p>${markers[4]}</p>
<script>
document.cookie='synthetic=${markers[3]}; SameSite=Strict';
localStorage.setItem('synthetic','${markers[3]}');sessionStorage.setItem('synthetic','${markers[1]}');
console.error('${markers.join(' ')}');
history.replaceState(null,'',location.pathname+'?code=${markers[2]}#${markers[4]}');
fetch('/callback?fixture-ready=1');
</script>`);
  });
  await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
  const origin = `http://127.0.0.1:${server.address().port}`;
  child = spawn(process.execPath,['tools/restricted_auth_evidence.mjs'],{env:{
    PATH:process.env.PATH, HOME:process.env.JUVAL_LAB_TMP, TMPDIR:process.env.JUVAL_LAB_TMP,
    DISPLAY:process.env.DISPLAY, XAUTHORITY:process.env.XAUTHORITY, JUVAL_SYNTHETIC_ORIGIN:origin,
    // Must be removed by controller before Playwright loads.
    DEBUG:'pw:api', PWDEBUG:'0'},stdio:['pipe','pipe','pipe']});
  child.stderr.on('data',d=>{stderr+=d});
  const exited = new Promise(resolve=>child.on('exit',(code,signal)=>resolve({code,signal})));
  const lines = createInterface({input:child.stdout})[Symbol.asyncIterator]();
  async function next() {
    const r = await lines.next(); check(!r.done,'EARLY_EXIT');
    outputs.push(r.value);
    check(!markers.some(s=>r.value.includes(s)),'SENTINEL_LEAK_STOP');
    const value = JSON.parse(r.value);
    check(Object.keys(value).sort().join(',')==='path,status','SCHEMA');
    check(['READY','OBSERVED','REJECTED','CLOSED','FAILED'].includes(value.status),'STATUS');
    check([null,'/login','/challenge','/callback'].includes(value.path),'PATH');
    return value;
  }
  check((await next()).status==='READY','LAUNCH');
  for(const state of ['login','challenge','callback']) {
    child.stdin.write(JSON.stringify({op:'visit',state})+'\n');
    const r=await next();check(r.status==='OBSERVED'&&r.path==='/'+state,'NORMALIZED_ROUTE');
    child.stdin.write('{"op":"observe"}\n');check((await next()).path==='/'+state,'OBSERVE');
  }
  for(let i=0;i<100 && fixturesReady<3;i++) await new Promise(resolve=>setTimeout(resolve,20));
  check(fixturesReady===3,'FIXTURE_EXECUTION');
  for(const op of ['evaluate','snapshot','console','network','cookies','storageState','screenshot','trace','navigate']) {
    child.stdin.write(JSON.stringify({op,value:markers.join(' ')})+'\n');
    check((await next()).status==='REJECTED','FAIL_CLOSED');
  }
  child.stdin.write(JSON.stringify({op:'observe',extra:markers[0]})+'\n');
  check((await next()).status==='REJECTED','EXTRA_KEYS');
  child.stdin.write('{broken\n');check((await next()).status==='REJECTED','MALFORMED');
  child.stdin.write('{"op":"close"}\n');check((await next()).status==='CLOSED','CLOSE');
  child.stdin.end();check((await exited).code===0,'EXIT');
  check(stderr==='','STDERR_OUTPUT_STOP');
  // All runtime files are owned by this synthetic subprocess scope; inspect only after close.
  let files=0;
  async function scan(dir) {
    for(const e of await readdir(dir,{withFileTypes:true})) {
      const p=dir+'/'+e.name;
      if(e.isDirectory())await scan(p);
      else if(e.isFile()){files++;const b=await readFile(p);check(!markers.some(s=>b.includes(Buffer.from(s))),'ARTIFACT_LEAK_STOP');}
    }
  }
  await scan(process.env.JUVAL_LAB_TMP);
  check(!(await readdir(process.env.JUVAL_LAB_TMP)).some(n=>n.startsWith('playwright_')),'PROFILE_CLEANUP');
  console.log(JSON.stringify({classification:'SYNTHETIC_BOUNDARY_PASS',responses:outputs.length,
    output_leakage:false,artifact_leakage:false,remaining_files:files,profile_cleanup:true, fixtures_executed:fixturesReady}));
} catch(e) {
  // Only our finite error codes may leave this harness; never subprocess exceptions/data.
  console.log(JSON.stringify({classification:'SYNTHETIC_BOUNDARY_FAILED'}));process.exitCode=1;
} finally {
  if(child&&child.exitCode===null) {child.stdin.end();await new Promise(resolve=>setTimeout(resolve,1000));if(child.exitCode===null)child.kill('SIGTERM');}
  if(server){server.closeAllConnections();await new Promise(resolve=>server.close(resolve));}
}

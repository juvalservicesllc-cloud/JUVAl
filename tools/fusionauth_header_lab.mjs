/** Read-only generic-provider header compatibility lab, NOT a real MFA flow.
 * No nginx/public activation, credentials, POST, email, HAR or cookie export.
 * Uses existing portal Playwright. All listeners and browser contexts are disposable.
 */
import {createServer, request} from 'node:http';
import {chromium} from '../project-portal/node_modules/@playwright/test/index.mjs';
const candidates=[{}, {'X-Content-Type-Options':'nosniff'}, {'Referrer-Policy':'same-origin'},
  {'X-Frame-Options':'SAMEORIGIN'},
  {'Permissions-Policy':'publickey-credentials-get=(self), publickey-credentials-create=(self)'}];
const allowed=path=>['/oauth2/two-factor','/password/forgot'].includes(path)
  || ['/css/','/js/','/images/','/fonts/'].some(prefix=>path.startsWith(prefix))
  || path==='/assets/icons/fingerprint-overlay.svg';
const browser=await chromium.launch({headless:true,executablePath:process.env.JUVAL_LAB_CHROMIUM});
try {
 for(const headers of candidates){
  const server=createServer((req,res)=>{
   const path=new URL(req.url,'http://127.0.0.1').pathname;
   if(req.method!=='GET'||!allowed(path)){res.writeHead(404);res.end();return;}
   // Deliberately no inbound cookies/authentication/forwarded headers or query values.
   const upstream=request({hostname:'127.0.0.1',port:9011,path,method:'GET',timeout:5000},response=>{
    const outgoing={'Content-Type':response.headers['content-type']??'application/octet-stream',...headers};
    res.writeHead(response.statusCode,outgoing);response.pipe(res);
   });
   upstream.on('timeout',()=>upstream.destroy());
   upstream.on('error',()=>{if(!res.headersSent)res.writeHead(502);res.end();});upstream.end();
  });
  await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
  const base=`http://127.0.0.1:${server.address().port}`;
  const context=await browser.newContext({serviceWorkers:'block',acceptDownloads:false});
  try {
   await context.route('**/*',route=>new URL(route.request().url()).origin===base?route.continue():route.abort());
   for(const path of ['/oauth2/two-factor','/password/forgot']){
    const page=await context.newPage();const assets=[];const failures=[];
    page.on('response',r=>{const u=new URL(r.url());if(u.origin===base)assets.push({path:u.pathname,status:r.status(),type:r.request().resourceType()});});
    page.on('requestfailed',r=>failures.push(new URL(r.url()).pathname));
    const response=await page.goto(base+path,{waitUntil:'networkidle',timeout:15000});
    const headerReadback=Object.fromEntries(Object.keys(headers).map(name=>[name,response.headers()[name.toLowerCase()]]));
    const scriptCount=await page.locator('script[src]').count();
    const primeExecuted=await page.evaluate(()=>typeof window.Prime!=='undefined');
    const styles=await page.evaluate(()=>Array.from(document.styleSheets).filter(s=>s.href).length);
    console.log(JSON.stringify({scope:'GENERIC_UNAUTHENTICATED_RENDER_ONLY',candidate:headers,headerReadback,path,status:response.status(),scriptReferences:scriptCount,loadedStylesheets:styles,primeExecuted,assets,failures}));
    if(Object.entries(headers).some(([name,value])=>headerReadback[name]!==value)||response.status()!==200||failures.length||!primeExecuted||styles<2||assets.some(a=>a.status>=400))throw new Error('GENERIC_HEADER_COMPATIBILITY_FAILED');
    await page.close();
   }
  } finally {await context.close();server.closeAllConnections();await new Promise(resolve=>server.close(resolve));}
 }
} finally {await browser.close();}

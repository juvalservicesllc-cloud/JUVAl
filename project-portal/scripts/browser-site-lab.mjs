// Isolated cookie-semantics lab: all requests fulfilled in memory, no provider
// access, existing profile, real credentials or cookie values in output.
import assert from 'node:assert/strict';
import {chromium} from '@playwright/test';
const browser=await chromium.launch({headless:true,...(process.env.JUVAL_LAB_CHROMIUM?{executablePath:process.env.JUVAL_LAB_CHROMIUM}:{})});
try {
 const context=await browser.newContext({serviceWorkers:'block'});
 await context.route('**/*',async route=>{
  const request=route.request(),url=new URL(request.url());
  if(!['app.juval.test','api.juval.test','outside.other.test'].includes(url.hostname))return route.abort();
  const headers=await request.allHeaders();
  if(url.pathname==='/seed')return route.fulfill({contentType:'text/html',headers:{'Set-Cookie':'lab_session=synthetic; Secure; HttpOnly; SameSite=Lax; Path=/'},body:'Lab'});
  if(url.pathname==='/probe')return route.fulfill({contentType:'application/json',headers:{'Access-Control-Allow-Origin':headers.origin??'null','Access-Control-Allow-Credentials':'true'},body:JSON.stringify({sent:!!headers.cookie})});
  return route.fulfill({contentType:'text/html',body:'<main>Isolated browser semantics</main>'});
 });
 const page=await context.newPage();
 await page.goto('https://api.juval.test/seed');
 assert.equal(await page.evaluate(()=>document.cookie.length),0,'HttpOnly on issuing host');
 await page.goto('https://app.juval.test/');
 assert.equal(await page.evaluate(async()=>await(await fetch('/probe')).json().then(x=>x.sent)),false,'host-only cookie not sent to sibling');
 const probe=()=>page.evaluate(async()=>await(await fetch('https://api.juval.test/probe',{credentials:'include'})).json());
 assert.equal((await probe()).sent,true,'same-site credentialed fetch');
 assert.equal(await page.evaluate(()=>document.cookie.length),0,'host-only HttpOnly cookie not exposed on app');
 await page.goto('https://outside.other.test/');
 assert.equal((await probe()).sent,false,'cross-site fetch excludes Lax cookie');
 await page.goto('https://api.juval.test/probe');
 assert.equal(JSON.parse(await page.locator('body').innerText()).sent,true,'top-level safe navigation includes Lax cookie');
 console.log('BROWSER_SEMANTICS_LAB_PASS: same-site fetch, cross-site negative, host-only/HttpOnly visibility, top-level GET');
}finally{await browser.close();}

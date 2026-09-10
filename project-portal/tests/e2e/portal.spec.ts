import {test,expect} from '@playwright/test';
test('command center, explanation, roadmap, search and theme',async({page})=>{
 await page.goto('/');await expect(page.getByRole('heading',{name:'Command Center',exact:true})).toBeVisible();
 await page.locator('.hero-number').click();await expect(page.getByRole('dialog')).toBeVisible();await expect(page.getByText(/weighted points/)).toBeVisible();await page.getByRole('button',{name:'Close dialog'}).click();
 await page.getByRole('navigation').getByRole('button',{name:'Roadmap'}).click();await page.getByLabel('Status filter').selectOption('BLOCKED');await expect(page.locator('.roadmap-line')).not.toHaveCount(0);await expect(page.locator('.roadmap-line .badge').first()).toHaveText('BLOCKED');
 await page.getByRole('button',{name:'Board',exact:true}).click();await expect(page.locator('.board-card')).not.toHaveCount(0);
 await page.keyboard.press('Control+k');await page.getByLabel('Global search').fill('ADR-036');await page.getByRole('dialog').getByRole('button').filter({hasText:'ADR-036'}).first().click();await expect(page.getByRole('dialog')).toContainText('ADR-036');await page.keyboard.press('Escape');
 await page.getByLabel('Toggle theme',{exact:true}).click();await expect(page.locator('html')).toHaveAttribute('data-theme','dark');await page.reload();await expect(page.locator('html')).toHaveAttribute('data-theme','dark');
});
test('all navigation destinations render',async({page})=>{await page.goto('/');const labels=await page.getByRole('navigation').getByRole('button').allTextContents();for(const label of labels){await page.getByRole('navigation').getByRole('button',{name:label.trim(),exact:true}).click();await expect(page.locator('main h1')).not.toBeEmpty();await expect(page.locator('main')).not.toContainText('undefined');}});
for(const width of [1440,1280,768,390])test(`responsive visual capture ${width}`,async({page})=>{await page.setViewportSize({width,height:1000});await page.goto('/');await expect(page.locator('.hero')).toBeVisible();await expect.poll(()=>page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);await page.screenshot({path:`test-results/command-${width}-light.png`,fullPage:true,animations:'disabled'});await page.getByLabel('Toggle theme',{exact:true}).click();await page.screenshot({path:`test-results/command-${width}-dark.png`,fullPage:true,animations:'disabled'});if(width<720){await page.getByLabel('Open navigation').click();await expect(page.getByRole('navigation')).toBeInViewport();await page.getByRole('navigation').getByRole('button',{name:'Roadmap'}).click();await expect(page.locator('main h1')).toHaveText('Roadmap');}});
test('sync and failure preserve snapshot',async({page})=>{await page.goto('/');await page.route('**/api/sync',route=>route.fulfill({status:503,contentType:'application/json',body:'{}'}));await page.getByRole('button',{name:'Sync repository'}).first().click();await expect(page.getByRole('alert')).toContainText('last successful snapshot');await expect(page.locator('.hero')).toBeVisible();});
test('offline snapshot and invalid payload are handled gracefully',async({page})=>{await page.route('**/api/state',route=>route.fulfill({contentType:'application/json',body:'{"schemaVersion":99}'}));await page.goto('/');await expect(page.getByText(/OFFLINE SNAPSHOT ·/)).toBeVisible();await expect(page.locator('.hero')).toBeVisible();});
test('ADR deep link, keyboard close and missing search state',async({page})=>{await page.goto('/?adr=ADR-036#ADRs');await expect(page.getByRole('dialog')).toContainText('ADR-036');await page.keyboard.press('Escape');await expect(page.getByRole('dialog')).not.toBeVisible();await expect(page.locator('main h1')).toHaveText('ADRs');});
test('same-origin sync works and private filesystem routes are denied',async({request})=>{test.setTimeout(90000);const denied=await request.post('/api/sync',{headers:{Origin:'https://untrusted.example'}});expect(denied.status()).toBe(403);for(const path of ['/data/generated/backend-junit.xml','/.verification/repository/pyproject.toml','/%64ata/generated/missing.json','/.env.local','/missing.pem']){const response=await request.get(path);expect(response.status()).toBe(403);}const result=await request.post('/api/sync',{headers:{Origin:'http://127.0.0.1:4317'}});expect(result.ok()).toBeTruthy();const s=await result.json();expect(s.sync.status).toBe('SUCCESS');expect(s.adrs.length).toBeGreaterThanOrEqual(36);});
test('roadmap source/date/risk filters and assurance views',async({page})=>{await page.setViewportSize({width:1440,height:1000});await page.goto('/#Roadmap');await page.getByLabel('Risk filter').selectOption('High');await expect(page.locator('.roadmap-line')).not.toHaveCount(0);await page.getByLabel('Source changed since').fill('2099-01-01');await expect(page.locator('.roadmap-line')).toHaveCount(0);await page.getByRole('button',{name:'Reset',exact:true}).click();await page.screenshot({path:'test-results/roadmap.png',fullPage:true,animations:'disabled'});await page.getByRole('navigation').getByRole('button',{name:'Amazon Readiness'}).click();await page.locator('.control-detail summary').first().click();await expect(page.locator('.control-columns').first()).toBeVisible();await page.screenshot({path:'test-results/amazon.png',fullPage:true,animations:'disabled'});await page.getByRole('navigation').getByRole('button',{name:'Architecture',exact:false}).click();await expect(page.locator('.architecture-node')).not.toHaveCount(0);await page.screenshot({path:'test-results/architecture.png',fullPage:true,animations:'disabled'});});

test('English and Spanish preserve route, filter values, evidence and language preference',async({page})=>{
 await page.goto('/#Roadmap');
 await page.getByLabel('Language / Idioma').selectOption('es');
 await expect(page.locator('html')).toHaveAttribute('lang','es');
 await expect(page.locator('main h1')).toHaveText('Hoja de ruta');
 await page.getByLabel('Filtro de estado').selectOption('BLOCKED');
 await expect(page.locator('.roadmap-line')).not.toHaveCount(0);
 await expect(page.locator('.roadmap-line .badge').first()).toHaveText('BLOQUEADO');
 await page.getByLabel('Buscar en esta vista').fill('Aprobación externa');
 await expect(page.locator('.roadmap-line')).toHaveCount(1);
 await page.locator('.roadmap-line').click();
 await expect(page.getByRole('dialog')).toContainText('Aprobación externa de Amazon');
 const evidence=await page.getByRole('dialog').locator('pre').first().textContent();
 await page.getByLabel('Cerrar diálogo').click();
 await page.getByLabel('Language / Idioma').selectOption('en');
 await expect(page).toHaveURL(/#Roadmap$/);
 await expect(page.getByLabel('Status filter')).toHaveValue('BLOCKED');
 await page.getByLabel('Search current view').fill('Amazon external approval');
 await page.locator('.roadmap-line').click();
 await expect(page.getByRole('dialog').locator('pre').first()).toHaveText(evidence!);
 await page.getByLabel('Close dialog').click();
 await page.getByLabel('Language / Idioma').selectOption('es');
 await page.reload();
 await expect(page.getByLabel('Language / Idioma')).toHaveValue('es');
 await expect(page.locator('main h1')).toHaveText('Hoja de ruta');
 const nav=page.getByRole('navigation').getByRole('button');
 for(let i=0;i<17;i++){await nav.nth(i).click();await expect(page.locator('main h1')).toHaveText((await nav.nth(i).innerText()).replace(/^\S+\s*/, '').replace(/\s*\d+$/,'').trim());}
 await page.goto('/#Roadmap');await page.setViewportSize({width:1440,height:1000});await page.screenshot({path:'test-results/spanish-roadmap.png',fullPage:true});
 await page.emulateMedia({reducedMotion:'reduce'});await page.setViewportSize({width:390,height:844});await page.screenshot({path:'test-results/spanish-mobile.png',fullPage:true,animations:'disabled'});
 await page.getByLabel('Cambiar tema').click();await page.screenshot({path:'test-results/spanish-mobile-dark.png',fullPage:true,animations:'disabled'});
 expect(await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth)).toBeTruthy();
});
test('hosted build refreshes its published snapshot without calling local sync',async({page})=>{
 const {readFile}=await import('node:fs/promises');
 const requests:string[]=[];
 await page.route('https://portal.example/**',async route=>{
  const path=new URL(route.request().url()).pathname;requests.push(path);
  const file=path==='/'?'index.html':path.slice(1);
  if(!['index.html','project-state.json'].includes(file)&&!/^assets\/[\w.-]+$/.test(file)){await route.abort();return;}
  await route.fulfill({body:await readFile(`dist/${file}`),contentType:file.endsWith('.js')?'application/javascript':file.endsWith('.css')?'text/css':file.endsWith('.json')?'application/json':'text/html'});
 });
 await page.goto('https://portal.example/');
 await expect(page.locator('.hero')).toBeVisible();
 await expect(page.getByText('Published snapshot',{exact:true})).toBeVisible();
 await page.getByRole('button',{name:'↻ Refresh snapshot',exact:true}).click();
 await expect(page.getByRole('status')).toContainText('Repository snapshot refreshed.');
 expect(requests.filter(p=>p==='/project-state.json').length).toBe(2);
 expect(requests.some(p=>p.startsWith('/api/'))).toBe(false);
});


test('existing synthetic private artifact is denied before Vite fallback',async({request})=>{
 const {mkdirSync,mkdtempSync,writeFileSync,rmSync}=await import('node:fs');
 const {resolve}=await import('node:path');
 mkdirSync('.verification',{recursive:true});
 const directory=mkdtempSync(resolve('.verification','deny-probe-'));
 try{
  writeFileSync(resolve(directory,'synthetic.txt'),'SYNTHETIC_PRIVATE_SENTINEL');
  for(const path of ['/'+directory.split('/').slice(-2).join('/')+'/synthetic.txt','/@fs'+directory+'/synthetic.txt']){
   const response=await request.get(path);
   expect(response.status()).toBe(403);
   expect(await response.text()).not.toContain('SYNTHETIC_PRIVATE_SENTINEL');
  }
 }finally{rmSync(directory,{recursive:true,force:true});}
});

import {createServer} from 'vite';
import {readFileSync} from 'node:fs';
import {output,portal} from './sync.mjs';
import {refresh} from './refresh.mjs';
const port=Number(process.env.PORTAL_PORT||4317);
let syncing=false;
const server=await createServer({root:portal,server:{host:'127.0.0.1',port,strictPort:true},plugins:[{name:'repository-snapshot',configureServer(vite){vite.middlewares.use('/api/state',(req,res)=>{res.setHeader('Content-Type','application/json');res.setHeader('Cache-Control','no-store');try{res.end(readFileSync(output));}catch{res.statusCode=503;res.end(JSON.stringify({error:'No snapshot available. Sync the repository to begin.'}));}});vite.middlewares.use('/api/sync',async(req,res)=>{
  res.setHeader('Content-Type','application/json');res.setHeader('Cache-Control','no-store');
  if(req.method!=='POST'){res.statusCode=405;res.end('{"error":"POST required"}');return;}
  if(req.headers.origin!==`http://127.0.0.1:${port}` && req.headers.origin!==`http://localhost:${port}`){res.statusCode=403;res.end('{"error":"Same-origin local access required"}');return;}
  if(syncing){res.statusCode=409;res.end('{"error":"Sync already in progress"}');return;}
  syncing=true;try{res.end(JSON.stringify(await refresh()));}catch{res.statusCode=503;res.end('{"error":"Sync failed. Last successful snapshot remains available."}');}finally{syncing=false;}
});}}]});
await server.listen();server.printUrls();

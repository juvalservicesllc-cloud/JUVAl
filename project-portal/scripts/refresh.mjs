import {execFile} from 'node:child_process';
import {promisify} from 'node:util';
import {readFileSync,writeFileSync,renameSync} from 'node:fs';
import {root,output,generate} from './sync.mjs';
import {githubSnapshot} from './github.mjs';
export async function refresh(){
 const at=new Date().toISOString();
 try{
  await promisify(execFile)('git',['fetch','origin','master'],{cwd:root,timeout:30000,windowsHide:true});
  await githubSnapshot();
  return generate();
 }catch{
  try{const previous=JSON.parse(readFileSync(output,'utf8'));previous.sync.lastAttempted=at;previous.sync.status='FAILED';previous.sync.errors=['Remote refresh failed. Last successful snapshot retained.'];previous.sync.history=[{at,status:'FAILED',head:previous.git.head},...previous.sync.history].slice(0,20);writeFileSync(output+'.tmp',JSON.stringify(previous,null,2));renameSync(output+'.tmp',output);}catch{/* No last snapshot; API returns the explicit empty state. */}
  throw new Error('Remote refresh failed. Last successful snapshot retained.');
 }
}
if(process.argv[1]?.endsWith('refresh.mjs'))refresh().then(s=>console.log(`Refreshed ${s.git.head.slice(0,7)}; ${s.adrs.length} ADRs`)).catch(()=>{console.error('Refresh failed; last snapshot retained.');process.exitCode=1;});

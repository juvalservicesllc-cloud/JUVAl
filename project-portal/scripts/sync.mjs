import {execFileSync} from 'node:child_process';
import {readFileSync,writeFileSync,renameSync,mkdirSync} from 'node:fs';
import {resolve,dirname} from 'node:path';
import {fileURLToPath} from 'node:url';
import {normalizeStatus,parseAdr,section,sanitize,validateState} from './model.mjs';
export const portal = resolve(dirname(fileURLToPath(import.meta.url)),'..');
export const root = process.env.JUVAL_EVIDENCE_ROOT ?? resolve(portal,'..');
export const output = resolve(portal,'data/generated/project-state.json');
const git = (...args) => execFileSync('git',args,{cwd:root,encoding:'utf8',timeout:15000,windowsHide:true,stdio:['ignore','pipe','pipe']}).trim();
export function generate() {
  const now = new Date().toISOString();
  const config = JSON.parse(readFileSync(resolve(portal,'data/project-config.json'),'utf8'));
  const refName = process.env.JUVAL_EVIDENCE_REF ?? config.ref ?? 'origin/master';
  const ref = git('rev-parse',refName);
  const tracked = git('ls-tree','-r','--name-only',ref).split('\n');
  const allowed = tracked.filter(p=> /^(docs\/.*\.md|README\.md|src\/juval\/.*\.(py|md)|tests\/.*\.py|deploy\/.*\.(md|sh|conf)|supabase\/migrations\/.*\.sql|frontend-next\/src\/.*\.(tsx|ts)|\.github\/workflows\/.*\.ya?ml)$/.test(p) && !/(^|\/)\.env|Secret Key/i.test(p));
  const warnings = ['README, AGENTS and PROJECT_PLAN contain historical statements. Evidence dates and source excerpts take precedence.','Progress is a curated acceptance-criteria model, not an independently approved business completion estimate.'];
  const documents = new Map();
  for(const p of allowed) {
    try { const content=git('show',`${ref}:${p}`); if(content.length>700000)continue; documents.set(p,sanitize(content)); } catch {warnings.push(`Unable to read allowlisted source: ${p}`);}
  }
  const head = git('rev-parse',ref);
  const localHead = git('rev-parse','HEAD');
  if(localHead!==head)warnings.push(`Local checkout ${localHead.slice(0,7)} differs from indexed ${refName} ${head.slice(0,7)}. Test results must identify which revision was executed.`);
  const commits = git('log',ref,'-80','--format=%H%x09%cs%x09%an%x09%s').split('\n').filter(Boolean).map(line=>{const [hash,date,author,...title]=line.split('\t');return {hash,date,author:sanitize(author),title:sanitize(title.join(' '))};});
  const adrs = [...documents].filter(([p])=>p.startsWith('docs/adr/')).map(([p,t])=>parseAdr(t,p));
  const sourceDates=new Map();
  const criteria = config.criteria.map(c=>{
    const source = documents.get(c.source);
    const fragment = source && c.section ? section(source,c.section) : null;
    let excerpt = fragment?.text ?? source?.slice(0,1800) ?? 'Source missing from safe allowlist.';
    let status='NOT_STARTED', verificationLevel='NOT_VERIFIED';
    if(source){
      if(c.rule === 'code'){status='COMPLETE';verificationLevel='VERIFIED_CODE';excerpt='Source file exists and was read at this snapshot. This confirms implementation presence, not correctness or runtime behavior.';}
      if(c.rule === 'gate' && fragment){ const raw=fragment.text.match(/Estado del gate:\s*\**([A-Z_]+)/)?.[1];status=raw==='PASS'?'COMPLETE':'PARTIAL';verificationLevel=raw==='PASS'?'VERIFIED_TEST':'NOT_VERIFIED'; }
      if(c.rule==='plan' && fragment) status=normalizeStatus(fragment.text.match(/Estado:\s*([^\n]+)/)?.[1]);
      if(c.rule==='rf') { const matches=[...source.matchAll(new RegExp(`^${c.id.toUpperCase()}\\s+([A-Z_]+).*`,'gm'))]; if(matches.length){excerpt=matches.at(-1)[0];status=normalizeStatus(matches.at(-1)[1]);} }
      if(c.rule==='identity'){const matches=[...source.matchAll(/^IDP_IMPLEMENTATION\s*=\s*([^\n]+)/gm)];excerpt=matches.at(-1)?.[0]??'No runtime evidence';status=normalizeStatus(matches.at(-1)?.[1]);}
      if(c.rule==='control6'){const matches=[...source.matchAll(/^CONTROL_6(?:_AMAZON)?\s*=\s*([^\n]+)/gm)];excerpt=matches.at(-1)?.[0]??'No Control 6 evidence';status=matches.length?normalizeStatus(matches.at(-1)[1]):'NOT_STARTED';}
      if(c.rule==='documented' && fragment){excerpt=fragment.text;if(!c.evidenceMatch||fragment.text.includes(c.evidenceMatch)){status=c.status;verificationLevel=c.verificationLevel;}else warnings.push(`Expected documented evidence missing: ${c.id}`);}
      if(c.rule==='manual'){status=c.status;verificationLevel='NOT_VERIFIED';excerpt=c.notes;}
    } else warnings.push(`Missing criterion source: ${c.source}`);
    if(c.section && !fragment) warnings.push(`Missing section ${c.section}: ${c.source}`);
    const line=fragment?.line ?? (source?.indexOf(excerpt)>=0 ? source.slice(0,source.indexOf(excerpt)).split('\n').length : 1);
    if(!sourceDates.has(c.source))sourceDates.set(c.source,source?git('log','-1','--format=%cs',head,'--',c.source):null);
    const evidenceSource=c.rule==='manual'||!source?'HISTORICAL_CONTEXT_ONLY':'REPOSITORY_VERIFIED';
    return {...c,evidenceSource,runtimeVerification:'EXTERNAL_RUNTIME_EVIDENCE_REQUIRED',status,verificationLevel,description:c.notes??c.title,sourceReference:`${c.source}#L${line}`,evidence:excerpt.slice(0,4000),lastUpdated:now,sourceUpdatedAt:sourceDates.get(c.source),confidence:c.rule==='manual'?'manual conservative assessment':c.rule==='code'?'high: source presence only':'documented claim; not re-executed',blockedBy:[],notes:c.notes??'',commit:head,parser:c.rule,relatedAdrs:[...new Set((source?.match(/ADR-\d+/g)??[]))].slice(0,12)};
  });
  for(const c of criteria)c.blockedBy=c.dependsOn.filter(id=>criteria.find(x=>x.id===id)?.status!=='COMPLETE');
  let previous=null;try{previous=JSON.parse(readFileSync(output,'utf8'));}catch{/* First snapshot. */}
  let divergence=null;try{divergence=git('rev-list','--left-right','--count','HEAD...@{upstream}').split(/\s+/).map(Number);}catch{warnings.push('No upstream reference available.');}
  const files=[...documents].map(([path,content])=>({path,title:path.split('/').at(-1),content: path.startsWith('docs/')||path==='README.md'?content:'Source indexed. Open the repository link for code; raw source is not exported.',kind:path.startsWith('docs/adr')?'ADR':path.startsWith('tests/')?'Test':path.split('/')[0]}));
  const sessionSource='src/juval/infrastructure/persistence/postgres_session_store.py';
  const sessionCode=documents.get(sessionSource)??'';
  const debt=[];
  if(sessionCode.includes('return _require_driver().connect'))debt.push({id:'PORTAL-DEBT-01',title:'One PostgreSQL connection per session operation',category:'Performance',severity:'Unmeasured',effort:'Pending estimate',impact:'Connection setup overhead under concurrent load',status:'PENDING_REVIEW',source:sessionSource,evidence:'return _require_driver().connect(self._dsn)',nextAction:'Measure connection setup overhead before considering pooling.'});
  if(sessionCode.includes('update identity_sessions set last_seen_at'))debt.push({id:'PORTAL-DEBT-02',title:'last_seen written during authenticated reads',category:'Performance',severity:'Unmeasured',effort:'Pending estimate',impact:'Write amplification with read traffic',status:'PENDING_REVIEW',source:sessionSource,evidence:'update identity_sessions set last_seen_at = %s where session_digest = %s',nextAction:'Measure write volume before introducing a bounded touch interval.'});
  for(const c of criteria){c.owner='Unassigned';c.risk=c.status==='BLOCKED'?'High':c.status==='COMPLETE'?'Low':'Medium';c.nextAction=c.notes||`Supply dated evidence to close: ${c.title}`;c.observedCommitDate=commits[0]?.date??null;}
  let testRun=null;try{testRun=JSON.parse(readFileSync(resolve(portal,'data/generated/test-run.json'),'utf8'));}catch{/* Tests unavailable is explicit. */}
  let github={status:'NOT_CONNECTED',checkedAt:null,branches:[],pulls:[],issues:[],runs:[],releases:[],alerts:[],error:'No remote metadata has been fetched. Local Git remains available.'};
  try{github=JSON.parse(readFileSync(resolve(portal,'data/generated/github.json'),'utf8'));}catch{/* Offline is supported. */}
  const state=validateState({schemaVersion:1,model:config.scope,phases:config.phases,criteria,adrs,files,commits,tests:{discoveredFiles:tracked.filter(p=>/^tests\/.*test_.*\.py$/.test(p)),run:testRun,coverage:'NOT_MEASURED',flaky:'NOT_MEASURED'},git:{branch:refName,head,localHead,divergence,dirty:!!git('status','--porcelain','--untracked-files=no'),untrackedPresent:!!git('ls-files','--others','--exclude-standard'),repository:config.repository,tags:git('tag','--list').split('\n').filter(Boolean)},github,sync:{mode:process.env.VERCEL?'AUTOMATIC GIT DEPLOYMENT':'MANUAL REMOTE-REF SNAPSHOT',lastAttempted:now,lastSuccessful:now,status:'SUCCESS',filesScanned:files.length,commitsProcessed:commits.length,warnings,errors:[],history:[{at:now,status:'SUCCESS',head},...(previous?.sync?.history??[])].slice(0,20)}});
  state.debt=debt;
  // Recorded observations remain separate from a current Linux measurement.
  state.evidenceSources={repository:{kind:'Git Repository Evidence',ref:refName,commit:head,localHead,status:'REPOSITORY_VERIFIED'},linux:{kind:'Linux Runtime Evidence',status:'EXTERNAL_RUNTIME_EVIDENCE_REQUIRED',observedAt:null,observations:[]},historical:{kind:'Historical Context',status:'HISTORICAL_CONTEXT_ONLY'}};
  const evidencePaths=['docs/compliance/SP_API_REGISTRATION_REMEDIATION.md','docs/compliance/IDENTITY_DEPLOYMENT_FUSIONAUTH.md','docs/PROJECT_STATUS.md'];
  state.recordedObservations=evidencePaths.flatMap(path=>(documents.get(path)??'').split('\n').flatMap((line,index)=> /IDP_RUNTIME|BROWSER_AUTH|SESSION_STORE|RF03_BEHAVIORAL|CONTROL_6_AMAZON|BEHAVIORALLY_VERIFIED|MainPID=|fusionauth-app.*service|AMAZON_COMPLIANCE_READINESS/.test(line)?[{source:path,sourceReference:`${path}#L${index+1}`,commit:head,evidence:line.trim(),evidenceSource:'REPOSITORY_VERIFIED',scope:'Dated repository record; later sections may supersede earlier entries. Not a current runtime probe.',runtimeVerification:'EXTERNAL_RUNTIME_EVIDENCE_REQUIRED'}]:[]));
  mkdirSync(dirname(output),{recursive:true});writeFileSync(output+'.tmp',JSON.stringify(state,null,2));renameSync(output+'.tmp',output);return state;
}
if(process.argv[1] && resolve(process.argv[1])===fileURLToPath(import.meta.url)){try{const s=generate();console.log(`Snapshot: ${s.criteria.length} criteria, ${s.adrs.length} ADRs, ${s.files.length} files, ${s.git.head.slice(0,7)}`);}catch{console.error('Snapshot generation failed; previous snapshot retained. Check local Git and source permissions.');process.exitCode=1;}}

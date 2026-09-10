import {test} from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {progress,normalizeStatus,parseAdr,validateState,sanitize,nextActions,riskScore,section} from '../scripts/model.mjs';
const item=(status,weight=1,verificationLevel='NOT_VERIFIED')=>({id:status,status,weight,verificationLevel,dependsOn:[],phase:0});
test('weighted progress separates evidence, excludes deferred and handles empty scope',()=>{const items=[item('COMPLETE',3,'VERIFIED_CODE'),item('PARTIAL',2),item('BLOCKED'),item('DEFERRED',99)];assert.deepEqual(progress(items),{percent:67,earned:4,total:6,count:3});assert.equal(progress(items,'verification').percent,0);assert.equal(progress([]).percent,null);assert.equal(progress([item('COMPLETE',2,'VERIFIED_TEST')],'verification').percent,100);});
test('normalization is conservative and respects blocked precedence',()=>{assert.equal(normalizeStatus('NOT STARTED — BLOCKED'),'BLOCKED');assert.equal(normalizeStatus('PARTIALLY_IMPLEMENTED'),'PARTIAL');assert.equal(normalizeStatus('NOT_IMPLEMENTED'),'NOT_STARTED');assert.equal(normalizeStatus('unknown'),'NOT_STARTED');});
test('ADR parser handles multiline accepted status and sections',()=>{const a=parseAdr('# ADR-036 — Sessions\n**Estado: Aceptada — Opción A\ncontinued**\n**Fecha: 2026-09-10**\n## Contexto\nwhy\n## Decisión\nPostgreSQL\n## Consecuencias\nlatency','docs/adr/ADR-036.md');assert.equal(a.status,'Accepted');assert.equal(a.date,'2026-09-10');assert.match(a.decision,/PostgreSQL/);assert.equal(a.id,'ADR-036');assert.equal(parseAdr('# No metadata','x').status,'NOT_VERIFIED');});
test('section parser does not cross sibling boundaries',()=>{assert.equal(section('## Phase 1\na\n### child\nb\n## Phase 2\nc','Phase 1').text,'## Phase 1\na\n### child\nb');assert.equal(section('text','absent'),null);});
test('section identifiers do not accidentally match phase ten',()=>{assert.equal(section('## Fase 10\nwrong','Fase 1'),null);});
test('risk prioritization is deterministic with dependency impact',()=>{const a={...item('BLOCKED',3),id:'a'},b={...item('PARTIAL',2),id:'b',dependsOn:['a']};assert.equal(riskScore(a),9);assert.equal(nextActions([b,a])[0].id,'a');});
test('secrets are redacted without dropping policy documents',()=>{assert.doesNotMatch(sanitize('client_secret=abcdef\npostgresql://user:password@host/db\nghp_abcdefghijklmnopqrstuvwxyz1234'),/abcdef|user:password|ghp_/);});
test('generated snapshot has valid provenance, unique IDs and real ADR discovery',()=>{const s=JSON.parse(readFileSync(new URL('../data/generated/project-state.json',import.meta.url)));validateState(s);assert.ok(s.adrs.length>=36);assert.ok(s.criteria.every(c=>c.commit===s.git.head));assert.equal(s.criteria.find(c=>c.id==='control-6').status,'PARTIAL');assert.equal(s.criteria.find(c=>c.id==='amazon-approval').status,'BLOCKED');assert.ok(s.files.every(f=>!f.path.includes('.env')&&!f.path.includes('Secret Key')));assert.throws(()=>validateState({...s,criteria:[{...s.criteria[0],weight:-1}]}));assert.throws(()=>validateState({...s,criteria:[s.criteria[0],s.criteria[0]]}));});

test('repository records do not masquerade as current Linux evidence',()=>{const s=JSON.parse(readFileSync(new URL('../data/generated/project-state.json',import.meta.url)));assert.equal(s.evidenceSources.repository.localHead,s.git.localHead);assert.equal(s.evidenceSources.repository.commit,s.git.head);if(s.git.localHead!==s.git.head)assert.ok(s.sync.warnings.some(w=>w.includes('differs from indexed')));assert.equal(s.evidenceSources.linux.status,'EXTERNAL_RUNTIME_EVIDENCE_REQUIRED');assert.equal(s.evidenceSources.linux.observedAt,null);assert.ok(s.criteria.every(c=>c.evidenceSource==='REPOSITORY_VERIFIED'||c.evidenceSource==='HISTORICAL_CONTEXT_ONLY'));assert.ok(s.recordedObservations.some(o=>o.evidence.includes('MainPID=369334')));assert.ok(s.recordedObservations.some(o=>o.evidence.includes('BEHAVIORALLY_VERIFIED')));assert.ok(s.recordedObservations.every(o=>o.runtimeVerification==='EXTERNAL_RUNTIME_EVIDENCE_REQUIRED'));});

test('accelerator mappings keep lab remediation separate from public readiness',()=>{
 const s=JSON.parse(readFileSync(new URL('../data/generated/project-state.json',import.meta.url)));
 const n1=s.criteria.find(c=>c.id==='nginx-n1');
 if(s.files.some(f=>f.path==='docs/adr/ADR-037-nginx-generated-response-hardening.md')){
   assert.equal(n1.status,'COMPLETE');
   assert.equal(n1.verificationLevel,'LAB_BEHAVIORALLY_VERIFIED');
   assert.equal(s.criteria.find(c=>c.id==='real-login-surface').status,'BLOCKED');
   const topology=s.criteria.find(c=>c.id==='browser-site-topology');
   if(s.adrs.find(a=>a.id==='ADR-038')?.status==='Accepted')assert.equal(topology.status,'COMPLETE');
   else assert.notEqual(topology.status,'COMPLETE');
 } else {
   assert.equal(n1.verificationLevel,'NOT_VERIFIED');
   assert.notEqual(n1.status,'COMPLETE');
 }
 assert.equal(s.criteria.find(c=>c.id==='amazon-approval').status,'BLOCKED');
});


test('readiness requires closed scope-specific evidence and retains deferred blockers',async()=>{
 const {readiness}=await import('../scripts/model.mjs');
 const criteria=[{id:'lab',weight:2,status:'COMPLETE',verificationLevel:'LAB_BEHAVIORALLY_VERIFIED'},{id:'public',weight:3,status:'DEFERRED',verificationLevel:'NOT_VERIFIED'}];
 assert.equal(readiness(criteria,{ids:['lab','public'],levels:['PRODUCTION_VERIFIED']}).percent,0);
 assert.equal(readiness(criteria,{ids:['lab','public'],levels:['LAB_BEHAVIORALLY_VERIFIED']}).percent,40);
 assert.throws(()=>readiness(criteria,{ids:['missing'],levels:['PRODUCTION_VERIFIED']}));
 assert.throws(()=>readiness(criteria,{ids:['lab','lab'],levels:['PRODUCTION_VERIFIED']}));
});

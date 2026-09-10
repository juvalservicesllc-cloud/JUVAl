export const statuses = ['COMPLETE','IN_PROGRESS','PARTIAL','BLOCKED','NOT_STARTED','DEFERRED'];
export const levels = ['VERIFIED','VERIFIED_CONFIG','VERIFIED_CODE','VERIFIED_TEST','BEHAVIORALLY_VERIFIED','LAB_BEHAVIORALLY_VERIFIED','PRODUCTION_VERIFIED','INFERRED','NOT_VERIFIED','NOT_TESTED','BLOCKED'];
export function normalizeStatus(raw = '') {
  const value = raw.toUpperCase().replaceAll(' ', '_');
  if (/BLOCKED|BLOQUEAD/.test(value)) return 'BLOCKED';
  if (/NOT_IMPLEMENTED|NOT_STARTED|NOT_EXECUTED|PENDING/.test(value)) return 'NOT_STARTED';
  if (/PARTIAL|PARCIAL/.test(value)) return 'PARTIAL';
  if (/IN_PROGRESS|IMPLEMENTED/.test(value)) return 'IN_PROGRESS';
  if (/COMPLETE|^PASS$/.test(value)) return 'COMPLETE';
  if (/DEFER/.test(value)) return 'DEFERRED';
  return 'NOT_STARTED';
}
export function progress(items, dimension = 'implementation') {
  const included = items.filter(c => c.status !== 'DEFERRED');
  const total = included.reduce((n,c) => n + c.weight, 0);
  const earned = included.reduce((n,c) => n + c.weight * (dimension === 'verification' ? (['VERIFIED','VERIFIED_TEST','BEHAVIORALLY_VERIFIED','LAB_BEHAVIORALLY_VERIFIED','PRODUCTION_VERIFIED'].includes(c.verificationLevel) ? 1 : 0) : c.status === 'COMPLETE' ? 1 : ['IN_PROGRESS','PARTIAL'].includes(c.status) ? .5 : 0), 0);
  return { percent: total ? Math.round(earned / total * 100) : null, earned, total, count: included.length };
}
export function riskScore(c) { return (c.status === 'BLOCKED' ? 3 : c.status === 'COMPLETE' ? 1 : 2) * (c.weight >= 3 ? 3 : 2); }
export function nextActions(criteria) {
  return criteria.filter(c=>!['COMPLETE','DEFERRED'].includes(c.status)).map(c=>({...c,priority:riskScore(c)+criteria.filter(d=>d.dependsOn.includes(c.id)).length*2})).sort((a,b)=>b.priority-a.priority || a.phase-b.phase || a.id.localeCompare(b.id));
}
export function section(text, needle) {
  const lines = text.split(/\r?\n/);
  const exact = new RegExp(needle.replace(/[.*+?^${}()|[\]\\]/g,'\\$&')+'(?=\\s|[—–:.)-]|$)','i');
  const start = lines.findIndex(line=>/^#{1,6}\s/.test(line) && exact.test(line));
  if(start < 0) return null;
  const depth = lines[start].match(/^#+/)[0].length;
  let end = start+1;
  while(end < lines.length && !new RegExp(`^#{1,${depth}} `).test(lines[end])) end++;
  return {text:lines.slice(start,end).join('\n'),line:start+1};
}
export function parseAdr(text,path) {
  const title = text.match(/^#\s+(.+)$/m)?.[1] ?? path;
  const raw = text.match(/(?:Estado|Status)\s*:\s*([^\r\n]+)/i)?.[1]?.replaceAll('*','').trim() ?? 'NOT_VERIFIED';
  return {id:path.match(/ADR-\d+/)?.[0] ?? path,title,status:/^Aceptada|^Accepted/i.test(raw)?'Accepted':/^Propuesta|^Proposed/i.test(raw)?'Proposed':raw,date:text.match(/(?:Fecha|Date)\s*:\s*\**(\d{4}-\d{2}-\d{2})/i)?.[1]??null,source:path,context:(section(text,'Contexto')??section(text,'Context'))?.text??'',decision:(section(text,'Decisión')??section(text,'Decision'))?.text??'',consequences:(section(text,'Consecuencias')??section(text,'Consequences'))?.text??'',supersededBy:text.match(/(?:Superseded by|Sustituida por)\s*:?\s*(ADR-\d+)/i)?.[1]??null};
}
export function validateState(state) {
  if(state?.schemaVersion !== 1 || !Array.isArray(state.criteria) || !state.sync?.lastSuccessful || !Array.isArray(state.adrs) || !Array.isArray(state.files) || !Array.isArray(state.phases) || !Array.isArray(state.commits) || !state.git?.head || !state.tests) throw new Error('Invalid project-state envelope');
  const ids = new Set();
  for(const c of state.criteria){
    if(!c.id || ids.has(c.id) || !statuses.includes(c.status) || !levels.includes(c.verificationLevel) || !Number.isFinite(c.weight) || c.weight <= 0 || !c.sourceReference || !c.evidence || !c.lastUpdated) throw new Error('Invalid criterion or provenance');
    ids.add(c.id);
  }
  for(const c of state.criteria) if(c.dependsOn.some(id=>!ids.has(id))) throw new Error('Unknown dependency');
  const visiting=new Set(),done=new Set();
  const visit=id=>{if(visiting.has(id))throw new Error('Cyclic dependency');if(done.has(id))return;visiting.add(id);for(const dep of state.criteria.find(c=>c.id===id).dependsOn)visit(dep);visiting.delete(id);done.add(id);};
  for(const id of ids)visit(id);
  return state;
}
// Allowlisted input is the primary boundary; redaction is defense in depth.
export function sanitize(text) {
  return text.replace(/-----BEGIN [^-]*PRIVATE KEY-----[\s\S]*?-----END [^-]*PRIVATE KEY-----/g,'[REDACTED PRIVATE KEY]')
    .replace(/\b(?:gh[pousr]_[A-Za-z0-9_]{20,}|github_pat_[A-Za-z0-9_]+|sk-[A-Za-z0-9_-]{16,}|eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+)\b/g,'[REDACTED TOKEN]')
    .replace(/(?:postgres(?:ql)?|mysql):\/\/[^\s`"<>]+/gi,'[REDACTED CONNECTION]')
    .replace(/((?:password|client_secret|api_key|access_token|refresh_token|totp_seed|authorization|cookie)\s*[:=]\s*)[^\r\n]+/gi,'$1[REDACTED]');
}

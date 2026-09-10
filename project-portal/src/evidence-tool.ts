import {useEffect} from 'react';
import type {State} from './model';
type Context={registerTool:(tool:{name:string;description:string;inputSchema:object;annotations:object;execute:(input:unknown)=>unknown},options:{signal:AbortSignal})=>void|Promise<void>};
export function useEvidenceTool(state:State|null){
 useEffect(()=>{
  const context=(document as Document&{modelContext?:Context}).modelContext;
  if(!state||!context)return;
  const lifecycle=new AbortController();
  try{Promise.resolve(context.registerTool({name:'get_project_evidence',description:'Read a criterion and its provenance from the currently displayed repository snapshot. No refresh or repository write.',inputSchema:{type:'object',properties:{criterionId:{type:'string'}},required:['criterionId'],additionalProperties:false},annotations:{readOnlyHint:true,untrustedContentHint:true},execute(input){if(!input||typeof input!=='object'||!('criterionId' in input)||typeof input.criterionId!=='string')return {error:'criterionId must be a string'};const criterion=state.criteria.find(c=>c.id===input.criterionId);return criterion?{criterion,commit:state.git.head,snapshotAt:state.sync.lastSuccessful}:{error:'Criterion not found'};}},{signal:lifecycle.signal})).catch(()=>{/* Unsupported registry leaves the normal evidence UI available. */});}catch{/* Progressive enhancement only. */}
  return()=>lifecycle.abort();
 },[state]);
}

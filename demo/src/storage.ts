import type { DemoDecisionPolicy, DemoRecord } from "./demo-engine"
import type { SourceFile } from "./batch"
export type BatchStatus="SUCCESS"|"PARTIAL_SUCCESS"|"FAILED"
export type Run={schema:1;runId:string;createdAt:string;inputFilename:string;records:DemoRecord[];warnings:string[];decisionPolicy?:DemoDecisionPolicy;files:SourceFile[];status:BatchStatus}
const key="juval.demo.runs.v1"
// ponytail: runs saved before multi-file batches lacked `files`/`status`; default them in place instead of a versioned migration for one additive change.
const migrate=(run:Run):Run=>({...run,files:run.files??[],status:run.status??"SUCCESS"})
export function loadRuns():{runs:Run[];warning?:string}{try{const parsed=JSON.parse(localStorage.getItem(key)||"[]");if(!Array.isArray(parsed)||parsed.some(run=>run?.schema!==1||!Array.isArray(run.records)))return {runs:[],warning:"Saved demo data used an incompatible or corrupt schema and was ignored."};return {runs:parsed.map(migrate)}}catch{return {runs:[],warning:"Saved demo data was corrupt and was ignored."}}}
export function saveRuns(runs:Run[]){localStorage.setItem(key,JSON.stringify(runs))}
export function clearRuns(){localStorage.removeItem(key)}

import type { DemoRecord } from "./demo-engine"
import type { Run } from "./storage"
import { sourceIdOf } from "./favorites"
export const productPath=(runId:string,sourceFileId:string,recordRef:string)=>`/run/${encodeURIComponent(runId)}/file/${encodeURIComponent(sourceFileId)}/product/${encodeURIComponent(recordRef)}`
export const resolveProduct=(runs:Run[],runId:string,sourceFileId:string,recordRef:string):{run?:Run;record?:DemoRecord;reason?:"RUN_NOT_FOUND"|"RECORD_NOT_FOUND"}=>{const run=runs.find(item=>item.runId===runId);if(!run)return{reason:"RUN_NOT_FOUND"};const record=run.records.find(item=>item.recordRef===recordRef&&sourceIdOf(item)===sourceFileId);return record?{run,record}:{run,reason:"RECORD_NOT_FOUND"}}

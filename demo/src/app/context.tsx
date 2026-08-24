import { createContext, useContext } from "react"
import type { Analytics, DemoDecisionPolicy, DemoRecord } from "../demo-engine"
import type { Run } from "../storage"
import type { BatchResult } from "../batch"
export type DemoApp={go:(path:string)=>void;dark:boolean;setDark:(value:boolean)=>void;runs:Run[];setRuns:(runs:Run[])=>void;active:Run|null;setActive:(run:Run|null)=>void;records:DemoRecord[];analytics:Analytics;decisionPolicy:DemoDecisionPolicy;setDecisionPolicy:(policy:DemoDecisionPolicy)=>void;favorites:string[];toggleFavorite:(runId:string,sourceFileId:string,recordRef:string)=>void;notice:string;setNotice:(value:string)=>void;processBatch:(files:File[])=>Promise<BatchResult&{runId:string}>;loadIncludedFile:()=>Promise<File>;download:(records?:DemoRecord[])=>void}
export const DemoAppContext=createContext<DemoApp|null>(null)
export const useDemoApp=()=>{const value=useContext(DemoAppContext);if(!value)throw new Error("Demo app context missing");return value}

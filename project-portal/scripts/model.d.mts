import type {Criterion} from '../src/model';
export function progress(items:Criterion[],dimension?:string):{percent:number|null;earned:number;total:number;count:number};
export function riskScore(c:Criterion):number;
export function nextActions(items:Criterion[]):(Criterion&{priority:number})[];
export function validateState(state:unknown):import('../src/model').State;

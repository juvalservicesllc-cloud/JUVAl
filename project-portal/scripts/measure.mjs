import {readFileSync} from 'node:fs';
import {progress, readiness, validateState} from './model.mjs';
const config=JSON.parse(readFileSync(new URL('../data/project-config.json',import.meta.url)));
const state=validateState(JSON.parse(readFileSync(new URL('../data/generated/project-state.json',import.meta.url))));
const result={modelVersion:config.modelVersion,commit:state.git.head,scope:'Curated repository evidence, not measured production coverage or Amazon approval',implementation:progress(state.criteria),verification:progress(state.criteria,'verification')};
for(const dimension of ['production_readiness','security_readiness','amazon_readiness'])result[dimension]=readiness(state.criteria,config.measurements[dimension]);
console.log(JSON.stringify(result,null,2));

import {useSyncExternalStore} from 'react';
import es from './es.json';
export type Language='en'|'es';
const catalog:Record<string,string>=es;
const lowercase=Object.fromEntries(Object.entries(catalog).map(([k,v])=>[k.toLowerCase(),v]));
function readLanguage():Language {try{return localStorage.getItem('portal-language')==='es'?'es':'en';}catch{return 'en';}}
let language=readLanguage();
const listeners=new Set<()=>void>();
export function setLanguage(value:Language){language=value;try{localStorage.setItem('portal-language',value);}catch{/* Session preference still works. */}document.documentElement.lang=value;document.title=value==='es'?'JUVAl · Inteligencia del proyecto':'JUVAl · Project Intelligence';listeners.forEach(fn=>fn());}
const subscribe=(fn:()=>void)=>{listeners.add(fn);return()=>{listeners.delete(fn);};};
export function useLanguage(){const value=useSyncExternalStore(subscribe,()=>language);return [value,setLanguage] as const;}
// Translate presentation strings only; IDs, route names and evidence stay unchanged.
export function t<T>(value:T):T {
 if(language==='en'||typeof value!=='string')return value;
 const key=value.trim();
 const translation=catalog[key]??catalog[key.replaceAll('_',' ')]??lowercase[key.replaceAll('_',' ').toLowerCase()];
 if(translation)return value.replace(key,translation) as T;
 const phase=key.match(/^PHASE (\d+)$/);if(phase)return `FASE ${phase[1]}` as T;
 const run=key.match(/^Run (.+); commit (.+)$/);if(run)return `Ejecución ${run[1]}; commit ${run[2]}` as T;
 const days=key.match(/^(\d+) days$/);if(days)return `${days[1]} días` as T;
 return value;
}
export function matches(text:string,query:string){return `${text} ${t(text)}`.toLocaleLowerCase(language).includes(query.toLocaleLowerCase(language));}

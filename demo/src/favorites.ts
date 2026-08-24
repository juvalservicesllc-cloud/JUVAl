import type { DemoRecord } from "./demo-engine"
export const sourceIdOf=(record:Pick<DemoRecord,"sourceFileId">)=>record.sourceFileId??"legacy"
export const favoriteKey=(runId:string,sourceFileId:string,recordRef:string)=>`${runId}:${sourceFileId}:${recordRef}`
const key="juval.demo.favorites.v2"
export const loadFavorites=()=>{try{const value=JSON.parse(localStorage.getItem(key)||"[]");return Array.isArray(value)&&value.every(x=>typeof x==="string")?value:[]}catch{return[]}}
export const saveFavorites=(favorites:string[])=>localStorage.setItem(key,JSON.stringify(favorites))

export const fmt=(n:number|null,suffix="")=>n===null?"—":`${suffix}${n.toFixed(2)}`
export const Badge=({children}:{children:string})=>{const icon=children==="BUY"?"●":children==="REVIEW"?"▲":children==="PASS"?"■":"";return <em className={`badge ${children}`}>{icon&&`${icon} `}{children}</em>}

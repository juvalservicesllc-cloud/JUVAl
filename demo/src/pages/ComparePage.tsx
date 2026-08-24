import{useDemoApp}from"../app/context";import{findExactMatches}from"../matching";import{sourceIdOf}from"../favorites";import{productPath}from"../product-route";import{Badge,fmt}from"./shared";

const metrics:{label:string;value:(r:ReturnType<typeof useDemoApp>["records"][number])=>number|null;fmt:(n:number)=>string;lowerIsBetter?:boolean}[]=[
  {label:"Supplier cost",value:r=>r.cost,fmt:n=>`$${n.toFixed(2)}`,lowerIsBetter:true},
  {label:"Selling price",value:r=>r.selling,fmt:n=>`$${n.toFixed(2)}`},
  {label:"Profit",value:r=>r.profit,fmt:n=>`$${n.toFixed(2)}`},
  {label:"ROI",value:r=>r.roi,fmt:n=>`${(n*100).toFixed(1)}%`},
  {label:"Margin",value:r=>r.margin,fmt:n=>`${(n*100).toFixed(1)}%`},
]

export function ComparePage(){
  const{active,records,go}=useDemoApp()
  if(!active)return <section className="panel"><h1>Compare matched products</h1><p>No active batch run.</p></section>
  const groups=findExactMatches(records)
  return <section className="panel">
    <h1>Compare matched products</h1>
    <p>Exact-identifier matches only (shared supplier product URL across source files). No fuzzy matching is performed; arithmetic highlights are informational only, never a claim of "better" where data is missing.</p>
    {groups.length===0&&<p>No exact cross-file matches found in this batch.</p>}
    {groups.map(group=>{
      const best=Object.fromEntries(metrics.map(m=>{const values=group.records.map(m.value).filter((v):v is number=>v!==null);if(values.length<2)return[m.label,null];return[m.label,m.lowerIsBetter?Math.min(...values):Math.max(...values)]}))
      return <div className="table" key={group.identifier} style={{marginBottom:18}}>
        <table><thead><tr><th>Field</th>{group.records.map(r=><th key={sourceIdOf(r)+r.recordRef}>{r.sourceFilename}</th>)}</tr></thead><tbody>
          <tr><td>Product</td>{group.records.map(r=><td key={sourceIdOf(r)+r.recordRef}><a href={productPath(active.runId,sourceIdOf(r),r.recordRef)}>{r.title}</a></td>)}</tr>
          {metrics.map(m=><tr key={m.label}><td>{m.label}</td>{group.records.map(r=>{const v=m.value(r);const isBest=v!==null&&best[m.label]!==null&&v===best[m.label];return <td key={sourceIdOf(r)+r.recordRef} style={isBest?{fontWeight:800,color:"var(--success)"}:undefined}>{v===null?"—":m.fmt(v)}</td>})}</tr>)}
          <tr><td>Decision</td>{group.records.map(r=><td key={sourceIdOf(r)+r.recordRef}><Badge>{r.decision}</Badge></td>)}</tr>
          <tr><td>Hazmat</td>{group.records.map(r=><td key={sourceIdOf(r)+r.recordRef}>{r.hazmat}</td>)}</tr>
          <tr><td>Bulky</td>{group.records.map(r=><td key={sourceIdOf(r)+r.recordRef}>{r.bulky}</td>)}</tr>
          <tr><td>Amazon provenance</td>{group.records.map(r=><td key={sourceIdOf(r)+r.recordRef}>{r.match}</td>)}</tr>
          <tr><td>Issues</td>{group.records.map(r=><td key={sourceIdOf(r)+r.recordRef}>{r.issues.join(", ")||fmt(null)}</td>)}</tr>
        </tbody></table>
      </div>
    })}
    <button onClick={()=>go("/catalog")}>Back to Catalog</button>
  </section>
}

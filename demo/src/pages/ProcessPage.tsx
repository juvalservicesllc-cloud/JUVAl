import{useDemoApp}from"../app/context";import{Badge}from"./shared";
const stages=["Import","Validate","Normalize","Supplier Mapping","Amazon Demo Match","Weight Demo Enrichment","Hazmat Demo Enrichment","Bulky Demo Enrichment","Profitability","Decision","Data Quality","Complete"]
export function ProcessPage(){
  const{active,records,go}=useDemoApp()
  const files=active?.files??[]
  const complete=files.filter(f=>f.status==="VALID").length
  return <section className="panel">
    <h1>Demo pipeline</h1>
    <p>LOCAL DEMO RUN · {active?.inputFilename??"No processed batch"} · {records.length} records</p>
    {files.length>0&&<><h2>Batch: Normalize — {complete} / {files.length} files</h2>
      <div className="table"><table><thead><tr><th>File</th><th>Status</th><th>Rows</th><th>Notes</th></tr></thead><tbody>
        {files.map(f=><tr key={f.sourceFileId}><td>{f.filename}</td><td><Badge>{f.status==="VALID"?"Complete":[...f.warnings].length?"Warning":"Failed"}</Badge></td><td>{f.rowsProcessed}</td><td>{[...f.warnings,...f.errors].join(" · ")||"—"}</td></tr>)}
      </tbody></table></div></>}
    <h2>Common stages</h2>
    {stages.map((s,i)=><p key={s}><Badge>{records.length?"COMPLETE":"WAITING"}</Badge> {i+1}. {s}</p>)}
    <button onClick={()=>go("/catalog")}>Open catalog</button>
  </section>
}

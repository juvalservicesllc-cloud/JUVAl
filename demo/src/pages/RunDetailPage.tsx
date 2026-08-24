import{useDemoApp}from"../app/context";import{analytics}from"../engine";import{Badge,fmt}from"./shared";
export function RunDetailPage({runId}:{runId:string}){
  const{runs,setActive,go}=useDemoApp(),run=runs.find(x=>x.runId===runId)
  if(!run)return <section className="panel"><h1>Run summary</h1><p>Run not found.</p></section>
  const combined=analytics(run.records)
  return <section className="panel">
    <h1>Batch run summary</h1>
    <p>LOCAL DEMO RUN · {run.inputFilename} · <Badge>{run.status}</Badge> · {run.records.length} records · {new Date(run.createdAt).toLocaleString()}</p>
    <h2>Included files</h2>
    <div className="table"><table><thead><tr><th>File</th><th>Type</th><th>Status</th><th>Rows detected</th><th>Rows processed</th><th>Notes</th></tr></thead><tbody>
      {run.files.map(f=><tr key={f.sourceFileId}><td>{f.filename}</td><td>{f.fileType}</td><td><Badge>{f.status}</Badge></td><td>{f.rowsDetected}</td><td>{f.rowsProcessed}</td><td>{[...f.warnings,...f.errors].join(" · ")||"—"}</td></tr>)}
    </tbody></table></div>
    <h2>Combined stats</h2>
    <div className="kpis"><article><small>Total records</small><strong>{combined.total}</strong></article><article><small>BUY</small><strong>{combined.decisions.BUY}</strong></article><article><small>REVIEW</small><strong>{combined.decisions.REVIEW}</strong></article><article><small>PASS</small><strong>{combined.decisions.PASS}</strong></article><article><small>Avg ROI</small><strong>{combined.avgRoi===null?"—":`${(combined.avgRoi*100).toFixed(1)}%`}</strong></article><article><small>Demo profit</small><strong>{fmt(combined.profit,"$")}</strong></article></div>
    <button onClick={()=>{setActive(run);go("/")}}>Use this run</button>
  </section>
}

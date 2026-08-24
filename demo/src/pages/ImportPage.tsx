import{useEffect,useState}from"react";import{MAX_FILES,parseBatch,type BatchResult}from"../batch";import{useDemoApp}from"../app/context";import{Badge}from"./shared";

const queueKey=(file:File)=>`${file.name}-${file.size}-${file.lastModified}`
const formatSize=(bytes:number)=>bytes<1024?`${bytes} B`:bytes<1024*1024?`${(bytes/1024).toFixed(1)} KB`:`${(bytes/1024/1024).toFixed(1)} MB`

export function ImportPage(){
  const{processBatch,loadIncludedFile}=useDemoApp()
  const[queue,setQueue]=useState<File[]>([])
  const[preview,setPreview]=useState<BatchResult|null>(null)
  const[loading,setLoading]=useState(false)
  const[rejected,setRejected]=useState<string[]>([])
  const[dragging,setDragging]=useState(false)
  const[processing,setProcessing]=useState(false)

  useEffect(()=>{if(!queue.length){setPreview(null);return}let cancelled=false;setLoading(true);parseBatch(queue).then(result=>{if(!cancelled){setPreview(result);setLoading(false)}});return()=>{cancelled=true}},[queue])

  const addFiles=(incoming:File[])=>{
    const accepted=(name:string)=>name.toLowerCase().endsWith(".csv")||name.toLowerCase().endsWith(".xlsx")
    const usable=incoming.filter(file=>accepted(file.name))
    const room=MAX_FILES-queue.length
    const toAdd=usable.slice(0,Math.max(0,room))
    const overflow=[...incoming.filter(file=>!accepted(file.name)).map(f=>`${f.name} (unsupported type)`),...usable.slice(Math.max(0,room)).map(f=>f.name)]
    setRejected(overflow)
    if(toAdd.length)setQueue(current=>[...current,...toAdd])
  }
  const removeFile=(file:File)=>setQueue(current=>current.filter(item=>queueKey(item)!==queueKey(file)))
  const clearAll=()=>{setQueue([]);setRejected([])}
  const process=async()=>{setProcessing(true);await processBatch(queue);setProcessing(false)}

  return <section className="panel">
    <h1>Import supplier files</h1>
    <p>Processed locally in your browser for demo purposes. Nothing is uploaded. Up to {MAX_FILES} files, CSV or XLSX, mixed batches allowed.</p>
    <label className={`drop-zone ${dragging?"dragging":""}`} onDragEnter={()=>setDragging(true)} onDragOver={event=>{event.preventDefault();setDragging(true)}} onDragLeave={()=>setDragging(false)} onDrop={event=>{event.preventDefault();setDragging(false);addFiles([...event.dataTransfer.files])}}>
      Drop CSV or XLSX files here, or choose files
      <input aria-label="Supplier files" type="file" accept=".csv,text/csv,.xlsx,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" multiple onChange={event=>{addFiles([...(event.target.files??[])]);event.target.value=""}}/>
    </label>
    <div className="filters">
      <button onClick={()=>loadIncludedFile().then(file=>addFiles([file]))}>Add included West Marine demo file</button>
      <button onClick={clearAll} disabled={!queue.length}>Clear all</button>
      <span>{queue.length} / {MAX_FILES} files</span>
    </div>
    {rejected.length>0&&<p role="alert">JUVAl supports up to {MAX_FILES} files per batch. Not added: {rejected.join(", ")}.</p>}

    {queue.length>0&&<div className="table"><table><thead><tr><th>File</th><th>Type</th><th>Size</th><th>Sheet</th><th>Rows</th><th>Status</th><th>Notes</th><th></th></tr></thead><tbody>
      {queue.map(file=>{const meta=preview?.files.find(f=>f.filename===file.name&&f.size===file.size);return <tr key={queueKey(file)}>
        <td>{file.name}</td>
        <td>{file.name.toLowerCase().endsWith(".xlsx")?"XLSX":"CSV"}</td>
        <td>{formatSize(file.size)}</td>
        <td>{meta?.sheetName??"—"}</td>
        <td>{loading?"…":meta?meta.rowsProcessed??meta.rowsDetected:"—"}</td>
        <td>{loading?<Badge>PENDING</Badge>:meta?<Badge>{meta.status}</Badge>:<Badge>PENDING</Badge>}</td>
        <td>{meta?[...meta.warnings,...meta.errors].join(" · ")||"—":"—"}</td>
        <td><button onClick={()=>removeFile(file)} aria-label={`Remove ${file.name}`}>Remove</button></td>
      </tr>})}
    </tbody></table></div>}

    {preview&&<p>{preview.files.filter(f=>f.status==="VALID").length} of {preview.files.length} files valid · {preview.records.length} records ready · batch will be <Badge>{preview.status}</Badge></p>}
    <button onClick={process} disabled={!queue.length||loading||processing}>{processing?"Processing…":`Process ${queue.length} file${queue.length===1?"":"s"}`}</button>
  </section>
}

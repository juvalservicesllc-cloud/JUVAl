import{useState}from"react";import{useDemoApp}from"../app/context";import{favoriteKey,sourceIdOf}from"../favorites";import{fmt}from"./shared";import{productPath}from"../product-route";
export function FavoritesPage(){
  const{runs,favorites,toggleFavorite,go}=useDemoApp()
  const[sourceFilter,setSourceFilter]=useState("")
  const items=runs.flatMap(run=>run.records.filter(record=>favorites.includes(favoriteKey(run.runId,sourceIdOf(record),record.recordRef))).map(record=>({run,record,sourceFileId:sourceIdOf(record)})))
  const sources=[...new Set(items.map(item=>item.record.sourceFilename??"Unknown source"))]
  const shown=sourceFilter?items.filter(item=>(item.record.sourceFilename??"Unknown source")===sourceFilter):items
  return <section className="panel">
    <h1>Favorites</h1>
    {items.length>0&&<div className="filters"><label>Source file<select aria-label="Favorites source" value={sourceFilter} onChange={event=>setSourceFilter(event.target.value)}><option value="">All sources</option>{sources.map(name=><option key={name}>{name}</option>)}</select></label></div>}
    {shown.length?<div className="grid">{shown.map(({run,record,sourceFileId})=><article key={favoriteKey(run.runId,sourceFileId,record.recordRef)}><img className="catalog-image" src={record.image} alt="" onError={e=>e.currentTarget.style.visibility="hidden"}/><a href={productPath(run.runId,sourceFileId,record.recordRef)}>{record.title}</a><p><small>{record.sourceFilename??"Unknown source"}</small></p><p>{record.decision} · {fmt(record.profit,"$")} · {record.roi===null?"No ROI":`${(record.roi*100).toFixed(1)}%`}</p><button aria-label={`Remove ${record.title} from favorites`} aria-pressed onClick={()=>toggleFavorite(run.runId,sourceFileId,record.recordRef)}>★ Remove</button></article>)}</div>:<><p>No favorite products yet.</p><button onClick={()=>go("/catalog")}>Browse Catalog</button></>}
  </section>
}

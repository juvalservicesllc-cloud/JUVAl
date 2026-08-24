import { describe, expect, it } from "vitest"
import { normalize, parseCsv } from "./engine"
import { productPath, resolveProduct } from "./product-route"
import { sourceIdOf } from "./favorites"
const csv="position-relative href,img-fluid src,product-brand-name,link,item-price,item-price (2)\n/a,,Brand,Title,$10,$20"
const record={...normalize(parseCsv(csv))[0],sourceFileId:"file-a",sourceFilename:"a.csv"}
const run={schema:1 as const,runId:"run-1",createdAt:"2026-01-01T00:00:00Z",inputFilename:"source.csv",records:[record],warnings:[],files:[],status:"SUCCESS" as const}
describe("durable product route",()=>{
  it("uses batch-scoped identity",()=>expect(productPath(run.runId,sourceIdOf(record),record.recordRef)).toBe(`/run/run-1/file/file-a/product/${record.recordRef}`))
  it("resolves persisted run records without active memory",()=>expect(resolveProduct([run],run.runId,"file-a",record.recordRef).record).toEqual(record))
  it("returns safe not-found states",()=>{
    expect(resolveProduct([run],"missing","file-a",record.recordRef).reason).toBe("RUN_NOT_FOUND")
    expect(resolveProduct([run],run.runId,"file-a","missing").reason).toBe("RECORD_NOT_FOUND")
  })
  it("disambiguates identical recordRef across different source files in the same batch",()=>{
    const otherFile={...record,sourceFileId:"file-b",sourceFilename:"b.csv"}
    const batch={...run,records:[record,otherFile]}
    expect(resolveProduct([batch],batch.runId,"file-a",record.recordRef).record?.sourceFileId).toBe("file-a")
    expect(resolveProduct([batch],batch.runId,"file-b",record.recordRef).record?.sourceFileId).toBe("file-b")
  })
})

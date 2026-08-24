export { parseCsv } from "./csv/parseCsv"
export { classifyColumns, detectWestMarine, validateWestMarine } from "./adapters/WestMarineCsvAdapter"
export { analytics, applyDecisionPolicy, defaultDecisionPolicy, ENGINE_VERSION, exportCsv, money, normalize, validDecisionPolicy } from "./demo-engine"
export type { Analytics, Decision, DemoDecisionPolicy, DemoRecord, Provenance } from "./demo-engine"

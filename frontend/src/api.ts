export type Binary = { id:string; filename:string; sha256:string; size:number; status:string; imported_at:string; metadata_json:{architecture?:string; functions?:unknown[]; sections?:{name:string; address:number; size:number; executable:boolean}[]; entry_point?:number; limitations?:string[]; duration_seconds?:number; analyzer_version?:string} };
export type Job = {id:string; kind:string; resource_id:string; state:string; progress:number; phase:string; cancel_requested:boolean; error:string|null; error_code:string|null; created_at:string};
export type Summary = {id:string; binary_id:string; address:number; end_address:number; name:string; instruction_count:number; block_count:number; confidence:number; discovery_method:string};
export type Instruction = {address:number; size:number; mnemonic:string; operands:string; token:string; bytes_hex:string; flow:string; branch_target:number|null};
export type CFG = {blocks:{id:string; start_address:number; end_address:number; instruction_addresses:number[]}[]; edges:{source:string; target:string; kind:string}[]; unresolved_branches:number[]; statistics:Record<string,number>};
export type FunctionDetail = {id:string; binary_id:string; address:number; end_address:number; name:string; instructions:Instruction[]; cfg:CFG; confidence:number; discovery_method:string; limitations:string[]};
export type Match = {rank:number; function_id:string; name:string; address:number; similarity_score:number; accepted:boolean; evidence:Record<string,number>; limitations:string[]};
export type QueryResult = {query_function_id:string; name:string; address:number; state:string; matches:Match[]};
export type Comparison = {id:string; status:string; config_json:Record<string,unknown>; source_binary_id:string; target_binary_id:string; result:{method:string; model_version:string; feature_schema:string; results:QueryResult[]; candidate_count:number; query_count:number; retrieval_seconds:number; threshold:number; limitations:string[]}|null};
export type Capabilities = {neural:{available:boolean; reason:string; model_version?:string; validation_mrr?:number}; providers:{id:string; available:boolean; enabled:boolean; reason:string; version?:string; capabilities?:string[]}[]; max_upload_bytes:number; feature_schema:string; analyzer_version:string};
export type Page<T> = {items:T[]; total:number; offset:number; limit:number};
export type Experiment = {id:string; kind:string; status:string; created_at:string; result:Record<string,unknown>|null};
export type ResearchStatus = {dataset_available:boolean; sample_count:number; projects:Record<string,string[]>; missing_toolchains:string[]; model:Capabilities['neural']};
export async function api<T>(path:string, init?:RequestInit):Promise<T> {
  const response = await fetch(`/api/v1${path}`,init);
  if (!response.ok) {
    const body = await response.json().catch(()=>null);
    throw new Error(body?.error?.message ?? (Array.isArray(body?.detail) ? body.detail.map((d:{msg:string})=>d.msg).join('; ') : `Request failed (${response.status})`));
  }
  return response.status===204 ? undefined as T : response.json();
}
export const post = <T,>(path:string, body?:unknown) => api<T>(path,{method:'POST',...(body!==undefined ? {headers:{'Content-Type':'application/json'},body:JSON.stringify(body)}:{})});
export const address = (value:number) => `0x${value.toString(16).padStart(8,'0')}`;
export const size = (bytes:number) => bytes<1024 ? `${bytes} B` : bytes<1048576 ? `${(bytes/1024).toFixed(1)} KB` : `${(bytes/1048576).toFixed(1)} MB`;

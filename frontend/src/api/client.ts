export interface Page<T>{items:T[];total:number;page:number;limit:number}
export function query(params:Record<string,string|number|boolean|undefined>){
  const search=new URLSearchParams()
  for(const [key,value] of Object.entries(params)) if(value!==undefined&&value!=='') search.set(key,String(value))
  const text=search.toString()
  return text?'?'+text:''
}
export async function request<T>(path:string,method='GET',body?:unknown):Promise<T>{
 const response=await fetch('/api'+path,{method,credentials:'same-origin',headers:body?{'Content-Type':'application/json'}:undefined,body:body?JSON.stringify(body):undefined})
 const data=await response.json().catch(()=>null)
 if(!response.ok){
   if(response.status===401) window.dispatchEvent(new Event('fgas-session-expired'))
   throw Object.assign(new Error(typeof data?.detail==='string'?data.detail:JSON.stringify(data?.detail || `HTTP ${response.status}`)),{status:response.status})
 }
 return data as T
}

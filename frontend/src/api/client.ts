export async function request<T>(path:string,method='GET',body?:unknown):Promise<T>{
 const response=await fetch('/api'+path,{method,credentials:'same-origin',headers:body?{'Content-Type':'application/json'}:undefined,body:body?JSON.stringify(body):undefined})
 const data=await response.json().catch(()=>null)
 if(!response.ok) throw Object.assign(new Error(typeof data?.detail==='string'?data.detail:JSON.stringify(data?.detail || `HTTP ${response.status}`)),{status:response.status})
 return data as T
}

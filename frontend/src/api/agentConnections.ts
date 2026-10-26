import { request } from './client'
export interface AgentConnection { id:string; owner_user_id:string; owner_name:string|null; name:string; level:'low'|'high'; active:boolean; expires_at:string|null; created_at:string }
export interface ConnectionInput { name:string; level:'low'|'high'; expires_at:string|null }
export const agentConnections = {
  list:()=>request<AgentConnection[]>('/agent-credentials'),
  create:(body:ConnectionInput)=>request<{credential:AgentConnection;secret:string}>('/agent-credentials','POST',body),
  secret:(id:string)=>request<{secret:string}>('/agent-credentials/'+id+'/secret'),
  update:(id:string,body:Partial<ConnectionInput>&{active?:boolean})=>request<AgentConnection>('/agent-credentials/'+id,'PATCH',body),
}

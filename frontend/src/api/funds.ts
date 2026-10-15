import {request} from './client'
export interface User{id:string;display_name:string;role:'admin'|'trusted'|'untrusted';active:boolean}
export interface StocktakeMetadata{id:string;name:string;status:"in_progress"|"ended"}
export type AccountKind='public'|'private'|'external'
export interface AccountBase{id:string;name:string;kind:AccountKind;member_id:string|null;member_name:string|null;avatar_url:string|null;tags:string[];active:boolean;stocktake:StocktakeMetadata|null}
export interface Account extends AccountBase{balance_minor:number}
export interface StockAccount extends AccountBase{current_custody:{id:string;member_id:string;member_name:string;valid_from:string;actor_id:string}|null}
export interface Member{id:string;name:string;note:string}
export interface Sku{id:string;name:string;specification:string;unit:string;avatar_url:string|null;active:boolean}
export interface Line{account_id:string;debit_minor:number;credit_minor:number}
export interface AgentSource{submitted_credential_id?:string|null;submitted_credential_name?:string|null}
export interface AgentAudit{actor_id:string;action:string;agent_credential_id?:string|null;agent_credential_name?:string|null;created_at:string}
export interface Transfer extends AgentSource{id:string;source_account_id:string;destination_account_id:string;source_account_name:string;destination_account_name:string;amount_minor:number;effective_date:string;description:string;tags:string[];counterparty:string|null;status:string;version:number;actor_name:string;approved_by_name:string|null;approval_mode:string|null;reversal_of:string|null;reason:string|null;journal_lines?:Line[];audit?:unknown[]}
export interface TransferInput{source_account_id:string;destination_account_id:string;amount:string;effective_date:string;description:string;tags:string[];counterparty:string|null}
export interface Preview{amount_minor:number;status:string;source_account_name:string;destination_account_name:string;journal_lines:Line[]}
export const api={users:()=>request<User[]>('/auth/users'),me:()=>request<User>('/auth/me'),login:(id:string)=>request<User>('/auth/login','POST',{user_id:id}),logout:()=>request('/auth/logout','POST'),accounts:()=>request<Account[]>('/accounts'),stockAccounts:()=>request<StockAccount[]>('/stock-accounts'),summary:()=>request<{total_minor:number;accounts:Account[]}>('/funds/summary'),transfers:()=>request<Transfer[]>('/transfers'),detail:(id:string)=>request<Transfer>('/transfers/'+id),preview:(body:TransferInput)=>request<Preview>('/transfers/preview','POST',body),submit:(body:TransferInput)=>request<Transfer>('/transfers','POST',body),decide:(item:Transfer,approve:boolean,reason:string)=>request<Transfer>(`/transfers/${item.id}/${approve?'approve':'reject'}`,'POST',{expected_version:item.version,...(!approve?{reason}:{})}),reverse:(id:string,reason:string)=>request<Transfer>(`/transfers/${id}/reverse`,'POST',{reason}),adminUsers:()=>request<User[]>('/users'),saveUser:(user:User)=>request<User>('/users/'+user.id,'PATCH',{role:user.role,active:user.active})}
export function money(fen:number){const value=BigInt(fen);return `${value<0n?'-':''}${(value<0n?-value:value)/100n}.${((value<0n?-value:value)%100n).toString().padStart(2,'0')}`}
export const kinds:Record<string,string>={public:'公账',private:'私账',external:'外部'}
export const statuses:Record<string,string>={pending:'待审批',posted:'已过账',rejected:'已拒绝',reversed:'已冲销'}

export function approvalLabel(mode:string|null|undefined){return ({automatic:"自动批准",manual:"人工批准",agent_direct:"Agent 直接执行",agent_approval:"Agent 批准"} as Record<string,string>)[mode||""]||"待处理"}

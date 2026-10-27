import {request} from './client'
import type { Account } from './accounts'
import type { Transfer, TransferInput } from "./funds";
export interface SettlementItem{transfer:Transfer;settled_minor:number;outstanding_minor:number}
export interface Match{item_transfer_code:string;amount_minor:number;effective:boolean}
export interface SettlementPayment{transfer:Transfer;matched_minor:number;unmatched_minor:number;matches:Match[]}
export interface SettlementOverview{account:Account;expenses:SettlementItem[];receipts:SettlementItem[];settlements:SettlementPayment[]}
export interface Allocation{item_transfer_code:string;amount:string}
export const settlementsApi={overview:(id:string)=>request<SettlementOverview>(`/accounts/${id}/settlement-overview`),create:(transfer:TransferInput,allocations:Allocation[])=>request('/settlements','POST',{transfer,allocations}),add:(id:string,allocations:Allocation[])=>request(`/transfers/${id}/settlement-matches`,'POST',{allocations})}

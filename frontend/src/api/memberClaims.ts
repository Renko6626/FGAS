import {request} from './client'
import type {Transfer,Line} from './funds'
export interface Member{id:string;name:string;note:string;account_id:string}
export interface Claim{id:string;member_id:string;declared_minor:number;confirmed_minor:number|null;basis:string;confirmation_reason:string|null;confirmed_at:string|null;repaid_minor:number;outstanding_minor:number;status:string;version:number;transfer:Transfer}
export interface Allocation{claim_id:string;amount:string;expected_version:number}
export interface Repayment{id:string;member_id:string;basis:string;allocation_mode:'oldest_first'|'manual';status:string;version:number;amount_minor:number;effective:boolean;allocations:{claim_id:string;amount_minor:number}[];reversal_id:string|null;transfer:Transfer}
export interface RepaymentInput{member_id:string;source_account_id:string;amount:string;effective_date:string;description:string;basis:string;allocation_mode:'oldest_first'|'manual';allocations?:{claim_id:string;amount:string}[]}
export interface RepaymentPreview{amount_minor:number;source_account_id:string;destination_account_id:string;allocation_mode:'oldest_first'|'manual';allocations:Allocation[];journal_lines:Line[]}
export interface ClaimInput{member_id:string;destination_account_id:string;amount:string;effective_date:string;description:string;basis:string;confirm_now:boolean;confirmed_amount?:string;confirmation_reason?:string}
export interface MemberDetail{member:Member;pending_minor:number;confirmed_minor:number;repaid_minor:number;outstanding_minor:number;ledger_balance_minor:number;other_movements_minor:number;claims:Claim[];repayments:Repayment[];other_transfers:Transfer[]}
export const membersApi={
 list:()=>request<Member[]>('/members'),create:(body:{name:string;note:string})=>request<Member>('/members','POST',body),update:(id:string,body:{name?:string;note?:string})=>request<Member>('/members/'+id,'PATCH',body),detail:(id:string)=>request<MemberDetail>('/members/'+id),
 claims:(memberId?:string,status?:string)=>request<Claim[]>('/member-claims?'+new URLSearchParams({...memberId?{member_id:memberId}:{},...status?{status}:{}})),claim:(id:string)=>request<Claim>('/member-claims/'+id),submitClaim:(body:ClaimInput)=>request<Claim>('/member-claims','POST',body),confirm:(claim:Claim,amount:string,reason:string)=>request<Claim>(`/member-claims/${claim.id}/confirm`,'POST',{expected_version:claim.version,confirmed_amount:amount,confirmation_reason:reason}),reject:(claim:Claim,reason:string)=>request<Claim>(`/member-claims/${claim.id}/reject`,'POST',{expected_version:claim.version,reason}),
 preview:(body:RepaymentInput)=>request<RepaymentPreview>('/repayments/preview','POST',body),submitRepayment:(body:RepaymentInput&{allocations:Allocation[]})=>request<Repayment>('/repayments','POST',body),repayments:(memberId?:string)=>request<Repayment[]>('/repayments'+(memberId?'?member_id='+encodeURIComponent(memberId):'')),repayment:(id:string)=>request<Repayment>('/repayments/'+id)
}

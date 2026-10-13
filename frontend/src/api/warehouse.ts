import {request} from './client'
import type {Sku,TransferInput} from './funds'
import type {ClaimInput} from './memberClaims'
export interface StockLine{id:string;sku_id:string;sku_name:string;unit:string;quantity:string}
export interface Confirmation{id:string;status:string;actor_id:string;basis:string;effective_date:string;payload:{observations:{line_id:string;observed_quantity:string;basis:string}[]};execution_snapshot:unknown}
export interface Difference{id:string;stock_transfer_id:string;location_id:string;location_name:string;sku_name:string;unit:string;expected_quantity:string;observed_quantity:string;delta:string;basis:string;status:string;adjustments:{id:string;status:string}[]}
export interface StockTransfer{id:string;source_location_id:string;destination_location_id:string;source_location_name:string;destination_location_name:string;source_kind:string;destination_kind:string;action_kind:string;effective_date:string;description:string;basis:string;status:string;content_version:number;execution_version:number;approval_snapshot:unknown;lines:StockLine[];confirmations:Confirmation[];differences:Difference[];difference_id:string|null;fund_references:{id:string;status:string;description:string;amount_minor:number;business_type:string;claim:{declared_minor:number;confirmed_minor:number|null;basis:string}|null}[];audit:unknown[]}
export interface StockInput{source_location_id:string;destination_location_id:string;action_kind:string;effective_date:string;description:string;basis:string;source_reference:string|null;fund_transfer_ids:string[];lines:{sku_id:string;quantity:string}[];idempotency_key:string}
export interface OperationInput{stock:StockInput;money:{kind:'fund_transfer';data:TransferInput&{idempotency_key:string}}|{kind:'member_claim';data:ClaimInput};idempotency_key:string}
export interface InventoryRow{location_id:string;location_name:string;member_name:string|null;sku_id:string;sku_name:string;unit:string;quantity:string;valuation:string;in_transit_planned_quantity:string;differences:{id:string;stock_transfer_id:string;delta:string;status:string;adjustment_id:string|null;adjustment_status:string|null}[]}
export const stockStatuses:Record<string,string>={pending:'待审批',in_transit:'在途（待确认完成）',completed:'已完成',rejected:'已拒绝',cancelled:'已取消',invalidated:'已失效',unresolved:'未调整',adjusting:'调整待完成',resolved:'已调整'}
export const actions:Record<string,string>={opening:'期初入库',arrival:'到货',sale:'销售出库',gift:'赠送',loss:'损耗',return:'退货',internal:'内部转移',adjustment_gain:'调增',adjustment_loss:'调减'}
export const today=()=>{const d=new Date();return `${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,'0')}-${String(d.getDate()).padStart(2,'0')}`} 
export const key=()=>crypto.randomUUID()
export function failure(e:unknown){return (e as Error).message+((e as {status?:number}).status===409?'。请刷新查看当前状态；原请求已保留，请核对后重试。':'。原请求已保留；结果不确定时先刷新查询记录，再重试原请求，不要再次实际交货。')}
// These backend conflicts occur only after same-key replay found no committed action.
// Key-content conflicts and transport/server failures remain unresolved and must replay.
const noncommittingConflicts = new Set([
  '货物转移版本已变化', '货物转移状态不允许该操作', '当前不能申请完成',
  '确认状态已变化', '确认绑定版本已变化', '原转移尚未完成',
  '该完成明细位置已登记差异', '差异已有有效调整',
  '位置未配置或已停用', 'SKU 不存在或已停用', 'SKU 已停用'
])
export function isDefinitiveStockConflict(error: unknown) {
  return (error as {status?: number}).status === 409 &&
    noncommittingConflicts.has((error as Error).message)
}
export const versions=(t:StockTransfer)=>({expected_content_version:t.content_version,expected_execution_version:t.execution_version})
export const warehouse={skus:()=>request<Sku[]>('/skus'),transfers:()=>request<StockTransfer[]>('/stock-transfers'),detail:(id:string)=>request<StockTransfer>('/stock-transfers/'+id),submit:(body:StockInput)=>request<StockTransfer>('/stock-transfers','POST',body),operation:(body:OperationInput)=>request<{stock_transfer:StockTransfer}>('/stock-operations','POST',body),action:(path:string,body:unknown)=>request<StockTransfer>(path,'POST',body),inventory:(filters:Record<string,string>)=>request<{snapshot_at:string;quantities:InventoryRow[];totals:{sku_id:string;quantity:string;valuation:string}[]}>('/inventory?'+new URLSearchParams(Object.entries(filters).filter(([,v])=>v)))}

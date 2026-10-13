import {request} from './client'
import type {Transfer} from './funds'
import type {StockTransfer} from './warehouse'
export type StocktakeKind='fund'|'stock'
interface BaseStocktake{id:string;name:string;description:string;status:'in_progress'|'ended';created_by:string;created_at:string}
export interface FundStocktake extends BaseStocktake{gain_account_id:string;loss_account_id:string;gain_account_name:string;loss_account_name:string}
export interface StockStocktake extends BaseStocktake{gain_account_id:string;loss_account_id:string;gain_account_name:string;loss_account_name:string}
export type Stocktake=FundStocktake|StockStocktake
export interface StocktakeDetail{stocktake:Stocktake;transfers:Transfer[]|StockTransfer[]}
const path=(kind:StocktakeKind)=>`/${kind}-stocktakes`
export const stocktakesApi={
 list:(kind:StocktakeKind)=>request<Stocktake[]>(path(kind)),
 create:(kind:StocktakeKind,data:{name:string;description:string})=>request<Stocktake>(path(kind),'POST',data),
 detail:(kind:StocktakeKind,id:string)=>request<StocktakeDetail>(`${path(kind)}/${id}`),
 update:(kind:StocktakeKind,id:string,description:string)=>request<Stocktake>(`${path(kind)}/${id}`,'PATCH',{description}),
 end:(kind:StocktakeKind,id:string)=>request<Stocktake>(`${path(kind)}/${id}/end`,'POST'),
}

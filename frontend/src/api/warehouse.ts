import { request, query, type Page } from './client';
import type { TransferInput } from "./funds";
import type { AgentSource, AgentAudit, JsonValue } from './audit';
export interface Sku {
  id: string;
  name: string;
  specification: string;
  unit: string;
  avatar_url: string | null;
  active: boolean;
}
export interface StockLine {
  id: string;
  sku_id: string;
  sku_name: string;
  unit: string;
  quantity: string;
}
export interface Confirmation extends AgentSource {
  id: string;
  status: string;
  actor_id: string;
  effective_date: string;
  approved_by: string | null;
  execution_snapshot: {
    mode?: string;
    agent_credential_id?: string | null;
    agent_credential_name?: string | null;
  } | null;
}
export interface RelatedTransfer {
  id: string;
  status: string;
  lines: {
    sku_id: string;
    quantity: string;
  }[];
  source_account_id: string;
  destination_account_id: string;
}
export interface StockTransfer extends AgentSource {
  actor_id: string;
  approved_by: string | null;
  approval_mode: string | null;
  id: string;
  source_account_id: string;
  destination_account_id: string;
  source_account_name: string;
  destination_account_name: string;
  source_kind: string;
  destination_kind: string;
  tags: string[];
  effective_date: string;
  description: string;
  status: string;
  related_transfer_id: string | null;
  related_transfers: RelatedTransfer[];
  approval_snapshot: StockApprovalSnapshot | null;
  lines: StockLine[];
  confirmations: Confirmation[];
  fund_references: {
    id: string;
    status: string;
    description: string;
    amount_minor: number;
    reversal_of: string | null;
    source_account_id: string;
    destination_account_id: string;
  }[];
  audit: (AgentAudit & {
    snapshot: JsonValue;
  })[];
}
export interface StockApprovalSnapshot {
  source_account_id: string;
  destination_account_id: string;
  source_account_name: string;
  destination_account_name: string;
  source_kind: string;
  destination_kind: string;
  description: string;
  tags: string[];
  source_reference: string | null;
  lines: StockLine[];
  fund_references: StockTransfer["fund_references"];
  related_transfer_id: string | null;
  effective_date: string;
  actor_id: string;
  role: string;
  mode: string;
  approved_at: string;
  agent_credential_id?: string | null;
  agent_credential_name?: string | null;
}
export interface SkuCreateInput {
  name: string;
  specification?: string;
  unit: string;
  avatar_url?: string | null;
  active?: boolean;
}
export type SkuUpdateInput = Partial<SkuCreateInput>;
export interface StockInput {
  source_account_id: string;
  destination_account_id: string;
  effective_date: string;
  description: string;
  tags: string[];
  source_reference: string | null;
  fund_transfer_ids: string[];
  lines: {
    sku_id: string;
    quantity: string;
  }[];
  related_transfer_id?: string | null;
}
export interface OperationInput {
  stock: StockInput;
  money: TransferInput;
}
export interface InventoryRow {
  account_id: string;
  account_name: string;
  member_name: string | null;
  sku_id: string;
  sku_name: string;
  unit: string;
  quantity: string;
  valuation: string;
  in_transit_planned_quantity: string;
}
export interface InventoryTotals {
  sku_id: string;
  quantity: string;
  valuation: string;
}
export interface InventoryPage extends Page<InventoryRow> {
  snapshot_at: string;
  totals: InventoryTotals[];
}

export const warehouse = {
  createSku: (body: SkuCreateInput) => request<Sku>("/skus", "POST", body),
  updateSku: (id: string, body: SkuUpdateInput) => request<Sku>(`/skus/${id}`, "PATCH", body),
  skus: () => request<Sku[]>("/skus"),
  transfers: (params: Record<string, string | number | boolean | undefined> = {}) =>
    request<Page<StockTransfer>>("/stock-transfers" + query(params)),
  detail: (id: string) => request<StockTransfer>("/stock-transfers/" + id),
  submit: (body: StockInput) => request<StockTransfer>("/stock-transfers", "POST", body),
  operation: (body: OperationInput) =>
    request<{ stock_transfer: StockTransfer }>("/stock-operations", "POST", body),
  action: (path: string, body: unknown) => request<StockTransfer>(path, "POST", body),
  inventory: (filters: Record<string, string>, page = 1, limit = 20) =>
    request<InventoryPage>("/inventory" + query({ ...filters, page, limit })),
};

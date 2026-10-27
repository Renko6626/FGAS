import { request, query, type Page } from './client';
import type { TransferInput } from "./funds";
import type { AgentSource, AgentAudit } from './audit';
export interface Sku {
  name: string;
  code: string;
  tags: string[];
  unit: string;
  avatar_url: string | null;
  active: boolean;
}
export interface StockLine {
  sku_code: string;
  sku_name: string;
  unit: string;
  quantity: string;
}
export interface Confirmation extends AgentSource {
  code: string;
  transfer_code: string;
  status: string;
  actor_id: string;
  effective_date: string;
  approved_by: string | null;
}
export interface RelatedTransfer {
  code: string;
  status: string;
  lines: {
    sku_code: string;
    quantity: string;
  }[];
  source_account_code: string;
  destination_account_code: string;
}
export interface StockTransfer extends AgentSource {
  actor_id: string;
  approved_by: string | null;
  approval_mode: string | null;
  code: string;
  source_account_code: string;
  destination_account_code: string;
  source_account_name: string;
  destination_account_name: string;
  source_kind: string;
  destination_kind: string;
  tags: string[];
  effective_date: string;
  description: string;
  status: string;
  related_transfer_code: string | null;
  related_transfers: RelatedTransfer[];
  lines: StockLine[];
  confirmations: Confirmation[];
  fund_references: {
    code: string;
    status: string;
    description: string;
    amount_minor: number;
    reversal_of_code: string | null;
    source_account_code: string;
    destination_account_code: string;
  }[];
  audit: (AgentAudit & {
    detail: {
      confirmation_code?: string;
      fund_transfer_code?: string;
      effective_date?: string;
      status?: string;
      reason?: string | null;
      mode?: string | null;
    };
  })[];
}
export interface SkuCreateInput {
  name: string;
  code: string;
  tags?: string[];
  unit: string;
  avatar_url?: string | null;
  active?: boolean;
}
export type SkuUpdateInput = Partial<SkuCreateInput>;
export interface StockInput {
  source_account_code: string;
  destination_account_code: string;
  effective_date: string;
  description: string;
  tags: string[];
  source_reference: string | null;
  fund_transfer_codes: string[];
  lines: {
    sku_code: string;
    quantity: string;
  }[];
  related_transfer_code?: string | null;
}
export interface OperationInput {
  stock: StockInput;
  money: TransferInput;
}
export interface InventoryRow {
  account_code: string;
  account_name: string;
  member_code: string | null;
  member_name: string | null;
  sku_code: string;
  sku_name: string;
  unit: string;
  quantity: string;
  valuation: string;
  in_transit_planned_quantity: string;
}
export interface InventoryTotals {
  sku_code: string;
  quantity: string;
  valuation: string;
}
export interface InventoryPage extends Page<InventoryRow> {
  snapshot_at: string;
  totals: InventoryTotals[];
}

export const warehouse = {
  createSku: (body: SkuCreateInput) => request<Sku>("/skus", "POST", body),
  updateSku: (code: string, body: SkuUpdateInput) => request<Sku>(`/skus/${encodeURIComponent(code)}`, "PATCH", body),
  skus: (filters: { code?: string; q?: string; tag?: string; active?: boolean } = {}) =>
    request<Sku[]>("/skus" + query(filters)),
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

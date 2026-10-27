import { request } from './client';

export interface FundChange {
  code: string; description: string; reversal_of_code: string | null; posted_at: string | null;
  delta_minor: number; source_account_name: string; destination_account_name: string;
}
export interface StockChange {
  code: string; description: string; posted_at: string;
  source_account_name: string; destination_account_name: string;
  lines: { sku_code: string; sku_name: string; unit: string; delta_quantity: string }[];
}
export interface DashboardSku {
  sku_code: string; sku_name: string; unit: string; avatar_url: string | null;
  quantity: string; incoming_quantity: string; outgoing_quantity: string; net_quantity: string;
}
interface OperationBase {
  code: string; created_at: string; effective_date: string; description: string;
  status: string; source_account_name: string; destination_account_name: string; actor_name: string;
}
export type DashboardOperation = OperationBase & (
  { kind: 'funds'; amount_minor: number; reversal_of_code: string | null } |
  { kind: 'stock'; lines: { sku_code: string; sku_name: string; unit: string; quantity: string }[] }
);
export interface Dashboard {
  snapshot_at: string; window_start: string;
  funds: { total_minor: number; incoming_minor: number; outgoing_minor: number; net_minor: number; recent: FundChange[] };
  stock: { skus: DashboardSku[]; recent: StockChange[] };
  counts: { pendingFunds: number; pendingStock: number; inTransit: number };
  operations: Record<'all' | 'funds' | 'stock', DashboardOperation[]>;
}
export const dashboardApi = { overview: () => request<Dashboard>('/dashboard') };

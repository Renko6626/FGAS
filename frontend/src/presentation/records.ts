import type { Transfer } from '../api/funds';
import type { StockLine, StockTransfer } from '../api/warehouse';
import type { DashboardOperation } from '../api/dashboard';
import { money, statuses } from './funds';
import { stockStatuses } from './warehouse';

export interface TransferRecordRow {
  kind: 'funds' | 'stock';
  code: string;
  title: string;
  description?: string;
  date: string;
  createdAt?: string;
  source: string;
  destination: string;
  amount?: string;
  goods: StockLine[];
  status: string;
  statusLabel: string;
  metadata: string[];
  reportPending?: boolean;
  note?: string;
  actionLabel?: string;
}

export function fundRecord(item: Transfer): TransferRecordRow {
  return {
    kind: 'funds', code: item.code,
    title: item.description || (item.reversal_of_code ? '资金冲销' : '未填写说明'),
    date: item.effective_date, source: item.source_account_name, destination: item.destination_account_name,
    amount: money(item.amount_minor), goods: [], status: item.status,
    statusLabel: statuses[item.status] || item.status,
    metadata: [...(item.reversal_of_code ? [`冲销 ${item.reversal_of_code}`] : []), ...item.tags.slice(0, 2)],
  };
}

export function stockRecord(item: StockTransfer): TransferRecordRow {
  return {
    kind: 'stock', code: item.code,
    title: item.lines.map(line => line.sku_name).join('、') || item.description || '货物转移',
    description: item.description, date: item.effective_date,
    source: item.source_account_name, destination: item.destination_account_name,
    goods: item.lines, status: item.status, statusLabel: stockStatuses[item.status] || item.status,
    metadata: [...item.tags.slice(0, 2), ...(item.fund_references.length ? [`关联 ${item.fund_references.length} 笔资金`] : [])],
    reportPending: item.confirmations.some(report => report.status === 'pending'),
  };
}

export function dashboardRecord(item: DashboardOperation): TransferRecordRow {
  return {
    kind: item.kind, code: item.code,
    title: item.kind === 'funds'
      ? item.description || (item.reversal_of_code ? '资金冲销' : '未填写说明')
      : item.lines.map(line => line.sku_name).join('、') || item.description || '货物转移',
    description: item.kind === 'stock' ? item.description : undefined,
    date: item.effective_date, createdAt: item.created_at,
    source: item.source_account_name, destination: item.destination_account_name,
    amount: item.kind === 'funds' ? money(item.amount_minor) : undefined,
    goods: item.kind === 'stock' ? item.lines : [],
    status: item.status, statusLabel: (item.kind === 'funds' ? statuses : stockStatuses)[item.status] || item.status,
    metadata: [item.actor_name, ...(item.kind === 'funds' && item.reversal_of_code ? [`冲销 ${item.reversal_of_code}`] : [])],
  };
}

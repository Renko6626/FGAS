import { request, query, type Page } from "./client";
import type { Account } from "./accounts";
import type { AgentSource } from "./audit";

export interface Line {
  account_id: string;
  debit_minor: number;
  credit_minor: number;
}
export interface Transfer extends AgentSource {
  id: string;
  source_account_id: string;
  destination_account_id: string;
  source_account_name: string;
  destination_account_name: string;
  amount_minor: number;
  effective_date: string;
  description: string;
  tags: string[];
  counterparty: string | null;
  status: string;
  version: number;
  actor_name: string;
  approved_by_name: string | null;
  approval_mode: string | null;
  reversal_of: string | null;
  reason: string | null;
  journal_lines?: Line[];
  audit?: unknown[];
}
export interface TransferInput {
  source_account_id: string;
  destination_account_id: string;
  amount: string;
  effective_date: string;
  description: string;
  tags: string[];
  counterparty: string | null;
}
export interface Preview {
  amount_minor: number;
  status: string;
  source_account_name: string;
  destination_account_name: string;
  journal_lines: Line[];
}

export const fundsApi = {
  summary: () => request<{ total_minor: number; accounts: Account[] }>("/funds/summary"),
  transfers: (params: Record<string, string | number | boolean | undefined> = {}) =>
    request<Page<Transfer>>("/transfers" + query(params)),
  detail: (id: string) => request<Transfer>("/transfers/" + id),
  preview: (body: TransferInput) => request<Preview>("/transfers/preview", "POST", body),
  submit: (body: TransferInput) => request<Transfer>("/transfers", "POST", body),
  decide: (item: Transfer, approve: boolean, reason: string) =>
    request<Transfer>(`/transfers/${item.id}/${approve ? "approve" : "reject"}`, "POST", {
      expected_version: item.version,
      ...(!approve ? { reason } : {}),
    }),
  reverse: (id: string, reason: string) =>
    request<Transfer>(`/transfers/${id}/reverse`, "POST", { reason }),
};

export function money(fen: number) {
  const value = BigInt(fen);
  const absolute = value < 0n ? -value : value;
  return `${value < 0n ? "-" : ""}${absolute / 100n}.${(absolute % 100n).toString().padStart(2, "0")}`;
}
export const statuses: Record<string, string> = {
  pending: "待审批",
  posted: "已过账",
  rejected: "已拒绝",
  reversed: "已冲销",
};

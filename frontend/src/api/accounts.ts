import { request } from "./client";

export interface StocktakeMetadata {
  id: string;
  name: string;
  status: "in_progress" | "ended";
}
export type AccountKind = "public" | "private" | "external";
export interface AccountBase {
  id: string;
  name: string;
  kind: AccountKind;
  member_id: string | null;
  member_name: string | null;
  avatar_url: string | null;
  tags: string[];
  active: boolean;
  stocktake: StocktakeMetadata | null;
}
export interface Account extends AccountBase {
  balance_minor: number;
}
export type StockAccount = AccountBase;
export interface ResponsibilityHistory {
  id: string;
  member_id: string;
  member_name: string;
  valid_from: string;
  valid_to: string | null;
  actor_id: string;
  actor_name: string;
  ended_by: string | null;
  ended_by_name: string | null;
}
export interface StockAccountDetail extends AccountBase {
  responsibility_history: ResponsibilityHistory[];
}

export interface AccountUpdateInput {
  name?: string;
  member_id?: string | null;
  avatar_url?: string | null;
  tags?: string[];
  active?: boolean;
}
export interface AccountCreateInput extends AccountUpdateInput {
  name: string;
  kind: AccountKind;
}
export const accountsApi = {
  create: (body: AccountCreateInput) => request<Account>("/accounts", "POST", body),
  update: (id: string, body: AccountUpdateInput) => request<Account>(`/accounts/${id}`, "PATCH", body),
  createStock: (body: AccountCreateInput) => request<StockAccount>("/stock-accounts", "POST", body),
  updateStock: (id: string, body: AccountUpdateInput) => request<StockAccount>(`/stock-accounts/${id}`, "PATCH", body),
  stockDetail: (id: string) => request<StockAccountDetail>(`/stock-accounts/${id}`),
  accounts: () => request<Account[]>("/accounts"),
  stockAccounts: () => request<StockAccount[]>("/stock-accounts"),
};

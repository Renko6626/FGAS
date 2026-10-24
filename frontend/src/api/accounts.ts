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
export interface StockAccount extends AccountBase {
  current_custody: {
    id: string;
    member_id: string;
    member_name: string;
    valid_from: string;
    actor_id: string;
  } | null;
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
  setCustody: (id: string, member_id: string | null) => request<StockAccount>(`/stock-accounts/${id}/custody`, "POST", { member_id }),
  accounts: () => request<Account[]>("/accounts"),
  stockAccounts: () => request<StockAccount[]>("/stock-accounts"),
};

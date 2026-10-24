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

export const accountsApi = {
  accounts: () => request<Account[]>("/accounts"),
  stockAccounts: () => request<StockAccount[]>("/stock-accounts"),
};
export const kinds: Record<string, string> = {
  public: "公账",
  private: "私账",
  external: "外部",
};

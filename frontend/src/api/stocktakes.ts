import { request, query, type Page } from "./client";
import type { Transfer } from "./funds";
import type { StockTransfer } from "./warehouse";

export type StocktakeKind = "fund" | "stock";
export interface Stocktake {
  id: string;
  name: string;
  description: string;
  status: "in_progress" | "ended";
  created_by: string;
  created_at: string;
  gain_account_id: string;
  loss_account_id: string;
  gain_account_name: string;
  loss_account_name: string;
}
export type StocktakeDetail =
  | { kind: "fund"; stocktake: Stocktake; transfers: Transfer[] }
  | { kind: "stock"; stocktake: Stocktake; transfers: StockTransfer[] };

const path = (kind: StocktakeKind) => `/${kind}-stocktakes`;
export const stocktakesApi = {
  list: (kind: StocktakeKind, params: Record<string, string | number | boolean | undefined> = {}) =>
    request<Page<Stocktake>>(path(kind) + query(params)),
  create: (kind: StocktakeKind, data: { name: string; description: string }) =>
    request<Stocktake>(path(kind), "POST", data),
  detail: async (kind: StocktakeKind, id: string): Promise<StocktakeDetail> => {
    if (kind === "fund") {
      const result = await request<{ stocktake: Stocktake; transfers: Transfer[] }>(`${path(kind)}/${id}`);
      return { ...result, kind };
    }
    const result = await request<{ stocktake: Stocktake; transfers: StockTransfer[] }>(`${path(kind)}/${id}`);
    return { ...result, kind };
  },
  update: (kind: StocktakeKind, id: string, description: string) =>
    request<Stocktake>(`${path(kind)}/${id}`, "PATCH", { description }),
  end: (kind: StocktakeKind, id: string) =>
    request<Stocktake>(`${path(kind)}/${id}/end`, "POST"),
};

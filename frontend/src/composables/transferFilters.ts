import type { Transfer } from "../api/funds";
import type { StockTransfer } from "../api/warehouse";

export interface StockFilters {
  search: string;
  status: string | null;
  skuCode?: string | null;
  tag: string | null;
}

export interface FundFilters extends StockFilters {
  dateFrom: string;
  dateTo: string;
}

export const emptyStockFilters = (): StockFilters => ({
  search: "",
  skuCode: null,
  status: null,
  tag: null,
});

export const emptyFundFilters = (): FundFilters => ({
  ...emptyStockFilters(),
  dateFrom: "",
  dateTo: "",
});

export const hasFundFilters = (filters: FundFilters) => !!(
  filters.search || filters.status || filters.tag || filters.dateFrom || filters.dateTo
);

export const fundDateError = (filters: FundFilters) => !!(
  filters.dateFrom && filters.dateTo && filters.dateFrom > filters.dateTo
);

export function filterFundTransfers(items: Transfer[], filters: FundFilters) {
  const query = filters.search.trim().toLocaleLowerCase();
  return items.filter(t =>
    (!filters.status || t.status === filters.status) &&
    (!filters.tag || t.tags.includes(filters.tag)) &&
    (!filters.dateFrom || t.effective_date >= filters.dateFrom) &&
    (!filters.dateTo || t.effective_date <= filters.dateTo) &&
    (!query || [
      t.source_account_name,
      t.destination_account_name,
      t.description,
      t.counterparty || "",
      t.actor_name,
      ...t.tags,
    ].some(value => value.toLocaleLowerCase().includes(query))),
  );
}

export function filterStockTransfers(items: StockTransfer[], filters: StockFilters) {
  return items.filter(t =>
    (!filters.skuCode || t.lines.some(line => line.sku_code === filters.skuCode)) &&
    (!filters.tag || t.tags.includes(filters.tag)) &&
    (!filters.status || t.status === filters.status) &&
    (!filters.search || [
      t.id,
      t.description,
      t.source_account_name,
      t.destination_account_name,
      ...t.lines.flatMap(line => [line.sku_code, line.sku_name]),
    ].join(" ").toLowerCase().includes(filters.search.trim().toLowerCase())),
  );
}

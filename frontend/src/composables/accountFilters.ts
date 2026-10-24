import type { AccountBase } from "../api/accounts";
interface AccountFilters {
  showEnded: boolean;
  category: string | null;
  tag: string | null;
  search?: string;
}
export function matchesAccountFilters(account: AccountBase, filters: AccountFilters) {
  const query = filters.search?.trim().toLocaleLowerCase();
  return account.active &&
    (filters.showEnded || account.stocktake?.status !== "ended") &&
    (!filters.category || account.kind === filters.category) &&
    (!filters.tag || account.tags.includes(filters.tag)) &&
    (!query || [account.name, account.member_name || "", ...account.tags]
      .some(value => value.toLocaleLowerCase().includes(query)));
}

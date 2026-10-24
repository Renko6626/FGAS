import { ref, type Ref } from "vue";
import { accountsApi, type Account, type StockAccount } from "../api/accounts";
import type { User } from "../api/auth";
import { dashboardApi, type Dashboard } from "../api/dashboard";
import { membersApi, type Member } from "../api/members";
import { warehouse, type Sku } from "../api/warehouse";

export function useWorkspace(
  user: Ref<User | null>,
  identityEpoch: Ref<number>,
  busy: Ref<boolean>,
  error: Ref<string>,
) {
  const accounts = ref<Account[]>([]);
  const locations = ref<StockAccount[]>([]);
  const dashboard = ref<Dashboard | null>(null);
  const counts = ref({ pendingFunds: 0, pendingStock: 0, inTransit: 0 });
  const total = ref(0);
  const skus = ref<Sku[]>([]);
  const members = ref<Member[]>([]);
  const revision = ref(0);

  function clear() {
    accounts.value = [];
    locations.value = [];
    dashboard.value = null;
    counts.value = { pendingFunds: 0, pendingStock: 0, inTransit: 0 };
    skus.value = [];
    members.value = [];
  }

  async function refresh() {
    if (!user.value) return;
    const epoch = identityEpoch.value;
    const actor = user.value.id;
    busy.value = true;
    error.value = "";
    try {
      const [a, l, overview, k, m] = await Promise.all([
        accountsApi.accounts(),
        accountsApi.stockAccounts(),
        dashboardApi.overview(),
        warehouse.skus(),
        membersApi.list(),
      ]);
      if (epoch !== identityEpoch.value || actor !== user.value?.id) return;
      accounts.value = a;
      locations.value = l;
      total.value = overview.funds.total_minor;
      skus.value = k;
      members.value = m;
      dashboard.value = overview;
      counts.value = overview.counts;
      revision.value++;
    } catch (e) {
      error.value = (e as Error).message;
    } finally {
      busy.value = false;
    }
  }

  return { accounts, locations, dashboard, counts, total, skus, members, revision, clear, refresh };
}

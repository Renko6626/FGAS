<script setup lang="ts">
import { ref, onMounted, watch } from "vue";
import { NButton, NSelect } from "naive-ui";
import type { StockAccount } from "../api/accounts";
import type { Member } from "../api/members";
import { warehouse, type InventoryRow, type Sku } from "../api/warehouse";
import AccountLabel from "../components/AccountLabel.vue";
import PaginationBar from "../components/PaginationBar.vue";
const props = defineProps<{
  locations: StockAccount[];
  skus: Sku[];
  members: Member[];
  revision: number;
}>();
const location = ref(""),
  sku = ref(""),
  member = ref(""),
  rows = ref<InventoryRow[]>([]),
  totals = ref<{ sku_id: string; quantity: string; valuation: string }[]>([]),
  error = ref(""),
  busy = ref(false),
  snapshot = ref(""),
  page = ref(1),
  limit = ref(20),
  total = ref(0);
async function refresh() {
  if (busy.value) return;
  busy.value = true;
  try {
    const result = await warehouse.inventory({
      account_id: location.value,
      sku_id: sku.value,
      custodian_id: member.value,
    }, page.value, limit.value);
    rows.value = result.items;
    totals.value = result.totals;
    total.value = result.total;
    snapshot.value = result.snapshot_at;
    error.value = "";
  } catch (e) {
    error.value = (e as Error).message;
  } finally {
    busy.value = false;
  }
}
watch([location, sku, member], () => {
  page.value = 1;
});
watch([page, limit], refresh);
onMounted(refresh);
</script>
<template>
  <div class="toolbar">
    <h2>库存数量</h2>
    <NButton :loading="busy" @click="refresh">查询 / 刷新</NButton>
  </div>
  <div class="filters">
    <NSelect
      v-model:value="location"
      clearable
      placeholder="所有实际地点"
      :options="
        props.locations
          .filter((l) => l.kind !== 'external')
          .map((l) => ({ label: l.name, value: l.id }))
      "
    /><NSelect
      v-model:value="sku"
      clearable
      placeholder="所有 SKU"
      :options="skus.map((s) => ({ label: s.name, value: s.id }))"
    /><NSelect
      v-model:value="member"
      clearable
      placeholder="所有当前保管成员"
      :options="members.map((m) => ({ label: m.name, value: m.id }))"
    />
  </div>
  <p class="error">{{ error }}</p>
  <p>未估值。仅已确认完成的转移影响库存。查询时间：{{ snapshot }}</p>
  <div class="table-wrap">
    <table>
      <thead>
        <tr>
          <th>地点 / 当前保管成员</th>
          <th>SKU</th>
          <th>库存数量</th>
          <th>未完成转移涉及数量</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="r in rows" :key="r.account_id + r.sku_id">
          <td>
            <AccountLabel
              :name="r.account_name"
              :url="locations.find((a) => a.id === r.account_id)?.avatar_url"
            /><small>{{ r.member_name || "未指定成员" }}</small>
          </td>
          <td>
            <AccountLabel
              :name="r.sku_name"
              :url="skus.find((s) => s.id === r.sku_id)?.avatar_url"
            />
          </td>
          <td>{{ r.quantity }} {{ r.unit }}</td>
          <td>{{ r.in_transit_planned_quantity }}</td>
        </tr>
      </tbody>
    </table>
  </div>
  <PaginationBar
    :page="page"
    :limit="limit"
    :total="total"
    @update:page="page = $event"
    @update:limit="limit = $event; page = 1"
  />
  <p v-for="t in totals" :key="t.sku_id">
    {{ skus.find((s) => s.id === t.sku_id)?.name || t.sku_id }} 合计：{{
      t.quantity
    }}，{{ t.valuation }}
  </p>
</template>

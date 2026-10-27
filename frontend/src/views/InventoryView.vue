<script setup lang="ts">
import { ref, onMounted, onBeforeUnmount, watch } from "vue";
import { NButton, NSelect } from "naive-ui";
import type { StockAccount } from "../api/accounts";
import type { Member } from "../api/members";
import { warehouse, type InventoryRow, type InventoryTotals, type Sku } from "../api/warehouse";
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
  totals = ref<InventoryTotals[]>([]),
  error = ref(""),
  busy = ref(false),
  snapshot = ref(""),
  page = ref(1),
  limit = ref(20),
  total = ref(0);
let requestSequence = 0;
async function refresh() {
  const sequence = ++requestSequence;
  busy.value = true;
  try {
    const result = await warehouse.inventory({
      account_code: location.value,
      sku_code: sku.value,
      member_code: member.value,
    }, page.value, limit.value);
    if (sequence !== requestSequence) return;
    rows.value = result.items;
    totals.value = result.totals;
    total.value = result.total;
    snapshot.value = result.snapshot_at;
    error.value = "";
  } catch (e) {
    if (sequence === requestSequence) error.value = (e as Error).message;
  } finally {
    if (sequence === requestSequence) busy.value = false;
  }
}
watch([location, sku, member], () => {
  ++requestSequence;
  busy.value = false;
  page.value = 1;
}, { flush: "sync" });
watch([page, limit], refresh, { flush: "sync" });
watch(() => props.revision, refresh, { flush: "sync" });
onBeforeUnmount(() => { ++requestSequence; });
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
          .map((l) => ({ label: l.name, value: l.code }))
      "
    /><NSelect
      v-model:value="sku"
      clearable
      filterable
      placeholder="所有 SKU"
      :options="skus.map((s) => ({ label: `${s.code} ${s.name}`, value: s.code }))"
    /><NSelect
      v-model:value="member"
      clearable
      placeholder="所有负责人"
      :options="members.map((m) => ({ label: `${m.name}（${m.code}）`, value: m.code }))"
    />
  </div>
  <p class="error">{{ error }}</p>
  <p>未估值。仅已确认完成的转移影响库存。查询时间：{{ snapshot }}</p>
  <div class="table-wrap">
    <table>
      <thead>
        <tr>
          <th>地点 / 负责人</th>
          <th>SKU</th>
          <th>库存数量</th>
          <th>待完成流入</th>
          <th>待完成流出</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="r in rows" :key="r.account_code + r.sku_code">
          <td>
            <AccountLabel
              :name="r.account_name"
              :url="locations.find((a) => a.code === r.account_code)?.avatar_url"
            /><small>{{ r.member_name || "未指定负责人" }}</small>
          </td>
          <td>
            <AccountLabel
              :name="`${r.sku_code} ${r.sku_name}`"
              :url="skus.find((s) => s.code === r.sku_code)?.avatar_url"
            />
          </td>
          <td>{{ r.quantity }} {{ r.unit }}</td>
          <td>{{ r.incoming_planned_quantity ?? "不可用" }}</td>
          <td>{{ r.outgoing_planned_quantity ?? "不可用" }}</td>
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
  <p>汇总范围：{{ location || member || sku ? "当前筛选范围" : "全部组织" }}。计划量仅含已批准但尚未确认完成的单据。各页重复显示同一范围汇总，请勿相加。</p>
  <p v-for="t in totals" :key="t.sku_code">
    {{ t.sku_code }} {{ t.sku_name }}：正式数量 {{ t.quantity }} {{ t.unit }}；
    外部流入计划 {{ t.incoming_to_org_quantity ?? "不可用" }}；
    对外流出计划 {{ t.outgoing_from_org_quantity ?? "不可用" }}；
    内部调拨计划 {{ t.internal_transfer_quantity ?? "不可用" }}。{{ t.valuation }}
  </p>
</template>

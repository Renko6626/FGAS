<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from "vue";
import { NButton, NInput, NSelect } from "naive-ui";
import type { StockAccount } from "../api/accounts";
import type { Member } from "../api/members";
import { warehouse, type InventoryRow, type InventoryTotals, type Sku, type StockTransfer } from "../api/warehouse";
import InventoryMap from "../components/inventory/InventoryMap.vue";
import InventoryMatrix from "../components/inventory/InventoryMatrix.vue";
import InventoryCatalog from "../components/inventory/InventoryCatalog.vue";

const props = defineProps<{ locations: StockAccount[]; skus: Sku[]; members: Member[]; revision: number }>();
const initial = new URLSearchParams(window.location.hash.split("?")[1] || "");
const view = ref(initial.get("view") === "matrix" ? "matrix" : "map");
const selectedSku = ref(initial.get("sku") || "");
const search = ref("");
const tag = ref<string | null>(null);
const showFilters = ref(false);
const onlyPending = ref(initial.get("pending") === "true");
const sort = ref(initial.get("sort") || "name");
const selectedLocations = ref<string[]>([]);
const member = ref<string | null>(null);
const rows = ref<InventoryRow[]>([]);
const totals = ref<InventoryTotals[]>([]);
const transfers = ref<StockTransfer[]>([]);
const busy = ref(false);
const error = ref("");
const snapshot = ref("");
const skuByCode = computed(() => new Map(props.skus.map(item => [item.code, item])));
const tagOptions = computed(() => [...new Set(props.skus.flatMap(item => item.tags))].sort((a, b) => a.localeCompare(b, "zh-CN")).map(value => ({ label: value, value })));
const internalLocations = computed(() => props.locations.filter(item => item.kind === "internal"));
const locationOptions = computed(() => internalLocations.value.map(item => ({ label: item.name, value: item.code })));
const memberOptions = computed(() => props.members.filter(item => internalLocations.value.some(place => place.member_code === item.code)).map(item => ({ label: item.name, value: item.code })));
const sortOptions = [
  { label: "名称排序", value: "name" }, { label: "SKU 排序", value: "code" },
  { label: "库存数量优先", value: "quantity" }, { label: "待处理优先", value: "pending" },
];
const scopedLocations = computed(() => internalLocations.value.filter(item => (!selectedLocations.value.length || selectedLocations.value.includes(item.code)) && (!member.value || item.member_code === member.value)));
const scopedCodes = computed(() => new Set(scopedLocations.value.map(item => item.code)));
const scopedTransfers = computed(() => transfers.value.filter(item => scopedCodes.value.has(item.source_account_code) || scopedCodes.value.has(item.destination_account_code)));
const pendingCounts = computed(() => {
  const counts = new Map<string, number>();
  for (const transfer of scopedTransfers.value) {
    for (const code of new Set(transfer.lines.map(line => line.sku_code))) counts.set(code, (counts.get(code) || 0) + 1);
  }
  return counts;
});
const scopedSkuCodes = computed(() => new Set(rows.value.filter(row => scopedCodes.value.has(row.account_code) && BigInt(row.quantity) !== 0n).map(row => row.sku_code)));
const visibleTotals = computed(() => {
  const query = search.value.trim().toLocaleLowerCase();
  return totals.value.filter(item => (!tag.value || skuByCode.value.get(item.sku_code)?.tags.includes(tag.value)) &&
    (!query || `${item.sku_code} ${item.sku_name}`.toLocaleLowerCase().includes(query)) &&
    (!onlyPending.value || pendingCounts.value.has(item.sku_code)) &&
    ((!selectedLocations.value.length && !member.value) || scopedSkuCodes.value.has(item.sku_code) || pendingCounts.value.has(item.sku_code)))
    .sort((a, b) => {
      if (sort.value === "pending") {
        const difference = (pendingCounts.value.get(b.sku_code) || 0) - (pendingCounts.value.get(a.sku_code) || 0);
        if (difference) return difference;
      }
      if (sort.value === "quantity") {
        const difference = BigInt(b.quantity) - BigInt(a.quantity);
        if (difference !== 0n) return difference > 0n ? 1 : -1;
      }
      return sort.value === "code" ? a.sku_code.localeCompare(b.sku_code) : a.sku_name.localeCompare(b.sku_name, "zh-CN") || a.sku_code.localeCompare(b.sku_code);
    });
});
const pendingSkuCount = computed(() => visibleTotals.value.filter(item => pendingCounts.value.has(item.sku_code)).length);
const updatedAt = computed(() => snapshot.value ? new Date(snapshot.value).toLocaleString("zh-CN", { hour12: false }) : "—");

watch(visibleTotals, items => {
  if (!items.some(item => item.sku_code === selectedSku.value)) {
    selectedSku.value = items.find(item => BigInt(item.incoming_to_org_quantity || "0") > 0n)?.sku_code || items[0]?.sku_code || "";
  }
});
watch([view, selectedSku, onlyPending, sort], () => {
  const params = new URLSearchParams();
  params.set("view", view.value);
  if (selectedSku.value) params.set("sku", selectedSku.value);
  if (onlyPending.value) params.set("pending", "true");
  if (sort.value !== "name") params.set("sort", sort.value);
  window.history.replaceState({}, "", `${window.location.pathname}${window.location.search}#inventory?${params}`);
});

let requestSequence = 0;
async function refresh() {
  const sequence = ++requestSequence;
  busy.value = true;
  error.value = "";
  try {
    const [inventory, plans, approvals] = await Promise.all([
      warehouse.inventory({}, 1, 100),
      warehouse.transfers({ status: "in_transit", page: 1, limit: 100 }),
      warehouse.transfers({ status: "pending", page: 1, limit: 100 }),
    ]);
    const allRows = [...inventory.items];
    const allPlans = [...plans.items];
    const allApprovals = [...approvals.items];
    for (let page = 2; page <= Math.ceil(inventory.total / 100); page++) {
      if (sequence !== requestSequence) return;
      allRows.push(...(await warehouse.inventory({}, page, 100)).items);
    }
    for (let page = 2; page <= Math.ceil(plans.total / 100); page++) {
      if (sequence !== requestSequence) return;
      allPlans.push(...(await warehouse.transfers({ status: "in_transit", page, limit: 100 })).items);
    }
    for (let page = 2; page <= Math.ceil(approvals.total / 100); page++) {
      if (sequence !== requestSequence) return;
      allApprovals.push(...(await warehouse.transfers({ status: "pending", page, limit: 100 })).items);
    }
    if (sequence !== requestSequence) return;
    rows.value = allRows;
    transfers.value = [...allPlans, ...allApprovals];
    totals.value = inventory.totals;
    snapshot.value = inventory.snapshot_at;
  } catch (e) {
    if (sequence === requestSequence) error.value = (e as Error).message;
  } finally {
    if (sequence === requestSequence) busy.value = false;
  }
}
watch(() => props.revision, refresh);
onMounted(refresh);
onBeforeUnmount(() => { ++requestSequence; });
</script>

<template>
  <div class="inventory-workspace" :aria-busy="busy">
    <div class="inventory-controls">
      <div class="inventory-views" role="group" aria-label="库存视图">
        <button :class="{ active: view === 'map' }" :aria-pressed="view === 'map'" @click="view = 'map'">后勤沙盘</button>
        <button :class="{ active: view === 'matrix' }" :aria-pressed="view === 'matrix'" @click="view = 'matrix'">分布矩阵</button>
      </div>
      <button class="pending-filter" :class="{ active: onlyPending }" :aria-pressed="onlyPending" title="包含待审批和待完成的货物转移" @click="onlyPending = !onlyPending"><span class="pending-indicator"></span>仅看待处理<strong>{{ pendingSkuCount }} 种</strong></button>
      <NButton size="small" quaternary :aria-expanded="showFilters" @click="showFilters = !showFilters">{{ showFilters ? '收起筛选' : '筛选' }}</NButton>
      <NButton size="small" :loading="busy" :title="`库存更新于 ${updatedAt}`" @click="refresh">刷新</NButton>
    </div>
    <div v-if="showFilters" class="inventory-filters">
      <NInput v-model:value="search" clearable placeholder="搜索货物名称或 SKU" :input-props="{ 'aria-label': '搜索货物' }" />
      <NSelect v-model:value="tag" :options="tagOptions" clearable placeholder="全部货物标签" aria-label="货物标签" />
      <NSelect v-model:value="selectedLocations" multiple clearable :max-tag-count="1" :options="locationOptions" placeholder="全部保管地点" aria-label="筛选保管地点" />
      <NSelect v-model:value="member" clearable :options="memberOptions" placeholder="全部负责人" aria-label="筛选负责人" />
    </div>
    <p v-if="error" class="error" role="alert">{{ error }}</p>
    <div v-if="totals.length" class="inventory-layout">
      <InventoryCatalog v-model:selected-sku="selectedSku" v-model:sort="sort" :totals="visibleTotals" :pending-counts="pendingCounts" :sort-options="sortOptions" />
      <div class="inventory-content">
        <InventoryMap v-if="view === 'map'" :selected-sku="selectedSku" :totals="visibleTotals" :rows="rows" :locations="locations" :location-codes="[...scopedCodes]" :skus="skus" :transfers="scopedTransfers" />
        <InventoryMatrix v-else v-model:selected-sku="selectedSku" :totals="visibleTotals" :rows="rows" :locations="scopedLocations" :location-count="internalLocations.length" :pending-counts="pendingCounts" :transfers="scopedTransfers" />
      </div>
    </div>
    <p v-else class="inventory-empty">{{ busy ? '正在读取库存与待完成转移…' : '还没有货物库存，登记货物转移后可在这里查看。' }}</p>
  </div>
</template>

<style scoped>
.inventory-workspace { min-width:0; }
.inventory-layout { display:grid; grid-template-columns:200px minmax(0,1fr); gap:22px; min-width:0; }
.inventory-content { min-width:0; }
.inventory-controls { display:flex; align-items:center; gap:8px; padding:0 0 14px; }
.inventory-views { display:flex; padding:4px; background:#edf1f4; border-radius:7px; margin-right:auto; }
.inventory-views button { padding:7px 15px; border:0; background:transparent; color:#52616c; border-radius:4px; min-width:0; font-size:14px; }
.inventory-views button.active { background:#fff; color:#1f4b51; box-shadow:0 1px 4px #1d394214; font-weight:650; }
.pending-filter { display:flex; align-items:center; gap:8px; min-width:0; padding:8px 12px; border:1px solid #d49a35; border-radius:6px; background:#fff6e4; color:#81520f; font-size:13px; font-weight:600; white-space:nowrap; }
.pending-filter:hover { background:#ffedc9; }
.pending-filter.active { background:#98601b; border-color:#98601b; color:#fff; }
.pending-filter strong { padding:1px 7px; border-radius:4px; background:#e9c683; color:#67400c; font-size:12px; }
.pending-filter.active strong { background:#fff1d4; }
.pending-indicator { width:6px; height:6px; border-radius:50%; background:#bd8228; }
.pending-filter.active .pending-indicator { background:#ffe6ad; }
.inventory-filters { display:flex; flex-wrap:wrap; gap:10px; margin-bottom:14px; }
.inventory-filters > :deep(.n-input) { width:240px; }
.inventory-filters > :deep(.n-select) { width:180px; }
.inventory-empty { padding:36px 0; color:#66707c; }
@media(max-width:1100px) { .inventory-layout { grid-template-columns:170px minmax(0,1fr); gap:16px; } }
@media(max-width:760px) {
  .inventory-layout { display:block; }
  .inventory-controls { flex-wrap:wrap; gap:8px; }
  .inventory-controls > :deep(.n-button) { min-width:48px; }
  .inventory-views { flex:0 0 auto; margin-right:auto; }
  .pending-filter { order:1; flex-basis:100%; justify-content:center; }
  .inventory-views button { flex:1; padding:7px 8px; font-size:13px; white-space:nowrap; }
  .inventory-filters > :deep(.n-input),.inventory-filters > :deep(.n-select) { width:100%; }
}
</style>

<script setup lang="ts">
import { computed, ref, onMounted, onBeforeUnmount, watch } from "vue";
import { NButton, NInput } from "naive-ui";
import type { StockAccount } from "../api/accounts";
import type { Member } from "../api/members";
import { warehouse, type InventoryRow, type InventoryTotals, type Sku } from "../api/warehouse";
import AccountLabel from "../components/AccountLabel.vue";
import AccountAvatar from "../components/AccountAvatar.vue";
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
  total = ref(0),
  search = ref(""),
  tag = ref(""),
  locationRows = ref<InventoryRow[]>([]),
  expandedLocation = ref(""),
  view = ref<"sku" | "location">("sku");
const skuByCode = computed(() => new Map(props.skus.map(item => [item.code, item])));
const tags = computed(() => [...new Set(props.skus.flatMap(item => item.tags))].sort((a, b) => a.localeCompare(b, "zh-CN")));
function matchesTag(code: string) { return !tag.value || !!skuByCode.value.get(code)?.tags.includes(tag.value); }
const locationGroups = computed(() => {
  const groups = new Map<string, { code: string; name: string; member: string | null; items: InventoryRow[] }>();
  for (const row of locationRows.value) {
    if (!matchesTag(row.sku_code) || (BigInt(row.quantity) === 0n && BigInt(row.incoming_planned_quantity || "0") === 0n && BigInt(row.outgoing_planned_quantity || "0") === 0n)) continue;
    let group = groups.get(row.account_code);
    if (!group) { group = { code: row.account_code, name: row.account_name, member: row.member_name, items: [] }; groups.set(row.account_code, group); }
    group.items.push(row);
  }
  return [...groups.values()];
});
const expandedGroup = computed(() => locationGroups.value.find(group => group.code === expandedLocation.value));
const shownTotals = computed(() => {
  const query = search.value.trim().toLocaleLowerCase();
  return totals.value.filter(t => matchesTag(t.sku_code) && (!query || `${t.sku_code} ${t.sku_name}`.toLocaleLowerCase().includes(query)));
});
function selectTag(value: string) { tag.value = value; if (sku.value && !matchesTag(sku.value)) sku.value = ""; }
const internalLocations = computed(() => props.locations.filter(a => a.kind === "internal"));
const selectedSku = computed(() => props.skus.find(s => s.code === sku.value));
const updatedAt = computed(() => snapshot.value ? new Date(snapshot.value).toLocaleString("zh-CN", { hour12: false }) : "—");
let requestSequence = 0;
async function refresh() {
  const sequence = ++requestSequence;
  busy.value = true;
  try {
    const filters = { account_code: location.value, sku_code: sku.value, member_code: member.value };
    const locationView = view.value === "location";
    const result = await warehouse.inventory(filters, locationView ? 1 : page.value, locationView ? 100 : limit.value);
    if (sequence !== requestSequence) return;
    if (locationView) {
      const allRows = [...result.items];
      for (let next = 2; next <= Math.ceil(result.total / 100); next++) {
        const batch = await warehouse.inventory(filters, next, 100);
        if (sequence !== requestSequence) return;
        allRows.push(...batch.items);
      }
      locationRows.value = allRows;
    } else rows.value = result.items;
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
  if (page.value === 1) refresh();
  else page.value = 1;
}, { flush: "sync" });
watch([page, limit], refresh, { flush: "sync" });
watch(() => props.revision, refresh, { flush: "sync" });
watch(view, () => { expandedLocation.value = ""; refresh(); });
onBeforeUnmount(() => { ++requestSequence; });
onMounted(refresh);
</script>
<template>
  <div class="inventory-header">
    <div><h2>货物库存</h2><p>已完成的货物转移计入库存，待完成的转移单独列出。</p></div>
    <NButton :loading="busy" @click="refresh">刷新</NButton>
  </div>
  <div class="view-tabs" aria-label="库存视图">
    <button :class="{ active: view === 'sku' }" :aria-pressed="view === 'sku'" @click="view = 'sku'">按货物</button>
    <button :class="{ active: view === 'location' }" :aria-pressed="view === 'location'" @click="view = 'location'">按储存位置</button>
  </div>
  <div class="inventory-filters">
    <div class="filter-row"><span>保管地点</span><div class="filter-options"><button :class="{ active: !location }" :aria-pressed="!location" @click="location = ''">全部</button><button v-for="place in internalLocations" :key="place.code" :class="{ active: location === place.code }" :aria-pressed="location === place.code" @click="location = place.code">{{ place.name }}</button></div></div>
    <div class="filter-row"><span>负责人</span><div class="filter-options"><button :class="{ active: !member }" :aria-pressed="!member" @click="member = ''">全部</button><button v-for="person in members" :key="person.code" :class="{ active: member === person.code }" :aria-pressed="member === person.code" @click="member = person.code">{{ person.name }}</button></div></div>
    <div v-if="tags.length" class="filter-row"><span>货物标签</span><div class="filter-options"><button :class="{ active: !tag }" :aria-pressed="!tag" @click="selectTag('')">全部</button><button v-for="item in tags" :key="item" :class="{ active: tag === item }" :aria-pressed="tag === item" @click="selectTag(item)">{{ item }}</button></div></div>
  </div>
  <p v-if="error" class="error" role="alert">{{ error }}</p>
  <template v-if="view === 'sku'">
  <div class="inventory-section-heading">
    <div><h3>{{ sku ? '已选货物' : '货物汇总' }}</h3><p>{{ location || member ? '当前筛选范围' : '全部组织' }}，点击货物查看保管明细</p></div>
    <NButton v-if="sku" @click="sku = ''; search = ''">查看全部货物</NButton>
    <NInput v-else v-model:value="search" clearable placeholder="搜索货物名称或 SKU" :input-props="{ 'aria-label': '搜索货物库存' }" />
  </div>
  <div v-if="shownTotals.length" class="inventory-grid">
    <button v-for="t in shownTotals" :key="t.sku_code" class="inventory-card" :class="{ selected: sku === t.sku_code }" :aria-pressed="sku === t.sku_code" @click="sku = t.sku_code; search = ''">
      <div class="item-heading"><AccountAvatar :name="t.sku_name" :url="skus.find(s => s.code === t.sku_code)?.avatar_url" /><div><strong>{{ t.sku_name }}</strong><small>{{ t.sku_code }}</small></div></div>
      <div class="item-quantity"><span>当前库存</span><strong>{{ t.quantity }} <small>{{ t.unit }}</small></strong></div>
      <div class="item-plans"><span>外部待入 <strong>{{ t.incoming_to_org_quantity ?? '—' }}</strong></span><span>对外待出 <strong>{{ t.outgoing_from_org_quantity ?? '—' }}</strong></span><span>内部调拨 <strong>{{ t.internal_transfer_quantity ?? '—' }}</strong></span></div>
    </button>
  </div>
  <p v-else class="inventory-empty">{{ busy ? '正在读取库存…' : '没有符合条件的货物。' }}</p>
  <section v-if="sku" class="inventory-details">
    <div class="detail-heading"><div><h3>保管明细</h3><p>{{ selectedSku?.name || sku }} 在各地点的库存和待完成转移</p></div><span>{{ total }} 条</span></div>
    <div v-if="rows.length" class="detail-grid">
      <div v-for="r in rows" :key="r.account_code + r.sku_code" class="detail-item">
        <div class="detail-identity"><AccountLabel :name="r.account_name" :code="r.account_code" :url="locations.find(a => a.code === r.account_code)?.avatar_url" /><span class="detail-member">{{ r.member_name || '未指定负责人' }}</span></div>
        <div class="detail-quantities"><span>库存 <strong>{{ r.quantity }} {{ r.unit }}</strong></span><span>待入 {{ r.incoming_planned_quantity ?? '—' }}</span><span>待出 {{ r.outgoing_planned_quantity ?? '—' }}</span></div>
      </div>
    </div>
    <p v-else class="inventory-empty">{{ busy ? '正在读取明细…' : '当前筛选范围没有保管明细。' }}</p>
    <PaginationBar v-if="total > 0" :page="page" :limit="limit" :total="total" @update:page="page = $event" @update:limit="limit = $event; page = 1" />
  </section>
  </template>
  <section v-else class="location-view">
    <div class="detail-heading"><div><h3>储存位置</h3><p>显示有库存或待完成转移的货物，点击位置查看明细。</p></div><NButton v-if="sku" @click="sku = ''">清除货物筛选：{{ selectedSku?.name || sku }}</NButton></div>
    <div v-if="locationGroups.length" class="location-grid">
      <button v-for="group in locationGroups" :key="group.code" class="location-card" :class="{ selected: expandedLocation === group.code }" :aria-pressed="expandedLocation === group.code" @click="expandedLocation = expandedLocation === group.code ? '' : group.code">
        <div class="location-heading"><AccountAvatar :name="group.name" :url="locations.find(a => a.code === group.code)?.avatar_url" /><div><strong>{{ group.name }}</strong><small>{{ group.member || '未指定负责人' }}</small></div></div>
        <div class="location-preview"><div v-for="item in group.items.slice(0, 3)" :key="item.sku_code"><span>{{ item.sku_name }}</span><strong>{{ item.quantity }} {{ item.unit }}</strong></div><small v-if="group.items.length > 3">等 {{ group.items.length }} 种货物</small><small v-else>{{ group.items.length }} 种货物</small></div>
      </button>
    </div>
    <p v-else class="inventory-empty">{{ busy ? '正在读取库存…' : '当前筛选范围没有库存或待完成转移。' }}</p>
    <div v-if="expandedGroup" class="inventory-details">
      <div class="detail-heading"><div><h3>{{ expandedGroup.name }}的货物</h3><p>当前库存及待完成转移</p></div><NButton @click="expandedLocation = ''">收起明细</NButton></div>
      <div class="detail-grid">
        <div v-for="item in expandedGroup.items" :key="item.sku_code" class="detail-item">
          <div class="detail-identity"><AccountLabel :name="item.sku_name" :code="item.sku_code" :url="skus.find(s => s.code === item.sku_code)?.avatar_url" /></div>
          <div class="detail-quantities"><span>库存 <strong>{{ item.quantity }} {{ item.unit }}</strong></span><span>待入 {{ item.incoming_planned_quantity ?? '—' }}</span><span>待出 {{ item.outgoing_planned_quantity ?? '—' }}</span></div>
        </div>
      </div>
    </div>
  </section>
  <p class="inventory-footnote">待入、待出和内部调拨仅包含已批准但尚未确认完成的转移。更新时间：{{ updatedAt }}</p>
</template>
<style scoped>
.inventory-header,.inventory-section-heading,.detail-heading { display:flex; align-items:center; justify-content:space-between; gap:16px; }
.inventory-header h2,.inventory-section-heading h3,.detail-heading h3 { margin:0; }
.inventory-header p,.inventory-section-heading p,.detail-heading p { margin:4px 0 0; font-size:13px; color:#66707c; }
.view-tabs { display:flex; gap:4px; border-bottom:1px solid #e3e8ec; margin-top:18px; }
.view-tabs button { border:0; border-bottom:2px solid transparent; padding:9px 14px; background:transparent; color:#66707c; }
.view-tabs button.active { color:#244a66; border-bottom-color:#345d78; font-weight:650; }
.location-view { margin-top:22px; }
.location-grid { display:grid; grid-template-columns:repeat(auto-fill,minmax(250px,1fr)); gap:12px; }
.location-card { text-align:left; border:1px solid #e2e8ed; border-radius:7px; padding:14px; background:#fff; color:#20242a; min-width:0; }
.location-card:hover,.location-card.selected { border-color:#82a1b8; background:#f5f9fc; }
.location-heading { display:flex; align-items:center; gap:10px; margin-bottom:10px; }
.location-heading :deep(.account-avatar) { width:38px; height:38px; margin:0; border-radius:50%; }
.location-heading strong,.location-heading small { display:block; overflow-wrap:anywhere; }
.location-preview > div { display:flex; justify-content:space-between; gap:8px; padding:4px 0; font-size:13px; }
.location-preview > div span { overflow:hidden; white-space:nowrap; text-overflow:ellipsis; }
.location-preview > div strong { white-space:nowrap; }
.location-preview small { display:block; margin-top:6px; color:#66707c; }
.inventory-filters { margin:20px 0; padding:12px 16px; background:#f5f7f9; border-radius:7px; }
.filter-row { display:flex; align-items:baseline; gap:12px; padding:4px 0; }
.filter-row > span { flex-shrink:0; width:58px; color:#66707c; font-size:13px; }
.filter-options { display:flex; flex-wrap:wrap; gap:4px; }
.filter-options button { padding:5px 10px; border:0; border-radius:4px; background:transparent; color:#42505c; }
.filter-options button.active { background:#dce9f2; color:#244a66; font-weight:600; }
.inventory-section-heading { margin:22px 0 14px; }
.inventory-section-heading :deep(.n-input) { width:260px; max-width:45%; }
.inventory-grid { display:grid; grid-template-columns:repeat(auto-fill,minmax(250px,1fr)); gap:12px; }
.inventory-card { text-align:left; border:1px solid #e2e8ed; border-radius:7px; background:#fff; padding:12px; color:#20242a; min-width:0; }
.inventory-card:hover,.inventory-card.selected { border-color:#82a1b8; background:#f5f9fc; }
.item-heading { display:flex; align-items:center; gap:10px; min-width:0; }
.item-heading :deep(.account-avatar) { width:40px; height:40px; margin:0; border-radius:6px; }
.item-heading strong,.item-heading small { display:block; overflow-wrap:anywhere; }
.item-heading small { margin-top:2px; }
.item-quantity { display:flex; justify-content:space-between; align-items:baseline; margin:10px 0 8px; gap:8px; }
.item-quantity span,.item-plans { color:#66707c; font-size:12px; }
.item-quantity strong { font-size:21px; font-variant-numeric:tabular-nums; }
.item-quantity strong small { font-size:12px; font-weight:400; }
.item-plans { display:flex; flex-wrap:wrap; gap:6px 12px; border-top:1px solid #e8edf1; padding-top:7px; }
.item-plans strong { color:#354c5f; }
.inventory-details { margin-top:24px; }
.detail-grid { display:grid; grid-template-columns:repeat(2,minmax(0,1fr)); gap:6px 16px; }
.detail-item { display:flex; align-items:center; justify-content:space-between; gap:8px 12px; min-width:0; padding:7px 10px; background:#f5f7f9; border-radius:5px; }
.detail-item :deep(.account-avatar) { width:24px; height:24px; font-size:12px; }
.detail-item :deep(.account-label-name small) { display:inline; margin:0 0 0 7px; font-size:12px; }
.detail-identity { display:flex; flex-wrap:wrap; align-items:center; gap:4px 10px; min-width:0; }
.detail-member { color:#66707c; font-size:12px; }
.detail-quantities { display:flex; flex-wrap:wrap; justify-content:flex-end; gap:4px 10px; flex-shrink:0; color:#66707c; font-size:12px; }
.detail-quantities strong { color:#20242a; }
@media(max-width:1000px) { .detail-grid { grid-template-columns:1fr; } }
.detail-heading { margin-bottom:12px; }
.detail-heading > span,.inventory-footnote { font-size:12px; color:#66707c; }
.inventory-empty { padding:20px 0; color:#66707c; }
.inventory-footnote { margin:20px 0 0; }
@media(max-width:600px) { .inventory-header,.inventory-section-heading { align-items:flex-start; flex-wrap:wrap; } .inventory-section-heading :deep(.n-input) { width:100%; max-width:none; } .filter-row { flex-direction:column; gap:4px; } .filter-row > span { width:auto; } }
</style>

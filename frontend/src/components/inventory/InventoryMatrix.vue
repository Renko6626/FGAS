<script setup lang="ts">
import { computed, nextTick, onMounted, ref, watch } from "vue";
import { NDrawer, NDrawerContent } from "naive-ui";
import type { StockAccount } from "../../api/accounts";
import type { InventoryRow, InventoryTotals, StockTransfer } from "../../api/warehouse";

const props = defineProps<{ totals: InventoryTotals[]; rows: InventoryRow[]; locations: StockAccount[]; locationCount: number; pendingCounts: Map<string, number>; transfers: StockTransfer[] }>();
const selectedSku = defineModel<string>("selectedSku", { required: true });
const matrixViewport = ref<HTMLElement | null>(null);
const showDetail = ref(false);
const detailLocation = ref("");
const rowByKey = computed(() => new Map(props.rows.map(row => [`${row.sku_code}:${row.account_code}`, row])));
const shownTotals = computed(() => props.totals);
const sortedLocations = computed(() => {
  const kinds = new Map<string, number>();
  for (const row of props.rows) {
    if ([row.quantity, row.incoming_planned_quantity, row.outgoing_planned_quantity].some(value => BigInt(value || "0") !== 0n)) kinds.set(row.account_code, (kinds.get(row.account_code) || 0) + 1);
  }
  return [...props.locations].sort((a, b) => (kinds.get(b.code) || 0) - (kinds.get(a.code) || 0) || a.name.localeCompare(b.name, "zh-CN"));
});
const shownLocations = computed(() => sortedLocations.value);
const focused = computed(() => props.totals.find(item => item.sku_code === selectedSku.value));
const detailRows = computed(() => props.rows.filter(row => row.sku_code === selectedSku.value && (!detailLocation.value || row.account_code === detailLocation.value) &&
  [row.quantity, row.incoming_planned_quantity, row.outgoing_planned_quantity].some(value => BigInt(value || "0") !== 0n)));
const detailPlans = computed(() => props.transfers.filter(item => item.lines.some(line => line.sku_code === selectedSku.value) &&
  (!detailLocation.value || item.source_account_code === detailLocation.value || item.destination_account_code === detailLocation.value)));
function cell(sku: string, location: string) { return rowByKey.value.get(`${sku}:${location}`); }
function openDetail(sku: string, location = "") { selectedSku.value = sku; detailLocation.value = location; showDetail.value = true; }
function quantityAt(transfer: StockTransfer) { return transfer.lines.find(line => line.sku_code === selectedSku.value)?.quantity; }
async function revealSelection() {
  await nextTick();
  const viewport = matrixViewport.value;
  const selected = viewport?.querySelector<HTMLElement>(".focused-row");
  if (viewport && selected) viewport.scrollTop += selected.getBoundingClientRect().top - viewport.getBoundingClientRect().top - 76;
}
watch([selectedSku, () => props.totals], revealSelection);
onMounted(revealSelection);
</script>

<template>
  <section class="inventory-matrix" aria-label="货物与保管地点分布矩阵">
    <div class="matrix-caption"><span>{{ shownTotals.length }} 种货物，显示 {{ shownLocations.length }} / {{ locationCount }} 个地点</span><span>地点列可左右滚动，社团合计包含全部地点</span></div>
    <div v-if="shownTotals.length && shownLocations.length" ref="matrixViewport" class="matrix-scroll" tabindex="0" role="region" aria-label="库存分布，可横向滚动">
      <table class="matrix-table">
        <thead><tr>
          <th class="product-column" scope="col">货物 / SKU</th>
          <th v-for="place in shownLocations" :key="place.code" scope="col" class="place-column"><span>{{ place.name }}</span><small>{{ place.member_name || '未指定负责人' }}</small></th>
          <th class="total-column" scope="col">社团合计<small>已入账库存</small></th>
        </tr></thead>
        <tbody>
          <tr v-for="item in shownTotals" :key="item.sku_code" :class="{ 'focused-row': selectedSku === item.sku_code }">
            <th scope="row" class="product-column"><button class="product-button" @click="openDetail(item.sku_code)"><strong>{{ item.sku_name }}</strong><small>{{ item.sku_code }}<span v-if="pendingCounts.has(item.sku_code)" class="plan-dot" title="有待处理转移"></span></small></button></th>
            <td v-for="place in shownLocations" :key="place.code" class="place-column">
              <button class="stock-cell" :class="{ populated: BigInt(cell(item.sku_code, place.code)?.quantity || '0') !== 0n }" :aria-label="`${item.sku_name}，${place.name}，库存 ${cell(item.sku_code, place.code)?.quantity || '0'} ${item.unit}，查看明细`" @click="openDetail(item.sku_code, place.code)">
                <strong>{{ BigInt(cell(item.sku_code, place.code)?.quantity || '0') === 0n ? '—' : cell(item.sku_code, place.code)?.quantity }}</strong>
                <span class="cell-plans"><small v-if="BigInt(cell(item.sku_code, place.code)?.incoming_planned_quantity || '0') > 0n" class="incoming">待入 {{ cell(item.sku_code, place.code)?.incoming_planned_quantity }}</small><small v-if="BigInt(cell(item.sku_code, place.code)?.outgoing_planned_quantity || '0') > 0n" class="outgoing">待出 {{ cell(item.sku_code, place.code)?.outgoing_planned_quantity }}</small></span>
              </button>
            </td>
            <td class="total-column"><button @click="openDetail(item.sku_code)"><strong>{{ item.quantity }}</strong><small>{{ item.unit }}</small></button></td>
          </tr>
        </tbody>
      </table>
    </div>
    <p v-else class="matrix-empty">{{ !shownLocations.length ? '当前负责人没有符合选择的保管地点，请调整筛选。' : '没有符合条件的货物。' }}</p>
    <p class="matrix-legend"><span class="plan-dot"></span>有待处理转移<span class="incoming">待入</span>与<span class="outgoing">待出</span>均为已批准计划，内部调拨会在两端分别显示，社团库存不变。</p>

    <NDrawer v-model:show="showDetail" :width="420" style="max-width: 100vw" placement="right">
      <NDrawerContent :title="focused?.sku_name || selectedSku" closable>
        <div v-if="focused" class="matrix-detail">
          <p class="detail-code">{{ selectedSku }}<span v-if="detailLocation"> / {{ locations.find(item => item.code === detailLocation)?.name }}</span></p>
          <div class="detail-total"><span>社团账面库存</span><strong>{{ focused.quantity }} <small>{{ focused.unit }}</small></strong></div>
          <h3>保管分布</h3>
          <div v-for="row in detailRows" :key="row.account_code" class="detail-place"><div><strong>{{ row.account_name }}</strong><small>{{ row.member_name || '未指定负责人' }}</small></div><div><strong>{{ row.quantity }} {{ row.unit }}</strong><small v-if="BigInt(row.incoming_planned_quantity || '0') > 0n">待入 {{ row.incoming_planned_quantity }}</small><small v-if="BigInt(row.outgoing_planned_quantity || '0') > 0n">待出 {{ row.outgoing_planned_quantity }}</small></div></div>
          <p v-if="!detailRows.length" class="detail-code">这个地点当前没有该货物的库存或待完成转移。</p>
          <h3>相关待处理转移</h3>
          <a v-for="plan in detailPlans" :key="plan.code" class="detail-plan" :href="`#stock?code=${encodeURIComponent(plan.code)}`"><strong>{{ plan.source_account_name }} → {{ plan.destination_account_name }}</strong><span>{{ quantityAt(plan) }} {{ focused.unit }}<small>{{ plan.code }}</small></span><small>{{ plan.status === 'pending' ? '待审批' : plan.confirmations.some(item => item.status === 'pending') ? '待完成（有人报告完成，待确认）' : '待完成' }}</small></a>
          <p v-if="!detailPlans.length" class="detail-code">没有相关的待处理转移。</p>
        </div>
      </NDrawerContent>
    </NDrawer>
  </section>
</template>

<style scoped>
.inventory-matrix { min-width:0; --product-width:190px; --place-width:136px; --total-width:96px; }
.matrix-caption { display:flex; flex-wrap:wrap; justify-content:space-between; gap:5px 12px; color:#73808b; font-size:12px; margin:0 0 10px; }
.matrix-scroll { overflow:auto; max-height:650px; border:1px solid #dfe7e9; border-radius:8px; isolation:isolate; scrollbar-color:#b7c9ca #f1f5f5; }
.matrix-table { border-collapse:separate; border-spacing:0; table-layout:fixed; width:max-content; min-width:100%; font-size:13px; }
.matrix-table th,.matrix-table td { box-sizing:border-box; border:0; border-bottom:1px solid #e8edef !important; padding:0; vertical-align:middle; white-space:normal; }
.matrix-table thead th { position:sticky; top:0; z-index:3; height:76px; background:#edf4f3; color:#405b5b; text-align:center; font-weight:600; padding:12px; }
.matrix-table th small { display:block; font-size:11px; font-weight:400; color:#7a8a8c; margin-top:5px; }
.matrix-table .product-column { position:sticky; left:0; z-index:2; width:var(--product-width); min-width:var(--product-width); max-width:var(--product-width); background:#fff; border-right:1px solid #e2e9ea; text-align:left; }
.matrix-table thead .product-column { z-index:4; background:#edf4f3; }
.matrix-table .place-column { width:var(--place-width); min-width:var(--place-width); max-width:var(--place-width); text-align:center; }
.matrix-table .total-column { position:sticky; right:0; z-index:2; width:var(--total-width); min-width:var(--total-width); max-width:var(--total-width); background:#f4f8f7; border-left:1px solid #dfe9e6; text-align:center; }
.matrix-table thead .total-column { z-index:4; background:#e4efeb; }
.matrix-table tbody tr:last-child > * { border-bottom:0; }
.matrix-table button { border:0; border-image:none; background:transparent; color:inherit; min-width:0; cursor:pointer; }
.product-button { display:block; width:100%; text-align:left; padding:13px 14px; }
.product-button strong { display:block; font-size:13px; font-weight:500; line-height:1.6; overflow-wrap:anywhere; }
.product-button small { display:flex !important; gap:7px; align-items:center; }
.plan-dot { display:inline-block; width:6px; height:6px; flex-shrink:0; border-radius:50%; background:#bc812b; }
.stock-cell { width:100%; min-height:66px; padding:9px 4px; color:#c4ced1 !important; }
.stock-cell strong { font-size:17px; font-weight:500; font-variant-numeric:tabular-nums; }
.stock-cell.populated { color:#245e58 !important; background:#eaf5f12e; }
.cell-plans { display:flex; flex-wrap:wrap; justify-content:center; gap:3px 7px; }
.cell-plans small { font-size:10px; white-space:nowrap; }
.incoming { color:#33796b !important; }
.outgoing { color:#a77528 !important; }
.total-column button { width:100%; padding:15px 4px; }
.total-column button strong { font-size:18px; font-variant-numeric:tabular-nums; }
.total-column button small { display:inline; margin-left:5px; font-size:11px; color:#7b8c88; }
.matrix-table tbody tr:hover .product-column,.matrix-table tbody tr.focused-row .product-column { background:#f0f7f5; }
.stock-cell:hover { background:#e8f2ef !important; }
.matrix-legend { display:flex; align-items:center; flex-wrap:wrap; gap:5px; color:#77848c; font-size:11px; margin:12px 0 0; }
.matrix-legend .plan-dot { margin-right:2px; }
.matrix-legend .incoming { margin-left:8px; }
.matrix-empty { padding:35px 0; color:#73808b; }
.matrix-detail { color:#273e43; }
.detail-code { font-size:12px; color:#78858c; line-height:1.7; }
.detail-total { background:#edf5f1; padding:18px; border-radius:7px; display:flex; justify-content:space-between; align-items:center; }
.detail-total > span { font-size:13px; }
.detail-total strong { font-size:26px; }
.detail-total small { font-size:12px; font-weight:400; }
.matrix-detail h3 { margin:28px 0 12px; font-size:15px; }
.detail-place { display:flex; justify-content:space-between; gap:15px; padding:13px 0; border-bottom:1px solid #e9edef; }
.detail-place > div:last-child { text-align:right; }
.detail-place strong,.detail-place small { display:block; }
.detail-place strong { font-size:13px; }
.detail-place small { font-size:12px; margin-top:5px; color:#75878a; }
.detail-plan { display:block; color:inherit; text-decoration:none; padding:15px 0; border-bottom:1px solid #e9edef; }
.detail-plan strong { display:block; font-size:13px; line-height:1.7; }
.detail-plan > span { display:flex; justify-content:space-between; margin:7px 0; font-size:13px; }
.detail-plan small { font-size:11px; color:#75878a; }
.detail-plan:hover strong { color:#26746b; }
@media(max-width:760px) {
  .inventory-matrix { --product-width:130px; --place-width:110px; --total-width:70px; }
  .matrix-caption { line-height:1.7; }
  .matrix-table thead th { padding:10px 8px; font-size:12px; }
  .product-button { padding:12px 9px; }
  .product-button strong { font-size:12px; }
  .total-column button strong { font-size:16px; }
  .total-column button small { display:block; margin:2px 0 0; }
  .matrix-scroll { max-height:600px; }
}
</style>

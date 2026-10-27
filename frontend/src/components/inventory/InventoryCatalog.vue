<script setup lang="ts">
import { computed, nextTick, onMounted, ref, watch } from "vue";
import { NSelect } from "naive-ui";
import type { InventoryTotals } from "../../api/warehouse";

const props = defineProps<{ totals: InventoryTotals[]; pendingCounts: Map<string, number>; sortOptions: { label: string; value: string }[] }>();
const selectedSku = defineModel<string>("selectedSku", { required: true });
const sort = defineModel<string>("sort", { required: true });
const viewport = ref<HTMLElement | null>(null);
const options = computed(() => props.totals.map(item => ({ label: `${item.sku_name}（${item.sku_code}）`, value: item.sku_code })));
async function revealSelection() {
  await nextTick();
  const list = viewport.value;
  const selected = list?.querySelector<HTMLElement>(".catalog-item.selected");
  if (list && selected) list.scrollTop = selected.offsetTop - list.clientHeight / 2 + selected.clientHeight / 2;
}
watch([selectedSku, () => props.totals], revealSelection);
onMounted(revealSelection);
</script>

<template>
  <aside class="inventory-catalog" aria-label="货物选择与排序">
    <div class="catalog-heading"><strong>货物 <small>{{ totals.length }} 种</small></strong><NSelect v-model:value="sort" size="small" :options="sortOptions" aria-label="货物排序" /></div>
    <div ref="viewport" class="catalog-items">
      <button v-for="item in totals" :key="item.sku_code" class="catalog-item" :class="{ selected: selectedSku === item.sku_code }" :aria-pressed="selectedSku === item.sku_code" @click="selectedSku = item.sku_code">
        <span class="catalog-name">{{ item.sku_name }}</span>
        <span class="catalog-meta"><small>{{ item.sku_code }}</small><strong title="社团账面库存">{{ item.quantity }}<small>{{ item.unit }}</small></strong></span>
        <span v-if="pendingCounts.get(item.sku_code)" class="catalog-pending">{{ pendingCounts.get(item.sku_code) }} 笔待处理</span>
      </button>
      <p v-if="!totals.length" class="catalog-empty">没有符合条件的货物</p>
    </div>
    <div class="catalog-mobile"><NSelect v-model:value="selectedSku" :options="options" filterable placeholder="没有符合条件的货物" aria-label="选择货物" /></div>
  </aside>
</template>

<style scoped>
.inventory-catalog { min-width:0; border-right:1px solid #e4ebeb; padding-right:15px; }
.catalog-heading { display:flex; flex-wrap:wrap; align-items:center; justify-content:space-between; gap:8px; padding:0 0 10px; }
.catalog-heading strong { font-size:13px; color:#445b5c; }
.catalog-heading small { font-size:11px; font-weight:400; color:#8b979b; margin-left:5px; }
.catalog-heading :deep(.n-select) { width:100%; }
.catalog-items { position:relative; max-height:650px; overflow:auto; scrollbar-width:thin; }
.catalog-item { display:block; width:100%; text-align:left; padding:11px 10px; border:0; border-left:3px solid transparent; background:transparent; color:#435557; min-width:0; border-radius:0 5px 5px 0; }
.catalog-item:hover { background:#f4f8f7; }
.catalog-item.selected { background:#eaf3ef; border-left-color:#337a6e; }
.catalog-name { display:-webkit-box; -webkit-line-clamp:2; -webkit-box-orient:vertical; overflow:hidden; font-size:12px; line-height:1.7; }
.catalog-item.selected .catalog-name { color:#23594f; font-weight:650; }
.catalog-meta { display:flex; justify-content:space-between; gap:7px; align-items:center; margin-top:7px; }
.catalog-meta > small { color:#8b979b; font-size:10px; }
.catalog-meta strong { font-size:13px; font-variant-numeric:tabular-nums; white-space:nowrap; }
.catalog-meta strong small { font-size:10px; font-weight:400; margin-left:3px; }
.catalog-pending { display:inline-block; margin-top:6px; padding:1px 5px; border-radius:3px; background:#f4e4c4; color:#815a20 !important; font-size:10px; }
.catalog-empty { color:#83918d; font-size:12px; padding:16px 4px; }
.catalog-mobile { display:none; }
@media(max-width:760px) {
  .inventory-catalog { border:0; padding:0; margin-bottom:12px; }
  .catalog-heading > strong,.catalog-items { display:none; }
  .catalog-heading { padding:0 0 8px; }
  .catalog-heading :deep(.n-select) { width:100%; }
  .catalog-mobile { display:block; }
}
</style>

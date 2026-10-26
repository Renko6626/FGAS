<script setup lang="ts">
import { computed } from "vue";
import { NInput, NSelect } from "naive-ui";
import { type Sku, type StockTransfer } from "../api/warehouse";
import { stockStatuses } from "../presentation/warehouse";
import type { StockFilters } from "../composables/transferFilters";
const props = defineProps<{
  items: StockTransfer[];
  skus: Sku[];
}>();
const filters = defineModel<StockFilters>({ required: true });
const statusOptions = Object.entries(stockStatuses).map(([value, label]) => ({ label, value }));
const tags = computed(() =>
  [...new Set(props.items.flatMap(t => t.tags))].map(value => ({ label: value, value })),
);
</script>

<template>
  <div class="stock-filters">
    <NInput
      v-model:value="filters.search"
      clearable
      placeholder="搜索用途、货物代号、名称、来源或去向"
    />
    <NSelect
      v-model:value="filters.skuCode"
      clearable
      filterable
      :options="skus.map(s => ({ label: `${s.code} ${s.name}`, value: s.code }))"
      placeholder="所有商品"
    />
    <NSelect
      v-model:value="filters.status"
      clearable
      :options="statusOptions"
      placeholder="所有货物状态"
    />
    <NSelect
      v-model:value="filters.tag"
      clearable
      filterable
      tag
      :options="tags"
      placeholder="所有标签"
    />
  </div>
</template>

<style scoped>
.stock-filters {
  display: grid;
  grid-template-columns: minmax(240px, 2fr) minmax(180px, 1fr) minmax(160px, 1fr) minmax(
      140px,
      1fr
    );
  gap: 16px;
  margin-bottom: 24px;
}
@media (max-width: 900px) { .stock-filters { grid-template-columns: 1fr; } }
</style>

<script setup lang="ts">
import { computed } from "vue";
import { NInput, NSelect } from "naive-ui";
import { stockStatuses, type StockTransfer } from "../api/warehouse";
import type { StockFilters } from "../composables/transferFilters";
const props = defineProps<{
  items: StockTransfer[];
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
      placeholder="搜索用途、货物、来源或去向"
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
  grid-template-columns: minmax(240px, 2fr) minmax(160px, 1fr) minmax(
      140px,
      1fr
    );
  gap: 16px;
  margin-bottom: 24px;
}
@media (max-width: 650px) { .stock-filters { grid-template-columns: 1fr; } }
</style>
